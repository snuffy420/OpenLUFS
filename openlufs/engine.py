"""Full-track measurement and dynamics-preserving constant-gain processing.

loudnorm is used only as a meter: its output is discarded. Renders and retries
always read the original source. No tempo or pitch processing is performed.
"""
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import uuid
from .models import Measurement, Result, Settings, WAV_EXTENSIONS, AIFF_EXTENSIONS, MP4_EXTENSIONS, OPUS_EXTENSIONS
from .ogg import inspect_opus, apply_opus_gain
from .analysis_cache import source_stamp
from .mp3 import silent_clamp_count, bitrate_properties
from .containers import restore_metadata, non_audio_digest
import mutagen

class Cancelled(Exception):
    pass


def resource_path(relative):
    base=Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    candidate=base/relative
    if candidate.exists() or getattr(sys,"frozen",False):
        return candidate
    return Path(__file__).resolve().parent/"resources"/relative


def find_ffmpeg():
    override = os.environ.get("OPENLUFS_FFMPEG")
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError("OPENLUFS_FFMPEG does not point to a file.")
        return str(path)
    bundled = resource_path("vendor/ffmpeg.exe" if os.name == "nt" else "vendor/ffmpeg")
    if bundled.is_file():
        return str(bundled)
    installed = shutil.which("ffmpeg")
    if installed:
        return installed
    raise RuntimeError("FFmpeg was not found. Run tools/fetch_ffmpeg.py or set OPENLUFS_FFMPEG.")

def find_gain_tool(platform_name=None):
    platform_name=platform_name or sys.platform
    override=os.environ.get('OPENLUFS_MP3RGAIN')
    if override:
        path=Path(override).expanduser().resolve()
        if not path.is_file():raise RuntimeError('OPENLUFS_MP3RGAIN does not point to a file.')
        return path
    name='mp3rgain.exe' if platform_name=='win32' else 'mp3rgain'
    bundled=resource_path('vendor/'+name)
    if bundled.is_file():return bundled
    installed=shutil.which('mp3rgain')
    if installed:return Path(installed)
    raise RuntimeError('mp3rgain was not found. Run python tools/fetch_mp3rgain.py, install mp3rgain on PATH, or set OPENLUFS_MP3RGAIN.')


