# Third-party software

OpenLUFS application code and original graphics are licensed GPL-3.0-or-later. Third-party software retains its own copyright and license terms. Full license texts available in the build environment are copied to `licenses/` and included in the portable archive.

| Component | Bundled/tested version | License and source |
| --- | --- | --- |
| Python | 3.12.6 | PSF license; https://www.python.org/downloads/source/ |
| PyQt6 | 6.11.0 | GPLv3; https://www.riverbankcomputing.com/software/pyqt/download |
| Qt runtime | 6.11.2 | LGPLv3/GPL; https://download.qt.io/archive/qt/ |
| PyQt6-sip | 13.12.0 | SIP license; see included license and https://www.riverbankcomputing.com/software/sip/download |
| Mutagen | 1.48.1 | GPL-2.0-or-later; https://github.com/quodlibet/mutagen |
| FFmpeg | 7.1 Gyan essentials | GPLv3-enabled build; https://github.com/FFmpeg/FFmpeg/tree/n7.1 |
| mp3rgain | 3.12.1 | MIT; https://github.com/M-Igashi/mp3rgain/tree/v3.12.1 |
| PyInstaller runtime | 6.18.0 | GPL with bootloader exception; https://github.com/pyinstaller/pyinstaller |

FFmpeg is bundled as an unmodified separate executable extracted from the imageio-ffmpeg 0.6.0 Windows x86_64 wheel. Its original build is from https://www.gyan.dev/ffmpeg/builds/. The exact binary hash, version and configure flags are in `vendor/manifest.json` (also included inside the executable). FFmpeg includes external libraries with their own licenses. See the configure flags and upstream build information for their provenance; the application does not claim copyright in those components.

The bundled FFmpeg contains filters and codecs beyond those used by OpenLUFS. OpenLUFS does not invoke tempo-stretching filters.

Pillow and imageio-ffmpeg are build-time tools. Pillow creates the original OpenLUFS graphics; imageio-ffmpeg supplies the Windows FFmpeg executable. They are not imported by the application at runtime.

The source archive contains OpenLUFS source and build scripts plus the FFmpeg executable. It is not a complete corresponding-source archive for every third-party binary. Anyone publishing the executable must supply any corresponding-source and build materials required by the applicable licenses. See docs/PUBLISHING.md.


Direct encoded MP3/AAC gain uses the unmodified mp3rgain executable. Its exact checksum, download URL and source tag are recorded in vendor/mp3rgain-manifest.json. The upstream tool is instructed not to add or rewrite analysis/undo tags. Its MIT license is included in licenses/mp3rgain-LICENSE.
NumPy 2.3.5 is bundled for sample-derived waveform envelopes and energy measurements. Its BSD license and bundled-library notices are in licenses/numpy-LICENSE.txt; source: https://github.com/numpy/numpy/tree/v2.3.5.
