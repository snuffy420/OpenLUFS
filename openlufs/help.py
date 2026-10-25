"""User-facing settings and processing help."""
from . import __version__
HELP_HTML=f"""
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
<li><b>ALAC (Apple Lossless):</b> 16-bit and 24-bit ALAC in M4A/M4B/M4R/audio MP4 retains
its codec, depth, sample rate, channels and supported tags, artwork, private fields and
chapters. Constant gain, limiting and preview are supported. Output compression is lossless;
bitrate and size can vary. Gain, limiting and sample rounding intentionally change the audio.
Other ALAC depths are rejected rather than reduced.</li>
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
direct Opus header gain. External DJ databases are not changed. HE-AAC, WMA,
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
<h2>Parallel processing</h2>
<p>Multiple tracks are analyzed and processed concurrently. The worker count is selected
automatically, normally up to four, and reduced when CPU or available memory is limited.
Each audio job has a limited thread budget. The app checks temporary disk space before
rendering. Progress counts finished and active tracks; files may finish out of order,
but the report keeps their original order. Cancelling stops new jobs and waits for active
subprocesses and temporary files to be cleaned up. Finished exports remain.</p>
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


ABOUT_HTML=f"""
<h1>OpenLUFS <span style="color:#8a9b9b">{__version__}</span></h1>
<p>Audio loudness normalization with optional true-peak limiting, waveform comparisons
and batch reports. Exports retain their supported source formats.</p>
<p>Use <b>Help</b> for settings, processing results, format support and troubleshooting.
Use <b>Donate BTC</b> to support development.</p>
<h2>Measurement and processing</h2>
<p>BS.1770-based integrated LUFS measurement through FFmpeg. LUFS normalization and
true-peak limiting can be enabled independently. No tempo or pitch changes are applied.</p>
<h2>zerØ software</h2>
<p>© 2026 zerØ software<br>Created by <b>snuffy420</b><br>
<a href="https://github.com/snuffy420">github.com/snuffy420</a></p>
<h2>License and credits</h2>
<p>GPL-3.0-or-later. See the supplied LICENSE and THIRD_PARTY_NOTICES.md files.</p>
<p>Python · Qt / PyQt6 · FFmpeg · mp3rgain · NumPy · Mutagen</p>
<p><a href="https://www.itu.int/rec/R-REC-BS.1770/en">ITU-R BS.1770</a> ·
<a href="https://ffmpeg.org/ffmpeg-filters.html#alimiter">FFmpeg limiter documentation</a></p>
"""

RESULTS_HELP_HTML="""
<h1>Understanding your results</h1>
<h2>Why did my track miss the LUFS target?</h2>
<p><b>With the limiter off, the peak ceiling still restricts gain.</b> OpenLUFS applies
one gain adjustment to the entire track. If the gain needed for your target would put
peaks above the ceiling, less gain is used. The app does not silently clip the file or
force the number to match.</p>
<p><b>Gain capped means the target was constrained by peak headroom.</b> It does not mean
the track was limited, that the peaks were crushed, or that the track matches the rest
of your library. Read the achieved LUFS and target difference in Track details or the report.</p>
<h2>Example: −11.82 LUFS input, −10 LUFS target</h2>
<p>If the input peak is +1.00 dBTP, reaching −10 LUFS needs +1.82 dB of gain.
The peak would rise to about +2.82 dBTP. With a −0.2 dBTP ceiling and the limiter off,
the app instead lowers the track about 1.22 dB, including its small safety margin.
The result is about −13.04 LUFS and −0.22 dBTP. The dynamics are preserved, but the target
is not matched.</p>
<p>A track at −7 LUFS can reach −10 LUFS more easily because its required gain is
−3 dB: turning it down lowers the peaks too. A small upward change can be impossible
without limiting if the input peaks are already too high. Available peak headroom,
rather than the size of the LUFS difference alone, determines what constant gain can do.</p>
<h2>What are my choices?</h2>
<ul><li><b>Preserve dynamics:</b> leave the limiter off and accept any reported shortfall,
or choose a lower common target that the tracks can reach safely.</li>
<li><b>Prioritize target matching:</b> enable LUFS normalization and the true-peak limiter.
OpenLUFS aims for ±0.1 LU and the ceiling. Peak reduction can change punch and dynamics;
preview and listen, especially when the reported reduction is large.</li>
<li><b>Control peaks only:</b> uncheck LUFS normalization and check True-peak limiter.
This does not raise the track toward a LUFS target.</li></ul>
<p>At least one option must be checked to process or preview. Turning off the limiter
does not authorize clipping or remove the safety ceiling.</p>
<h2>Why do −13 and −10 LUFS waveforms look equally tall?</h2>
<p>Waveform height shows sample amplitude, not whole-track perceived loudness. Two tracks
can have similar peak heights but different sustained energy. If measured at −13 and
−10 LUFS, they differ by 3 LU and have not matched. LUFS and dBTP cannot be added together.
OpenLUFS processes tracks independently; it does not match waveform heights to other tracks.
Its preview uses a shared amplitude scale for original and processed audio.</p>
<h2>Track statuses and processing methods</h2>
<table cellpadding="7" cellspacing="0" border="1">
<tr><th>Message</th><th>Meaning</th></tr>
<tr><td>Queued</td><td>Waiting for analysis or processing.</td></tr>
<tr><td>Measuring</td><td>Reading source loudness and audio properties.</td></tr>
<tr><td>Using analysis</td><td>Reusing a measurement of the unchanged source.</td></tr>
<tr><td>Analyzed</td><td>Source measurement is ready; no output has been created by analysis.</td></tr>
<tr><td>Processing</td><td>Preparing, rendering, preserving metadata or verifying an export. It can include bounded internal retries. Each retry starts from the original float intermediate, not an earlier encoded output.</td></tr>
<tr><td>Gain only</td><td>A constant gain adjustment was sufficient. No peak limiting was used.</td></tr>
<tr><td>Direct gain</td><td>MP3/AAC encoded gain changed without another encode. Steps are approximately 1.505 dB, so the exact LUFS target may be unavailable.</td></tr>
<tr><td>Header gain</td><td>Opus header gain changed in 1/256 dB steps; encoded audio packets were retained.</td></tr>
<tr><td>Gain capped</td><td>Peak headroom constrained the gain. No limiter was used. The achieved LUFS may be below the requested target.</td></tr>
<tr><td>Peak limited</td><td>Waveform peaks were reduced where necessary. Check achieved LUFS and peaks; the status alone does not mean LUFS normalization was enabled.</td></tr>
<tr><td>Limited + encoded</td><td>Peaks were limited and the compressed audio was re-encoded. Another lossy generation was introduced.</td></tr>
<tr><td>Re-encoded</td><td>The source format was rendered again without peak limiting. Compressed lossy formats incur another lossy generation.</td></tr>
<tr><td>Unchanged</td><td>Peak-only processing found the source already below the ceiling and copied it unchanged.</td></tr>
<tr><td>Complete</td><td>Processing finished; the track row normally replaces this stage with its processing method.</td></tr>
<tr><td>Cancelled</td><td>The current operation was stopped. Earlier completed exports remain; unfinished temporary output is removed.</td></tr>
<tr><td>Failed</td><td>The operation did not succeed. Read Track details or the batch report for the specific cause; do not treat the track as successfully normalized.</td></tr>
</table>
<h2>Numbers, notes and warnings</h2>
<ul>
<li><b>Input / output LUFS:</b> measured whole-track loudness before and after processing.
A less negative number is louder. Integrated loudness does not guarantee identical levels
in every intro, breakdown or mix transition.</li>
<li><b>Peak dBTP:</b> the source true peak after analysis, or the verified output true peak
after export. The ceiling is a maximum; peaks do not need to reach it.</li>
<li><b>LRA:</b> loudness range, in LU. It describes loudness variation, not the maximum sample peak.</li>
<li><b>Target difference / not matched:</b> output LUFS minus target LUFS. −3 LU means
3 LU below target; +0.5 LU means 0.5 LU above it. A difference within ±0.1 LU is treated
as matched when LUFS normalization is enabled. Peak-only processing has no LUFS target.</li>
<li><b>Gain / input gain:</b> the fixed adjustment applied before any optional limiting.
With limiting, this number is not the total change at every sample.</li>
<li><b>Estimated peak reduction:</b> an estimate of the reduction needed to control peaks,
not a recorded time-varying gain-reduction trace. Large values warrant a listening check.</li>
<li><b>Encoded gain steps:</b> MP3/AAC direct gain can miss the exact target even with enough
headroom because available gain steps are coarse. Opus steps are much smaller.</li>
<li><b>UNKNOWN bitrate mode:</b> the mode could not be established from metadata or a complete frame scan, or the report predates the detection fix. It does
not mean the output becomes another format or bitrate. Direct gain retains the stream. Analysis and export both inspect frames when encoder information is missing: constant frame bitrates are shown as CBR, varying rates as VBR. Known VBR/ABR encoder modes are retained.
A varying frame bitrate alone cannot reliably distinguish VBR from ABR.</li>
<li><b>Re-encoded / quality estimated:</b> original encoder settings were unavailable or
waveform processing was needed. MP3 VBR quality can be estimated; actual average bitrate
and file size can change. A 32-bit float intermediate does not make lossy encoding lossless.</li>
<li><b>Playback-gain tags retained:</b> a player using ReplayGain, R128 or Sound Check may
apply another volume adjustment. Those tags are not a guarantee of the new output level.</li>
<li><b>Unmeasurable / —:</b> no finite measurement or completed result is available in that
field. Silence and audio below the loudness gate cannot be normalized.</li>
</ul>
<h2>Common failures and what to check</h2>
<ul>
<li><b>No decodable audio / unsupported encoding:</b> the extension alone is not enough.
Check the supported formats below. Protected files, multichannel audio and unsupported
codec variants are rejected rather than silently converted.</li>
<li><b>Silence / below the loudness gate / too short:</b> a measurable integrated loudness
is required. Audio must be at least 400 ms long.</li>
<li><b>Gain bounds / unsupported encoded gain:</b> this file cannot safely use the requested
direct encoded gain. Limiter-enabled processing can try a rendered path; no guarantee is
made for malformed or unsupported files.</li>
<li><b>Source changed:</b> the input changed after measurement or during processing.
Analyze the current file again and retry.</li>
<li><b>Export rejected / could not verify:</b> output properties, metadata, target or peak
checks failed. The failed candidate is not published as a successful export. Read the
specific report error before retrying.</li>
<li><b>Output exists / output must be a new file:</b> originals and earlier exports are
protected. Choose a new destination; do not overwrite the source.</li>
<li><b>Missing tool / permission / disk space / preview error:</b> confirm the installation,
write access and available storage. Preview may require substantial temporary space.
Its files are removed after normal close, cancellation or failure.</li>
</ul>
"""
HELP_HTML=RESULTS_HELP_HTML+HELP_HTML
