from datetime import datetime, timezone
from dataclasses import asdict
import json
from pathlib import Path
import uuid
from . import __version__
from .engine import Cancelled, Engine
from .analysis_cache import AnalysisCache


def write_report(folder, settings, results, errors, cancelled=False):
    path = Path(folder)/f"OpenLUFS-report-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {"version": __version__, "created_utc": datetime.now(timezone.utc).isoformat(),
                "settings": asdict(settings), "cancelled": cancelled,
                "results": [r.to_dict() for r in results], "errors": errors}
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return path


def process_batch(planned, settings, cancel, callback=None, analysis_cache=None):
    callback = callback or (lambda *args: None)
    engine, results, errors = Engine(cancel), [], []
    cache = analysis_cache if analysis_cache is not None else AnalysisCache()
    for index, (source, destination) in enumerate(planned):
        if cancel.is_set():
            break
        try:
            callback(index, "Processing", None)
            before = cache.measure(source, engine.analyze)
            callback(index, "Source ready", before)
            result = engine.normalize(source, destination, settings, before=before,
                                      progress=lambda stage: None)
            results.append(result)
            callback(index, "Complete", result)
        except Cancelled:
            callback(index, "Cancelled", None)
            break
        except Exception as error:
            errors.append({"source": str(source), "error": str(error)})
            callback(index, "Failed", str(error))
    return results, errors
