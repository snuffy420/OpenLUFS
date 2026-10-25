"""Reuse source measurements only while the source file's identity is unchanged."""
from dataclasses import dataclass
from pathlib import Path
import threading


def source_stamp(path):
    stat = Path(path).stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


@dataclass(frozen=True)
class CachedAnalysis:
    stamp: tuple
    measurement: object


class AnalysisCache:
    def __init__(self):
        self.entries={};self._lock=threading.RLock();self._key_locks={}
        self._generation=0;self._versions={}

    def get(self,path):
        key=Path(path).resolve()
        with self._lock:
            entry=self.entries.get(key)
            if entry is None:return None
            try:valid=entry.stamp==source_stamp(key)
            except OSError:valid=False
            if not valid:
                self.entries.pop(key,None);return None
            return entry.measurement

    def measure(self,path,analyze):
        key=Path(path).resolve()
        with self._lock:key_lock=self._key_locks.setdefault(key,threading.Lock())
        # Different files measure concurrently; duplicate requests share one meter pass.
        with key_lock:
            cached=self.get(key)
            if cached is not None:return cached
            with self._lock:token=(self._generation,self._versions.get(key,0))
            stamp=source_stamp(key);measurement=analyze(key)
            if source_stamp(key)!=stamp:
                raise ValueError('Source changed during analysis; analyze it again before processing.')
            with self._lock:
                if token==(self._generation,self._versions.get(key,0)):
                    self.entries[key]=CachedAnalysis(stamp,measurement)
            return measurement

    def discard(self,path):
        key=Path(path).resolve()
        with self._lock:
            self.entries.pop(key,None);self._versions[key]=self._versions.get(key,0)+1

    def clear(self):
        with self._lock:
            self.entries.clear();self._generation+=1
