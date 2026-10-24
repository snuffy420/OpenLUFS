"""Reuse source measurements only while the source file's identity is unchanged."""
from dataclasses import dataclass
from pathlib import Path


def source_stamp(path):
    stat = Path(path).stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


@dataclass(frozen=True)
class CachedAnalysis:
    stamp: tuple
    measurement: object


class AnalysisCache:
    def __init__(self):
        self.entries = {}

    def get(self, path):
        key = Path(path).resolve()
        entry = self.entries.get(key)
        if entry is None:
            return None
        try:
            valid = entry.stamp == source_stamp(key)
        except OSError:
            valid = False
        if not valid:
            self.entries.pop(key, None)
            return None
        return entry.measurement

    def measure(self, path, analyze):
        key = Path(path).resolve()
        cached = self.get(key)
        if cached is not None:
            return cached
        stamp = source_stamp(key)
        measurement = analyze(key)
        if source_stamp(key) != stamp:
            raise ValueError('Source changed during analysis; analyze it again before processing.')
        self.entries[key] = CachedAnalysis(stamp, measurement)
        return measurement

    def discard(self, path):
        self.entries.pop(Path(path).resolve(), None)

    def clear(self):
        self.entries.clear()
