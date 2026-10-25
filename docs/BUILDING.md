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

The build regenerates the donation QR and checks its exact payload with an independent decoder, tests the source, renders current screenshots from generated audio, compiles `dist/OpenLUFS.exe`, runs the frozen self-test, and creates:

- `releases/OpenLUFS-1.3.0-windows-x64-setup.exe`
- `releases/OpenLUFS-1.3.0-windows-x64-portable.7z`
- `releases/OpenLUFS-1.3.0-source.7z`
- An accompanying `.sha256` and `.sha` file for each archive, plus `SHA256SUMS.txt`.
- `GitHub/OpenLUFS-1.3.0/`, containing the clean project tree for repository upload. A numbered folder is used if one already exists.

The source archive includes Windows processing executables. The GitHub folder includes their pinned manifests and fetch scripts; generated binaries belong in Releases rather than Git history. Virtual environments, personal settings, test audio, temporary files and compiled output are excluded from the upload folder.

Verify an archive with `Get-FileHash PATH_TO_ARCHIVE -Algorithm SHA256` and compare it with its checksum file. Files ending in `.sha` contain SHA-256 hashes and match the corresponding `.sha256` file.

The Windows workflow produces build artifacts and does not publish a release. See [PUBLISHING.md](PUBLISHING.md) for repository/release steps and dependency redistribution notes.

Donation QR generation uses qrcode, Pillow and zxing-cpp only on the build machine. The application displays the included PNG and does not require these QR tools at runtime.

The installer uses a pinned Inno Setup 7 x64 compiler prepared automatically in `.build-tools/InnoSetup7`. It is a build tool, not a runtime dependency. `OPENLUFS_ISCC` can point to an existing compatible ISCC.exe. The installer includes the exact verified portable payload and a marker selecting per-user preferences. It defaults to Program Files, registers an uninstaller and offers an unchecked desktop-shortcut task.

Run `python tools/check_installer.py releases/OpenLUFS-1.3.0-windows-x64-setup.exe` to install a test copy into an isolated project folder using the per-user override, check Installed Apps registration and frozen diagnostics, then uninstall it. The check refuses to overwrite an existing per-user OpenLUFS installation. Production defaults still request elevation for Program Files.

Mac/Linux source launchers are `setup.sh` and `run.sh`; detailed user instructions are in INSTALLATION.md. Shell syntax and platform selection are tested here, but native Mac/Linux GUI/audio validation is not claimed.
