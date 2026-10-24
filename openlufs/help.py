"""User-facing settings and processing help."""
from . import __version__
ABOUT_HTML=f"""
<h1>OpenLUFS <span style="color:#8a9b9b">{__version__}</span></h1>
<p>Adjust the loudness of mono and stereo audio files while keeping their original formats.</p>
<h2>LUFS normalization</h2>
<p>LUFS measures perceived loudness across the whole track. −10 LUFS is louder than
−12 LUFS. Enable <b>LUFS normalization</b> and enter the level you want your tracks to approach.
−12 LUFS is a practical starting point for a DJ library; −10 to −12 LUFS may need more peak
control, while −14 LUFS generally leaves more headroom. There is no universal DJ target.</p>
<h2>True-peak limiter</h2>
<p><b>Limiting is disabled by default to preserve dynamics.</b> With True-peak limiter unchecked,
OpenLUFS applies one constant gain across each track. The ceiling remains a safety limit:
if the requested gain would exceed it, less gain is applied and the track is marked
<b>Gain capped</b>. The achieved LUFS and difference from your target are shown explicitly.</p>
<p><b>A track below the target has not matched it.</b> LUFS and dBTP do not add together
to produce equal loudness. The peak-safe result preserves dynamics but may remain quieter
than other tracks. Choose a lower common target, or enable limiting if closer matching
matters more than retaining the original peak dynamics.</p>
<p>Check <b>True-peak limiter</b> to enable it. With LUFS normalization also enabled,
OpenLUFS targets ±0.1 LU and controls peaks where necessary. This can reduce punch or make
a track denser when substantial gain reduction is required. Large peak reductions can be
audible. The limiter is not promised to be transparent at every setting.</p>
<p>Turn off LUFS normalization and enable the limiter for <b>peak limiting only</b>.
This controls peaks without raising the whole track toward a LUFS target. If the source
is already under the ceiling, it is copied unchanged. At least one processing option
must be enabled to process or preview a track.</p>
<h2>Peak ceiling · dBTP</h2>
<p>True peak estimates the waveform between digital samples, where peaks can exceed the
sample values. The ceiling is a maximum, not a peak level every track must reach.
<b>−1 dBTP</b> is a useful starting point; −2 leaves more margin for later processing,
while −0.5 leaves less. Later EQ, mixing or encoding can change the peaks again.</p>
<h2>Formats and quality</h2>
<ul>
<li><b>WAV/WAVE and AIFF/AIF/AIFC:</b> retain the original supported PCM/float encoding,
bit depth, rate, channels and metadata outside the audio sample payload.</li>
<li><b>FLAC:</b> retains depth, rate, channels and user metadata. The processed samples
are compressed losslessly; stream information and seek indexes are updated as needed.</li>
<li><b>MP3:</b> direct gain avoids another encode where possible. It moves in about
1.505 dB steps, so an exact target is not always available. When waveform processing
is needed, CBR retains the original nominal bitrate. VBR retains its mode and available
quality setting; unknown quality is estimated. VBR average bitrate and size can vary.</li>
<li><b>AAC-LC:</b> raw ADTS AAC and supported M4A/M4B/M4R/audio MP4 retain their container.
Rendered AAC targets the source's measured bitrate; actual average bitrate can vary.</li>
<li><b>Ogg Opus:</b> OPUS/OGG/OGA containing Opus use direct header gain in 1/256 dB steps
where possible, or re-encode to Opus when waveform processing is required. Comments and
artwork are retained. Chained/multiplexed Ogg and Vorbis are not supported.</li>
</ul>
<p>Rendered audio uses a <b>32-bit floating-point WAV</b> intermediate. Re-encoding MP3,
AAC or Opus introduces another lossy generation; the intermediate does not make that
encode lossless. User tags and artwork are restored; audio-dependent technical metadata
is regenerated. Integer rounding, gain and limiting intentionally change samples.</p>
<p>Existing ReplayGain, R128 or Sound Check tags can cause extra playback adjustment.
They are retained rather than recalculated, apart from R128 references adjusted during
direct Opus header gain. External DJ databases are not changed. HE-AAC, ALAC, WMA,
protected audio, multichannel files and unsupported variants are rejected.</p>
<h2>Preview</h2>
<p>Select a track and use <b>Preview</b>. It processes a temporary copy with your actual
settings, then compares the decoded original and output on the <b>same linear amplitude
scale</b>. Dotted lines mark ± full scale. Full-track peak envelopes retain the minimum
and maximum decoded sample in each display bin; zoom in for finer detail.</p>
<p><b>Normal</b> uses green sample envelopes. <b>RGB</b> colors the full waveform using
red bass, green mids and blue highs. <b>3-band</b> combines blue bass, orange mids and white highs in one layered waveform per channel. The colored interiors indicate relative band energy; the outside edge retains the full waveform peaks. Crossovers
are normally 200 Hz and 2500 Hz with 8th-order filters; they adapt for very low sample rates.
These are defined signal views, not a claim to reproduce another application's colors.</p>
<p>All preview outputs and decoded/band files are removed when the preview closes,
is cancelled, or fails. Preview does not create a batch report or modify the original.
Normal cleanup cannot run after a forced process termination or power failure.</p>
<h2>Reports and workflow</h2>
<p><b>Analyze</b> measures inputs without exporting. Unchanged measurements are reused;
changed files are remeasured. <b>Process LUFS</b> writes and verifies new copies. The
Processing message stays steady while work is underway. Cancel appears during processing.</p>
<p><b>Open report</b> displays a readable batch panel with achieved LUFS, peaks, processing
methods and any target shortfalls. You can open previous reports and export CSV, readable
HTML or report data. Peak reduction is an estimate, not an instrumented gain-reduction trace.</p>
<p>Settings, output path, preview style and window size are remembered. Originals and
existing exports are never overwritten. First-use values are −12 LUFS and −1 dBTP, with
LUFS normalization enabled and limiting disabled. Your saved values take precedence.</p>
<p>OpenLUFS uses BS.1770-based measurement, linked-channel lookahead limiting with 4×
oversampling, 5 ms lookahead, 80 ms release and disabled automatic makeup gain. Every final
export is measured. No tempo, pitch or EQ changes are applied.</p>
<p><a href="https://www.itu.int/rec/R-REC-BS.1770/en">ITU-R BS.1770</a> ·
<a href="https://ffmpeg.org/ffmpeg-filters.html#alimiter">FFmpeg limiter documentation</a><br>
Python · Qt / PyQt6 · FFmpeg · mp3rgain · NumPy · Mutagen<br>GPL-3.0-or-later. See the supplied license and third-party notices.</p>
"""