class Engine:
    def __init__(self, cancel=None, executable=None, threads=2):
        self.cancel = cancel if cancel is not None else threading.Event()
        self.executable = executable or find_ffmpeg()
        self.threads=max(1,min(32,int(threads)))

    def run(self, arguments, executable=None):
        if self.cancel.is_set():
            raise Cancelled()
        process = subprocess.Popen(
            [str(executable or self.executable), *([] if executable else ["-hide_banner", "-nostdin", "-nostats", "-filter_threads", str(self.threads), "-filter_complex_threads", str(self.threads), "-threads", str(self.threads)]), *map(str, arguments)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            while True:
                try:
                    stdout, stderr = process.communicate(timeout=0.15)
                    break
                except subprocess.TimeoutExpired:
                    if self.cancel.is_set():
                        raise Cancelled()
            if self.cancel.is_set():
                raise Cancelled()
            text = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
            if process.returncode:
                raise RuntimeError(("Gain tool: " if executable else "FFmpeg: ") + text[-1800:].strip())
            return text
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def analyze(self, path):
        text = self.run(["-i", Path(path), "-map", "0:a:0", "-vn", "-sn", "-dn",
                         "-af", "loudnorm=I=-24:TP=-1:LRA=50:print_format=json",
                         "-f", "null", "-"])
        matches = re.findall(r'\{\s*"input_i".*?\}', text, flags=re.S)
        if not matches:
            raise RuntimeError("Could not read loudness measurement.")
        data = json.loads(matches[-1])
        header = text.split("Stream mapping:")[0]
        stream = re.search(r"^\s*Stream #.*?Audio:\s*(.+)", header, flags=re.M)
        if not stream:
            raise RuntimeError("No decodable audio stream found.")
        description = stream.group(1)
        rate = re.search(r"(\d+) Hz", description)
        channel = re.search(r"\d+ Hz,\s*([^,]+)", description)
        if not rate or not channel:
            raise RuntimeError("Could not determine audio properties.")
        layout = channel.group(1).strip()
        channels = {"mono": 1, "stereo": 2}.get(layout, 0)
        if channels not in {1, 2}:
            raise ValueError("This release supports mono and stereo audio. Multichannel audio is not downmixed.")
        duration = re.search(r"Duration: (\d+):(\d+):([\d.]+)", header)
        seconds = int(duration[1])*3600+int(duration[2])*60+float(duration[3]) if duration else 0.0
        bits_match = re.search(r"\((\d+) bit\)", description)
        codec = description.split(",")[0].split(" ")[0]
        bits = int(bits_match.group(1)) if bits_match else (32 if "s32" in description or "flt" in description else 16)
        if "24" in codec:
            bits = 24
        elif codec in {"pcm_f32le", "pcm_f64le"}:
            bits = 64 if "64" in codec else 32
        if codec.startswith("pcm_"):
            depth=re.search(r"(8|16|24|32|64)(?:le|be)?$",codec)
            if depth: bits=int(depth.group(1))
        if Path(path).suffix.lower()==".aac" and codec=="aac":
            from .render_formats import adts_samples
            seconds=adts_samples(path)/int(rate.group(1))
        bitrate,bitrate_mode=0,""
        try:
            original=mutagen.File(path)
            if original is not None:
                bitrate=int(getattr(original.info,"bitrate",0) or 0)
                if codec=="alac":
                    bits=int(getattr(original.info,"bits_per_sample",0) or 0)
                mode=getattr(original.info,"bitrate_mode",None)
                bitrate_mode=getattr(mode,"name",str(mode) if mode is not None else "").replace("BitrateMode.","")
        except Exception:
            pass
        if codec=="mp3":
            bitrate,bitrate_mode=bitrate_properties(path)
        if codec=="aac" and Path(path).suffix.lower()==".aac" and bitrate<=0 and seconds>0:
            from .render_formats import tag_bounds
            _,start,end=tag_bounds(path)
            bitrate=round((end-start)*8/seconds)
        profile_match=re.search(r"\(([^)]+)\)",description) if codec=="aac" else None
        profile=profile_match[1] if profile_match else ""
        return Measurement(float(data["input_i"]), float(data["input_tp"]),
                           float(data["input_lra"]), float(data["input_thresh"]),
                           int(rate.group(1)), channels, seconds, codec, bits, bitrate, bitrate_mode, profile)


    @staticmethod
    def pcm_encoding(source, before):
        ext=source.suffix.lower()
        if ext in WAV_EXTENSIONS and before.codec in {'pcm_u8','pcm_s16le','pcm_s24le','pcm_s32le','pcm_f32le','pcm_f64le'}:
            return ['-f','wav','-c:a',before.codec,'-rf64','auto']
        if ext in AIFF_EXTENSIONS and before.codec in {'pcm_s8','pcm_s16be','pcm_s24be','pcm_s32be','pcm_f32be','pcm_f64be','pcm_s16le','pcm_s24le','pcm_s32le'}:
            return ['-f','aiff','-c:a',before.codec]
        if ext in MP4_EXTENSIONS and before.codec=='alac':
            if before.bits not in {16,24}:
                raise ValueError('ALAC export supports 16-bit and 24-bit sources; other depths are rejected rather than changed.')
            return ['-c:a','alac','-sample_fmt','s16p' if before.bits==16 else 's32p',
                    '-bits_per_raw_sample',str(before.bits),'-f','mp4']
        if ext=='.flac':
            return ['-c:a','flac','-sample_fmt','s16' if before.bits<=16 else 's32','-bits_per_raw_sample',str(before.bits)]
        raise ValueError('No verified lossless, metadata-preserving renderer for this format. No conversion or lossy re-encoding was performed.')

    def normalize(self, source, destination, settings=Settings(), before=None, progress=None):
        source,destination=Path(source).resolve(),Path(destination).resolve()
        if source==destination or destination.exists():
            raise ValueError('Output must be a new file. Originals and existing exports are never overwritten.')
        if source.suffix.lower()!=destination.suffix.lower():
            raise ValueError('Output must retain the original file format.')
        notify=progress or (lambda stage:None)
        initial_stamp=source_stamp(source)
        if before is None:
            notify('Measuring')
            before=self.analyze(source)
        else:
            notify('Using analysis')
        if not math.isfinite(before.integrated) or not math.isfinite(before.true_peak):
            raise ValueError('Silence or audio below the loudness gate cannot be normalized.')
        if before.duration and before.duration<0.4:
            raise ValueError('Audio must be at least 400 ms for integrated loudness measurement.')
        if not settings.normalize_lufs and not settings.allow_limiter:
            raise ValueError("Enable LUFS normalization or the peak limiter before processing.")
        if settings.allow_limiter:
            from .matching import normalize_matching
            return normalize_matching(self, source, destination, settings, before, notify)
        requested=settings.target-before.integrated
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=destination.with_name(f'.openlufs-{uuid.uuid4().hex}{destination.suffix}')
        warnings=[]
        direct_notes=[]
        ext=source.suffix.lower()
        direct=ext in ({'.mp3','.aac'} | MP4_EXTENSIONS) and before.codec in {'mp3','aac'}
        opus=ext in OPUS_EXTENSIONS and before.codec=='opus'
        step_db=1/256 if opus else 20*math.log10(2**0.25)
        gain=min(requested,settings.ceiling-before.true_peak-0.02)
        peak_constrained=gain<requested-0.100001
        steps=None
        if direct or opus:
            tool=find_gain_tool() if direct else None
            steps=min(round(requested/step_db),math.floor((settings.ceiling-before.true_peak)/step_db))
            gain=steps*step_db
            peak_constrained=steps<round(requested/step_db)
            metadata_hash=non_audio_digest(source) if direct else None
            if opus: inspect_opus(source)
        else:
            encoding=self.pcm_encoding(source,before)
        try:
            for attempt in range(1,5):
                if direct or opus:
                    notify('Applying header gain' if opus else 'Applying direct gain')
                    shutil.copyfile(source,temporary)
                    if opus and steps:
                        opus_notes=apply_opus_gain(temporary,steps)
                    elif steps:
                        text=self.run(['-g',steps,'-s','s','-o','json',temporary],executable=tool)
                        start=text.find('{')
                        if start<0: raise RuntimeError('Gain tool did not return a verification result.')
                        document,_=json.JSONDecoder().raw_decode(text[start:])
                        rows=document.get('files',[])
                        if not rows or rows[0].get('status')!='success' or rows[0].get('gain_applied_steps')!=steps:
                            raise ValueError('This encoding could not be adjusted safely without re-encoding.')
                        warning = str(rows[0].get('warning') or '')
                        direct_notes = []
                        if 'unsupported' in warning.lower():
                            raise ValueError('Unsupported encoded gain adjustment; no output was committed.')
                        if 'clamp' in warning.lower():
                            match = re.fullmatch(r'(\d+) gain value\(s\) clamped at 0 \(silence\) - saturated gain is not losslessly reversible', warning)
                            if ext != '.mp3' or steps >= 0 or not match:
                                raise ValueError('Encoded gain bounds reached; exact constant gain is unavailable for this file.')
                            count = silent_clamp_count(source, temporary, steps, rows[0].get('frames'))
                            if count != int(match[1]):
                                raise ValueError('MP3 gain warning did not match the independently checked silent blocks.')
                            direct_notes.append(f'{count} gain value(s) at zero belong to empty MP3 blocks; all non-silent blocks received the requested constant gain.')
                    if direct and (temporary.stat().st_size!=source.stat().st_size or non_audio_digest(temporary)!=metadata_hash):
                        raise ValueError('Original container or metadata bytes changed; export rejected.')
                else:
                    notify('Applying gain')
                    self.run(['-y','-threads',str(self.threads),'-i',source,'-map','0:a:0',
                              *(['-map_chapters','0'] if before.codec=='alac' else []),'-vn','-sn','-dn',
                              '-af',f'volume={gain:.9f}dB:precision=double','-ar',before.sample_rate,
                              *encoding,'-threads',str(self.threads),temporary])
                    notify('Preserving metadata')
                    if before.codec=='alac':
                        from .render_formats import restore_render_metadata
                        restore_render_metadata(source,temporary)
                    else:
                        restore_metadata(source,temporary)
                notify('Verifying export')
                after=self.analyze(temporary)
                if not math.isfinite(after.integrated) or not math.isfinite(after.true_peak):
                    raise ValueError('Export has no measurable loudness.')
                if (before.sample_rate,before.channels)!=(after.sample_rate,after.channels):
                    raise ValueError('Source sample rate or channel count changed; export rejected.')
                if before.codec!=after.codec:
                    raise ValueError('Source codec changed; export rejected.')
                if not (direct or opus) and before.bits!=after.bits:
                    raise ValueError('Source bit depth changed; export rejected.')
                if direct and (before.bitrate!=after.bitrate or before.bitrate_mode!=after.bitrate_mode):
                    raise ValueError('Encoded bitrate or bitrate mode changed; export rejected.')
                if (direct or opus) and abs((after.integrated-before.integrated)-gain)>0.25:
                    raise ValueError('Measured gain was inconsistent with a constant encoded gain change; export rejected.')
                overshoot=after.true_peak-settings.ceiling
                if overshoot>0:
                    if direct or opus:
                        steps-=max(1,math.ceil((overshoot+0.01)/step_db)); gain=steps*step_db
                    else:
                        gain-=overshoot+0.03
                    peak_constrained=True
                    continue
                error=settings.target-after.integrated
                # Direct encoded gain is quantized. Never replace it with a lossy
                # encode or a limiter to manufacture a closer numerical result.
                if not (direct or opus) and not peak_constrained and abs(error)>0.100001:
                    new_gain=min(gain+max(-1,min(1,error)),settings.ceiling-before.true_peak-0.02)
                    if abs(new_gain-gain)>0.005:
                        gain=new_gain; continue
                if opus:
                    warnings.append('Opus header gain changed; encoded audio packets and descriptive metadata were retained.')
                    warnings.extend(opus_notes if steps else [])
                if direct:
                    warnings.append('Direct encoded gain in 1.50515 dB steps; audio was not re-encoded. No peak limiter was used.')
                    warnings.extend(direct_notes)
                if abs(error)>0.100001:
                    warnings.append(f'Requested {settings.target:.2f} LUFS; achieved {after.integrated:.2f} LUFS. '
                                    +('Peak headroom constrained the gain; dynamics were preserved.' if peak_constrained else 'The nearest available encoded gain step was used.'))
                original=mutagen.File(source)
                if not opus and original is not None and original.tags and any(any(token in str(k).lower() for token in ['replaygain','r128','itunnorm','rva2']) for k in original.tags):
                    warnings.append('Original playback-gain metadata was retained unchanged; players using those tags may apply an additional gain adjustment.')
                if self.cancel.is_set(): raise Cancelled()
                if source_stamp(source)!=initial_stamp:
                    raise ValueError("Source changed during processing; export rejected. Analyze it again.")
                source_stat=source.stat()
                os.utime(temporary,ns=(source_stat.st_atime_ns,source_stat.st_mtime_ns))
                with destination.open('xb'): pass
                try: os.replace(temporary,destination)
                except BaseException:
                    destination.unlink(missing_ok=True); raise
                return Result(str(source),str(destination),before,after,gain,
                              'Gain capped' if peak_constrained else 'Header gain' if opus else 'Direct gain' if direct else 'Gain only',attempt,warnings,
                              {'matching':True,'limited':False,'reencoded':False,'target_lufs':settings.target,
                               'deviation_lu':after.integrated-settings.target,'target_met':abs(error)<=.100001,
                               'peak_safe_gain_capped':peak_constrained})
            raise ValueError('Could not verify a safe constant-gain export. No output was committed.')
        finally:
            temporary.unlink(missing_ok=True)
