# Processing and validation

LUFS normalization is enabled and limiting is disabled by default. The two controls are independent. The desktop and CLI can normalize LUFS with a peak-safe gain cap, normalize with limiting, or apply peak limiting without a loudness boost. Enabling limiting allows the matching render path; disabling it preserves constant gain and reports target shortfalls explicitly.

## Source analysis

`Engine.analyze` uses FFmpeg loudnorm solely as a meter; its rendered output is discarded. The source cache records file identity, size and nanosecond timestamps. Unchanged inputs reuse measured loudness, true peak and format properties. Changed sources are remeasured. Every export is measured independently. Raw ADTS duration is counted from its frame sample counts rather than estimated from bitrate.

## Matching path

`matching.py` first checks whether preserving constant/direct gain can meet ±0.1 LU and the chosen true-peak ceiling. It uses that path when possible. Otherwise it decodes once to PCM float32 WAV, retaining sample rate and channels and preserving decoded peaks above full scale. Every candidate render reads that same float source.

Gain is followed, only when needed, by 4× resampling, FFmpeg's linked-channel alimiter with 5 ms lookahead and 80 ms release, disabled automatic output leveling, compensated latency, and resampling to the original rate. Peak limiting changes dynamics. The app does not claim a best-in-class or universally transparent limiter; listening tests remain necessary.

The final encoding is measured. Loudness error adjusts input gain; peak overshoot adjusts the internal limiter ceiling independently. No candidate is used as the input to another encode. Exports must meet ±0.1 LU and the requested ceiling; retries are bounded and unverified outputs are rejected. Reports distinguish direct gain, limiting, and additional lossy encoding. Peak reduction is estimated from the source peak, input gain and limiter ceiling; it is not an instrumented gain-reduction trace.

## Format retention

PCM WAV/AIFF exports retain their original storage codec/depth, rate, channels and container bytes outside the sample payload. FLAC retains original non-technical blocks and updates technical stream information and seeks. Matching can alter samples and introduce integer rounding.

MP3 preserves raw user-tag regions and generates fresh stream delay/padding headers when re-encoded. Known CBR bitrate, ABR target and VBR quality/mode are retained where recoverable. Files without explicit bitrate mode are inspected at frame level. Unknown VBR quality is estimated and reported. Raw AAC user tags are retained. MP4 user metadata atoms and tags are restored while new audio-dependent tables remain in use. Opus descriptive comments/artwork are restored with regenerated stream headers.

Re-encoding MP3/AAC/Opus introduces a lossy generation. A float WAV intermediate does not make that encoding lossless. VBR averages and AAC/Opus averages can differ from source measurements even when matching encoder targets. Source extension, codec, rate and channels are checked; PCM storage depth and CBR MP3 bitrate are checked where applicable. Source changes, cancellation and destination collisions prevent commit.

## Preserving path

Direct MP3/AAC gain uses approximately 1.50515 dB steps; Opus uses its Q7.8 header field in 1/256 dB steps. Peak constraints can cap gain. WAV/AIFF/FLAC use continuous fixed gain. No limiter or lossy transcode fallback is used when the limiter is disabled.

MP3 gain-floor warnings are accepted only after independent side-information checks establish that every saturated value belongs to an empty granule with zero data length and zero big_values. Non-silent saturation remains rejected. Opus direct gain leaves encoded packets unchanged and updates R128 references as required by RFC 7845.

## Validation

Tests exercise actual codecs and generated transient signals, source protection, cached measurements, metadata/private tags, storage depth, sample count, decoded loudness/peaks and quiet-passage behavior. GUI tests cover typed settings, persistence, resizing, scaling and worker workflows. Representative user tracks are also checked on isolated copies; the MP3 previously capped at −16.07 LUFS reached −10.06 LUFS / −0.71 dBTP at 320 kb/s with matching enabled.

The archived original script is `norm-original.py.txt`. The 1.3.0 release build was checked on Windows 10, including the compiled preview/report panels and temporary-file cleanup.

