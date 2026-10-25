import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import signal
import threading
import sys
from .batch import process_batch, write_report, analyze_batch
from .engine import Engine
from .models import Settings, discover, plan_outputs


def main(argv=None):
    parser = argparse.ArgumentParser(prog="OpenLUFS", description="Analyze and normalize integrated loudness.")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze", help="Measure audio without changing files.")
    analyze.add_argument("paths", nargs="+")
    normalize = sub.add_parser("normalize", help="Write verified normalized copies.")
    normalize.add_argument("paths", nargs="+")
    normalize.add_argument("-o", "--output", required=True)
    normalize.add_argument("--target", type=float, default=-14)
    normalize.add_argument("--ceiling", type=float, default=-1)
    normalize.add_argument("--limiter", action="store_true", help="Enable peak limiting; with LUFS enabled this prioritizes target matching.")
    normalize.add_argument("--peak-only", action="store_true", help="Disable LUFS normalization and control peaks only (requires --limiter).")
    normalize.add_argument("--match-target", action="store_true", help="Allow peak limiting and re-encoding when needed to match LUFS.")
    normalize.add_argument("--no-recursive", action="store_true")
    for command in [analyze,normalize]:
        command.add_argument('--jobs',type=int,choices=range(1,33),metavar='N',
                             help='Maximum concurrent tracks, 1–32. Default: automatic CPU/memory limits; resource limits still apply.')
    args = parser.parse_args(argv)
    try:
        files = discover(args.paths, not getattr(args, "no_recursive", False), getattr(args, "output", None))
        if not files:
            parser.error("No supported audio files found.")
        if args.command == "analyze":
            cancel=threading.Event();previous=signal.signal(signal.SIGINT,lambda *_:cancel.set())
            try:measurements,errors=analyze_batch(files,cancel,workers=args.jobs)
            finally:signal.signal(signal.SIGINT,previous)
            rows=[]
            for index,measurement in measurements:
                row=asdict(measurement)
                row={k:v if not isinstance(v,float) or math.isfinite(v) else None for k,v in row.items()}
                rows.append({'source':str(files[index]),**row})
            print(json.dumps(rows,indent=2,ensure_ascii=False,allow_nan=False))
            for error in errors:print(f"{error['source']}: {error['error']}",file=sys.stderr)
            return 130 if cancel.is_set() else 1 if errors else 0
        settings = Settings(args.target, args.ceiling, allow_limiter=args.limiter or args.match_target, normalize_lufs=not args.peak_only)
        root = args.paths[0] if len(args.paths) == 1 and Path(args.paths[0]).is_dir() else None
        planned = plan_outputs(files, args.output, "source", root)
        cancel = threading.Event()
        previous=signal.signal(signal.SIGINT, lambda *_: cancel.set())
        try:
            results, errors = process_batch(planned, settings, cancel,
                lambda i, stage, value: print(f"[{i+1}/{len(files)}] {files[i].name}: {stage}"),workers=args.jobs)
        finally:signal.signal(signal.SIGINT,previous)
        report = write_report(args.output, settings, results, errors, cancel.is_set())
        print(f"{len(results)} exported; {len(errors)} failed. Report: {report}")
        for error in errors:
            print(f"{error['source']}: {error['error']}")
        return 130 if cancel.is_set() else 1 if errors else 0
    except Exception as error:
        parser.exit(1, f"OpenLUFS: {error}\n")
