"""Verified loudness matching with selective oversampled peak limiting.

Every render starts with the same decoded 32-bit float source. Retry gain and
peak margin are independent; no intermediate MP3/AAC/Opus is re-encoded again.
"""
from dataclasses import replace
import math
import os
from pathlib import Path
import tempfile
import shutil
from .analysis_cache import source_stamp
from .models import Result, MP4_EXTENSIONS, OPUS_EXTENSIONS
from .render_formats import encoding_profile, restore_render_metadata
from .ogg import inspect_opus
import mutagen

TOLERANCE=0.100001


def publish(engine,source,temporary,destination,stamp):
    if engine.cancel.is_set():
        from .engine import Cancelled
        raise Cancelled()
    if source_stamp(source)!=stamp:
        raise ValueError('Source changed during processing; export rejected. Analyze it again.')
    stat=source.stat();os.utime(temporary,ns=(stat.st_atime_ns,stat.st_mtime_ns))
    with destination.open('xb'):pass
    try:os.replace(temporary,destination)
    except BaseException:
        destination.unlink(missing_ok=True);raise


def normalize_matching(engine,source,destination,settings,before,notify):
    destination.parent.mkdir(parents=True,exist_ok=True)
    stamp=source_stamp(source)
    gain=settings.target-before.integrated if settings.normalize_lufs else 0
    ext=source.suffix.lower()
    encoded=before.codec in {'mp3','aac','opus'}
    direct_possible=not encoded
    if encoded:
        step=1/256 if before.codec=='opus' else 20*math.log10(2**.25)
        steps=min(round(gain/step),math.floor((settings.ceiling-before.true_peak)/step))
        direct_possible=abs(before.integrated+steps*step-settings.target)<=TOLERANCE
    else:
        direct_possible=before.true_peak+gain<=settings.ceiling-.02
    with tempfile.TemporaryDirectory(prefix='.openlufs-match-',dir=destination.parent) as folder:
        work=Path(folder)
        candidate=work/('output'+source.suffix)
        if not settings.normalize_lufs and before.true_peak<=settings.ceiling:
            shutil.copyfile(source,candidate)
            publish(engine,source,candidate,destination,stamp)
            return Result(str(source),str(destination),before,before,0,'Unchanged',0,
                          ['Peaks were already below the ceiling; LUFS normalization was disabled.'],
                          {'matching':False,'limited':False,'reencoded':False})
        if direct_possible and settings.normalize_lufs:
            try:
                result=engine.normalize(source,candidate,replace(settings,allow_limiter=False),before,notify)
            except ValueError:
                # An encoded-gain boundary can still require waveform processing.
                if not encoded:raise
                candidate.unlink(missing_ok=True)
            else:
                if abs(result.after.integrated-settings.target)<=TOLERANCE and result.after.true_peak<=settings.ceiling:
                    publish(engine,source,candidate,destination,stamp)
                    result.destination=str(destination)
                    result.processing={'matching':True,'limited':False,'reencoded':False,'target_tolerance_lu':.1}
                    return result
                candidate.unlink(missing_ok=True)
        encoding,profile,notes=encoding_profile(source,before,engine)
        notify('Decoding to 32-bit float')
        decoded=work/'source-float32.wav'
        engine.run(['-y','-i',source,'-map','0:a:0','-vn','-sn','-dn','-map_metadata','-1',
                    '-c:a','pcm_f32le','-ar',before.sample_rate,'-rf64','auto',decoded])
        limited=before.true_peak+gain>settings.ceiling-.02
        margin=.3 if encoded else .05
        internal_ceiling=settings.ceiling-margin
        # 4x processing resolves intersample peaks. The final decoded export is
        # still measured because downsampling and lossy encoders can add peaks.
        oversample=before.sample_rate*4
        used_limiter=False
        for attempt in range(1,11):
            notify('Limiting peaks' if limited else 'Matching loudness')
            filters=[f'volume={gain:.12f}dB:precision=double']
            if limited:
                filters.extend([f'aresample={oversample}:filter_size=64',
                    f'alimiter=limit={10**(internal_ceiling/20):.12f}:attack=5:release=80:level=false:latency=true',
                    f'aresample={before.sample_rate}:filter_size=64'])
                used_limiter=True
            engine.run(['-y','-threads',str(engine.threads),'-i',decoded,*(['-i',source] if ext in MP4_EXTENSIONS else []),'-map','0:a:0',
                        *(['-map_chapters','1'] if ext in MP4_EXTENSIONS else []),'-vn','-sn','-dn','-map_metadata','-1',
                        '-af',','.join(filters),'-ar',before.sample_rate,*encoding,'-threads',str(engine.threads),candidate])
            notify('Preserving metadata')
            restore_render_metadata(source,candidate)
            notify('Verifying export')
            after=engine.analyze(candidate)
            if not math.isfinite(after.integrated) or not math.isfinite(after.true_peak):
                raise ValueError('Matching export has no measurable loudness.')
            if (before.codec,before.sample_rate,before.channels)!=(after.codec,after.sample_rate,after.channels):
                raise ValueError('Matching changed source codec, sample rate or channel count; export rejected.')
            if not encoded and before.bits!=after.bits:
                raise ValueError('Matching changed original PCM storage depth; export rejected.')
            if ext=='.mp3' and profile.get('mode')=='CBR' and after.bitrate!=profile['target_bitrate']:
                raise ValueError('CBR MP3 output did not retain the selected source bitrate.')
            # ADTS has no sample-accurate end trim; it can add one AAC frame.
            duration_tolerance=max(.06,2048/before.sample_rate)
            if abs(after.duration-before.duration)>duration_tolerance:
                raise ValueError('Matching changed track duration beyond encoder padding tolerance; export rejected.')
            error=settings.target-after.integrated if settings.normalize_lufs else 0
            overshoot=after.true_peak-settings.ceiling
            if abs(error)<=TOLERANCE and overshoot<=0:
                warnings=list(notes)
                if encoded:
                    warnings.append('Re-encoded once from a 32-bit floating-point WAV intermediate. This introduces a new lossy encoding generation; it is not lossless.')
                if used_limiter:
                    warnings.append('Oversampled, stereo-linked lookahead limiting was required. Peak dynamics changed; quieter passages are left uncompressed when below the limiter threshold.')
                else:
                    warnings.append('Continuous constant gain matched the target without peak limiting.')
                if used_limiter:
                    reduction=max(0,before.true_peak+gain-internal_ceiling)
                    warnings.append(f'Estimated maximum peak reduction: {reduction:.2f} dB.'
                                    +(' Substantial reduction was needed; review the transients by listening.' if reduction>=3 else ''))
                original=mutagen.File(source)
                if original is not None and original.tags and any(any(t in str(k).lower() for t in ['replaygain','r128','itunnorm','rva2']) for k in original.tags):
                    warnings.append('Original playback-gain tags were retained; players using them may apply an additional volume adjustment. They were not recalculated for the processed audio.')
                processing={'matching':settings.normalize_lufs,'limited':used_limiter,'reencoded':encoded,
                            'target_lufs':settings.target if settings.normalize_lufs else None,
                            'deviation_lu':after.integrated-settings.target if settings.normalize_lufs else None,
                            'target_met':abs(error)<=TOLERANCE if settings.normalize_lufs else None,
                            'intermediate':'32-bit float WAV','target_tolerance_lu':.1,
                            'encoding':profile,'pre_limiter_gain_db':gain}
                if used_limiter:
                    processing['limiter']={'lookahead_ms':5,'release_ms':80,'oversample_factor':4,
                        'automatic_makeup':False,'internal_ceiling_dbtp':internal_ceiling,
                        'estimated_peak_reduction_db':max(0,before.true_peak+gain-internal_ceiling)}
                publish(engine,source,candidate,destination,stamp)
                return Result(str(source),str(destination),before,after,gain,
                              'Limited + encoded' if used_limiter and encoded else 'Peak limited' if used_limiter else 'Re-encoded',
                              attempt,warnings,processing)
            # Always render from the original float WAV. Never process a prior
            # encoded result; only its meter readings guide the next attempt.
            gain+=max(-6,min(6,error))
            if overshoot>0:
                limited=True
                internal_ceiling-=overshoot+.08
            if internal_ceiling < -23:
                break
        raise ValueError('Could not verify both target loudness (±0.1 LU) and the peak ceiling; no output was committed.')
