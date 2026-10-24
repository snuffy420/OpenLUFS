# Building from source

These instructions are for developers rebuilding OpenLUFS. The portable executable already includes its runtime dependencies.

Use Windows x64 and Python 3.11 or later (the release environment uses Python 3.12). Install 7-Zip on the build machine for archive creation; it is not an application runtime dependency.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools\fetch_ffmpeg.py
.\.venv\Scripts\python.exe tools\fetch_mp3rgain.py
.\.venv\Scripts\python.exe tools\build.py
```

The build tests the source, renders current screenshots from generated audio, compiles `dist/OpenLUFS.exe`, runs the frozen self-test, and creates:

- `releases/OpenLUFS-1.2.1-windows-x64-portable.7z`
- `releases/OpenLUFS-1.2.1-source.7z`
- An accompanying `.sha256` and `.sha` file for each archive, plus `SHA256SUMS.txt`.
- `GitHub/OpenLUFS-1.2.1/`, containing the clean project tree for repository upload. A numbered folder is used if one already exists.

The source archive includes Windows processing executables. The GitHub folder includes their pinned manifests and fetch scripts; generated binaries belong in Releases rather than Git history. Virtual environments, personal settings, test audio, temporary files and compiled output are excluded from the upload folder.

Verify an archive with `Get-FileHash PATH_TO_ARCHIVE -Algorithm SHA256` and compare it with its checksum file. Files ending in `.sha` contain SHA-256 hashes and match the corresponding `.sha256` file.

The Windows workflow produces build artifacts and does not publish a release. See [PUBLISHING.md](PUBLISHING.md) for repository/release steps and dependency redistribution notes.
