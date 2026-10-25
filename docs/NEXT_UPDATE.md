# 1.3.0 release checklist

## MP3 bitrate-mode detection

- [x] Fix CBR MP3s displayed as `UNKNOWN` in track details and reports. When the metadata parser cannot identify the mode, inspect MPEG audio frames to distinguish CBR, VBR and ABR where reliably identifiable. Do not infer CBR from the displayed average bitrate alone.
- Reported example: `Avicii - Fade into darkness - 2Crimes remix.mp3`, 44,100 Hz stereo, displayed as `320 kb/s UNKNOWN`; user confirms the file is CBR.
- [x] Verify shared analysis/export detection and regression coverage for CBR files without recognizable encoder headers, while retaining known VBR/ABR modes.

Completed for 1.3.0. See CHANGELOG.md for the public release notes.

## Implemented for 1.3.0: About, Help and Bitcoin donations

- [x] Split About into About, Help and Donate BTC tabs.
- [x] Explain Gain capped, target differences, peak safety with limiting off, all processing methods and common warnings/failures.
- [x] Add the owner's Bitcoin address, a copy button, themed BTC icon and independently verified QR code.

- [x] Confirmed the reported Avicii file is detected as 320 kb/s CBR by inspecting its actual audio frames. Analysis and rendering now share the same detection.

## ALAC support

- [x] Add mono/stereo 16/24-bit ALAC in M4A/M4B/M4R/audio MP4 with constant gain, optional limiting and preview.
- [x] Preserve codec, depth, rate, channel count, decoded sample count and MP4 user metadata, artwork, private atoms and chapters.
- [x] Place ALAC immediately beside FLAC on the main supported-format list.
- [x] Add real ALAC codec tests and update Help/README. Unsupported ALAC depths are rejected rather than silently changed.

## Batch performance and credits

- [x] Add bounded parallel analysis/processing, serialized progress, source-order reports and cancellation cleanup.
- [x] Make analysis caching thread-safe; constrain FFmpeg thread pools and reserve temporary disk space.
- [x] Avoid whole-media memory copies when restoring MP4 metadata.
- [x] Add --jobs to the CLI and a reproducible mixed-format benchmark.
- [x] Add © 2026 zerØ software, snuffy420 and the GitHub profile link to About.

- [x] Finalize the 1.3.0 changelog in CHANGELOG.md and prepare portable/source archives and checksums.

- [x] Finalize the seamless Windows title bar, window controls and system drag/resize actions, then refresh all 1.3.0 packages and screenshots.

- [x] Consolidate the header to one large logo/title and toolbar; center and compact the BTC address and reserve a fixed footer confirmation without donation-panel scrollbars.

- [x] Match the About button hover highlight to the other toolbar buttons and refresh all 1.3.0 artifacts.
