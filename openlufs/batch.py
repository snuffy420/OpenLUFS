from datetime import datetime, timezone
from dataclasses import asdict
import json
from pathlib import Path
import uuid
import shutil
import threading
from contextlib import contextmanager
from .parallel import run_tracks
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


class DiskBudget:
    """Conservative temporary-space reservations shared by active track jobs."""
    def __init__(self):self.condition=threading.Condition();self.reserved={}

    @contextmanager
    def reserve(self,destination,required,cancel):
        parent=Path(destination).parent;parent.mkdir(parents=True,exist_ok=True)
        device=parent.stat().st_dev
        with self.condition:
            while True:
                if cancel.is_set():raise Cancelled()
                held=self.reserved.get(device,0)
                available=shutil.disk_usage(parent).free-held-64*1024**2
                if required<=available:
                    self.reserved[device]=held+required;break
                if not held:raise OSError('Not enough free space for a verified export and its temporary files.')
                self.condition.wait(.1)
        try:yield
        finally:
            with self.condition:
                self.reserved[device]-=required;self.condition.notify_all()


def temporary_space(source,before,settings):
    size=Path(source).stat().st_size
    raw=before.duration*before.sample_rate*before.channels*4
    if settings.allow_limiter and not settings.normalize_lufs and before.true_peak<=settings.ceiling:
        return int(size*1.1+16*1024**2)
    if settings.allow_limiter:return int(3*raw+size+32*1024**2)
    if before.codec in {'mp3','aac','opus'}:return int(size*1.1+16*1024**2)
    return int(2*max(size,raw)+16*1024**2)


def analyze_batch(files,cancel,callback=None,analysis_cache=None,workers=None):
    files=list(files);cache=analysis_cache if analysis_cache is not None else AnalysisCache()
    def job(index,source,emit):
        engine=Engine(cancel,threads=1)
        emit('Using analysis' if cache.get(source) is not None else 'Measuring')
        return 'Analyzed',cache.measure(source,engine.analyze)
    outcomes=run_tracks(files,job,cancel,callback,workers)
    measurements=[(i,payload) for i,stage,payload in outcomes if stage=='Analyzed']
    errors=[{'source':str(files[i]),'error':payload} for i,stage,payload in outcomes if stage=='Failed']
    return measurements,errors


def process_batch(planned,settings,cancel,callback=None,analysis_cache=None,workers=None):
    planned=list(planned);cache=analysis_cache if analysis_cache is not None else AnalysisCache()
    budget=DiskBudget()
    def job(index,item,emit):
        source,destination=item;engine=Engine(cancel,threads=1)
        emit('Processing')
        before=cache.measure(source,engine.analyze);emit('Source ready',before)
        with budget.reserve(destination,temporary_space(source,before,settings),cancel):
            result=engine.normalize(source,destination,settings,before=before,progress=lambda stage:None)
        return 'Complete',result
    outcomes=run_tracks(planned,job,cancel,callback,workers)
    results=[payload for _,stage,payload in outcomes if stage=='Complete']
    errors=[{'source':str(planned[i][0]),'error':payload} for i,stage,payload in outcomes if stage=='Failed']
    return results,errors