References: [BS.1770](https://www.itu.int/rec/R-REC-BS.1770/en), [FFmpeg alimiter](https://ffmpeg.org/ffmpeg-filters.html#alimiter), [mp3rgain](https://github.com/M-Igashi/mp3rgain/tree/v3.12.1), [Opus mapping](https://www.rfc-editor.org/rfc/rfc7845.html).

## Preview and reports

The waveform preview processes an actual temporary output, decodes original/output float32 streams, and uses per-display-bin minima/maxima to retain every sample peak. Both panels share a linear amplitude scale. RGB maps relative band power to red/green/blue; 3-band layers blue/orange/white within the full-band peak envelope, with one lane per channel. Nested layer fractions are the square root of cumulative mid/high power shares. Neither mode rescales the waveform. Both use 8th-order 200/2500 Hz crossovers (adapted at low rates). These are defined signal views rather than vendor-specific waveform claims. Preview maps are closed before all temporary files are removed on normal close, cancellation or failure. Forced termination can prevent cleanup.

Reports remain JSON data on disk and open in a themed parser/viewer with previous-report loading and CSV/HTML/JSON export. Target differences are displayed explicitly. Source measurements and user settings are retained where valid; output verification is never skipped.

## About, Help and donations

AboutDialog separates application credits, detailed processing help and optional Bitcoin donations. Help covers statuses, headroom, target differences, codec steps and failures. Donation address copying uses the owner's exact address. The static QR encodes a Bitcoin URI with no amount and is decoded independently during builds. QR generation/decoding packages are build-time only; runtime displays the PNG. The donation tab uses a fixed, responsive panel with a centered single-line address and an always-reserved footer confirmation. Optional explanatory copy is hidden on compact displays; the QR resizes while retaining its quiet zone. The primary Windows header contains one set of branding, toolbar controls and caption actions; system dragging is available from its background or branding.

## MP3 bitrate modes

Analysis and encoding profiles share `mp3.bitrate_properties`. Explicit CBR/VBR/ABR encoder metadata takes precedence. Missing modes trigger a complete frame-header scan: nominal bitrates, rather than frame lengths affected by padding, distinguish constant and varying streams. Only an identified Xing/Info/VBRI metadata frame is excluded; the first ordinary audio frame participates. Truncation cannot establish a CBR mode. Unmarked variable streams are handled as VBR because historical ABR intent cannot be reconstructed from frame variation. Older reports keep their recorded measurements.

## ALAC

Supported ALAC is mono/stereo, 16 or 24 bits, in the existing MP4 extension set. Analysis reads ALAC storage depth from the MP4 codec metadata. Constant gain renders through the ALAC encoder with the original sample format/depth and uses the same MP4 metadata restoration as matching renders. Limiter-enabled processing treats ALAC as a lossless codec, verifies depth and retains its sample count. Explicit chapter mapping preserves the chapter track, and raw user metadata/artwork/private atoms are retained. Unsupported source depths are rejected. Lossless output bitrate is not forced to the input compressed bitrate.

## Parallel batches

A bounded ThreadPoolExecutor schedules at most the active worker count, with serialized callbacks on the coordinator thread and results assembled in source order. Defaults cap at four tracks, reserve CPU headroom and budget 512 MiB per worker against available RAM. Explicit CLI jobs remain constrained by resource safeguards. Per-source cache locks deduplicate metering while allowing other sources to proceed; clear/discard cannot restore an in-flight invalidated entry. Shared cancellation stops new submission and joins all active cleanup before reporting completion. FFmpeg filter pools and decoder threads are constrained per job. Temporary-space reservations serialize disk-heavy jobs when capacity is insufficient.

MP4 restoration reads only atom headers and movie/user metadata, turns the rendered moov into a free atom in place, then appends restored metadata. The media payload and chunk offsets remain unchanged. This avoids allocating/copying complete M4A audio files for each concurrent job. Generated mixed-format benchmarks compare serial and parallel runs and check decoded audio hashes for equality.
