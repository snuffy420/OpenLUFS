"""Exercise the actual frozen executable, including its extracted FFmpeg."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parents[1]
exe=Path(sys.argv[1]) if len(sys.argv)>1 else root/"dist/OpenLUFS.exe"
with tempfile.TemporaryDirectory(prefix="openlufs-frozen-",dir=root/".build-temp") as folder:
    report=Path(folder)/"diagnostics.json"
    run=subprocess.run([str(exe),"--diagnostics",str(report)],timeout=120)
    if not report.exists():
        raise SystemExit(f"Frozen diagnostics failed: {run.returncode}")
    data=json.loads(report.read_text(encoding="utf-8"))
    print(json.dumps(data,indent=2))
    if run.returncode or not data.get("ok"):
        raise SystemExit("Frozen audio self-test failed")
