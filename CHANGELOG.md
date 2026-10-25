# Changelog

## 1.3.0 — 2026-10-25

### Added

- A single compact, draggable main header with the full-size logo/title and toolbar; duplicate small title-bar branding has been removed.
- Centered, compact BTC address field and a fixed footer copy confirmation; copying no longer adds a scrollbar or shifts donation content.
- Seamless Windows title bar matching the app background, with minimize/maximize/restore/close controls, title-bar dragging and edge/corner resizing.

- ALAC (Apple Lossless) support for mono/stereo, 16-bit and 24-bit audio in M4A, M4B, M4R and audio MP4 files.
- ALAC constant-gain normalization, optional peak limiting, peak-only processing and waveform preview. Exports retain the ALAC codec, depth, sample rate, channel count and decoded sample count.
- ALAC tag, artwork, private metadata and chapter preservation. Other ALAC depths are rejected rather than silently reduced.
- ALAC beside FLAC in the main screen's supported-format list, with updated import filters and format help.
- Separate About, Help and Donate BTC tabs.
- Detailed Help covering Gain capped, achieved LUFS, target differences, peak headroom, encoded gain steps, processing statuses, warnings and common failures.
- Worked examples explaining why limiting-disabled processing can miss the target and why equal waveform heights do not establish equal loudness.
- Optional Bitcoin donations with the owner's address, copy-address button, themed Bitcoin icon and scannable QR code with no preset amount.
- © 2026 zerØ software, creator credit for snuffy420 and a clickable GitHub profile link in About.
- A CLI `--jobs N` option for analysis and processing, plus a reproducible mixed-format performance benchmark.

### Fixed

- About now uses the same hover highlight and border feedback as the other main toolbar buttons.

- CBR MP3 files without recognizable encoder headers no longer display UNKNOWN when their audio frames establish a constant bitrate.
- Analysis and export share MP3 bitrate-mode detection, preventing inconsistent format information between the two paths.
- MP3 frame padding is no longer confused with bitrate variation. An ordinary first audio frame is retained during detection; only identified Xing/Info/VBRI metadata frames are excluded.
- Explicit VBR/ABR encoder information is retained. Unmarked varying streams are handled as VBR because historical ABR intent cannot be recovered from frame variation alone.
- Incomplete MP3 frame scans do not falsely establish a CBR mode. Older saved reports retain their previously recorded measurements.

### Performance and reliability

- Analyze and process multiple tracks concurrently with bounded scheduling, normally up to four workers, reduced according to CPU and available memory.
- Constrain FFmpeg decoder, encoder and filter thread budgets to reduce CPU oversubscription.
- Share source measurements through a thread-safe cache. Duplicate requests reuse one measurement while unrelated tracks can proceed concurrently.
- Reserve temporary disk space before exporting and defer disk-heavy jobs when other active jobs hold the required capacity.
- Preserve source order in results and reports even when tracks finish out of order. Progress now counts finished and active tracks.
- Cancellation stops new submissions, terminates active FFmpeg work and waits for subprocess and temporary-file cleanup. Completed exports remain available.
- Isolate track failures so other tracks can continue processing.
- Restore M4A/ALAC metadata without loading or copying the complete media payload. Audio/chapter offsets remain unchanged.
- Regenerate and independently decode the donation QR during builds. The app uses the included image and needs no QR generation tools at runtime.

### Documentation and validation

- Updated README, in-app Help and actual application screenshots, including ALAC test tracks, processing explanations and donations.
- All 89 automated tests passed. Additional checks passed at 200% display scaling, through the real CLI, and inside the compiled executable, including ALAC, parallel batches, Help/donations, preview cleanup and report viewing.
- Added regression coverage for ALAC depth/rate/channels, metadata/artwork/chapters, MP3 detection, real concurrent processing, cancellation, cache invalidation, report ordering, small-window layouts and exact QR/address handling.
- A local benchmark of eight 45-second WAV/FLAC/MP3/ALAC tracks took 16.74 seconds with one worker and 4.66 seconds with four workers (about 3.6× faster). Decoded outputs were identical. Performance varies with hardware, storage, source files and settings.

Release files include the Windows portable and Python source `.7z` archives, individual SHA-256 checksum files (`.sha256` and `.sha`), and `SHA256SUMS.txt`. A clean source tree is also prepared for direct GitHub upload.
