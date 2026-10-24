from dataclasses import dataclass, asdict, field
import math
import os
from pathlib import Path

FORMAT_GROUPS = (
    ("WAV", (".wav", ".wave")),
    ("FLAC", (".flac",)),
    ("AIFF", (".aif", ".aiff", ".aifc")),
    ("MP3", (".mp3",)),
    ("AAC-LC", (".aac", ".m4a", ".m4b", ".m4r", ".mp4")),
    ("Ogg Opus", (".opus", ".ogg", ".oga")),
)
SUPPORTED = {ext for _,extensions in FORMAT_GROUPS for ext in extensions}
SUPPORTED_SUMMARY = "WAV · AIFF · FLAC · MP3 · M4A · AAC · Ogg Opus"
SUPPORTED_DISPLAY = "WAV/WAVE · FLAC · AIF/AIFF/AIFC · MP3 · AAC/M4A/M4B/M4R/MP4 (AAC-LC) · OPUS/OGG/OGA (Opus)"
AUDIO_FILE_FILTER = "Supported audio (" + " ".join("*"+ext for ext in sorted(SUPPORTED)) + ");;" + ";;".join(
    name + " (" + " ".join("*"+ext for ext in extensions) + ")" for name,extensions in FORMAT_GROUPS) + ";;All files (*)"
MP4_EXTENSIONS = {".m4a", ".m4b", ".m4r", ".mp4"}
WAV_EXTENSIONS = {".wav", ".wave"}
AIFF_EXTENSIONS = {".aif", ".aiff", ".aifc"}
OPUS_EXTENSIONS = {".opus", ".ogg", ".oga"}


@dataclass(frozen=True)
class Settings:
    target: float = -14.0
    ceiling: float = -1.0
    output_format: str = "source"
    allow_limiter: bool = False
    normalize_lufs: bool = True

    def __post_init__(self):
        if not math.isfinite(self.target) or not -36 <= self.target <= -6:
            raise ValueError("Target must be between -36 and -6 LUFS.")
        if not math.isfinite(self.ceiling) or not -9 <= self.ceiling <= -0.1:
            raise ValueError("Ceiling must be between -9 and -0.1 dBTP.")
        if self.output_format != "source":
            raise ValueError("OpenLUFS preserves the original format; conversion is not supported.")
        if not isinstance(self.normalize_lufs, bool):
            raise ValueError("LUFS normalization must be enabled or disabled.")
        if not isinstance(self.allow_limiter, bool):
            raise ValueError("Matching mode must be enabled or disabled.")

@dataclass(frozen=True)
class Measurement:
    integrated: float
    true_peak: float
    loudness_range: float
    threshold: float
    sample_rate: int
    channels: int
    duration: float
    codec: str
    bits: int
    bitrate: int = 0
    bitrate_mode: str = ""
    profile: str = ""

@dataclass
class Result:
    source: str
    destination: str
    before: Measurement
    after: Measurement
    gain_db: float
    mode: str
    attempts: int
    warnings: list[str]
    processing: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def discover(paths, recursive=True, exclude=None, cancel=None):
    """Deduplicate sources and skip symlink directories and the output tree."""
    files = set()
    excluded = Path(exclude).resolve() if exclude else None
    for item in paths:
        if cancel is not None and cancel.is_set():
            break
        path = Path(item).resolve()
        exclusion = excluded if excluded and path.is_dir() and excluded != path and excluded.is_relative_to(path) else None
        candidates = []
        if path.is_dir():
            for root, dirs, names in os.walk(path, followlinks=False):
                if cancel is not None and cancel.is_set():
                    break
                dirs[:] = sorted(d for d in dirs if not (Path(root)/d).is_symlink()
                                 and (exclusion is None or (Path(root)/d).resolve() != exclusion))
                candidates.extend(Path(root)/name for name in names)
                if not recursive:
                    break
        else:
            candidates.append(path)
        for candidate in candidates:
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED:
                resolved = candidate.resolve()
                if exclusion and resolved.is_relative_to(exclusion):
                    continue
                files.add(resolved)
    return sorted(files, key=lambda p: str(p).casefold())


def plan_outputs(files, folder, output_format, source_root=None):
    """Allocate unique destinations without overwriting sources or exports."""
    root = Path(folder).resolve()
    source_root = Path(source_root).resolve() if source_root else None
    reserved = {str(Path(p).resolve()).casefold() for p in files}
    planned = []
    for item in files:
        source = Path(item).resolve()
        relative = source.relative_to(source_root) if source_root and source.is_relative_to(source_root) else Path(source.name)
        if output_format != "source":
            raise ValueError("Exports must keep the original format.")
        ext = source.suffix
        dest = root/relative.with_suffix(ext)
        base, index = dest, 1
        while dest.exists() or str(dest).casefold() in reserved:
            dest = base.with_name(f"{base.stem} ({index}){base.suffix}")
            index += 1
        reserved.add(str(dest).casefold())
        planned.append((source, dest))
    return planned
