# Build with: python -m PyInstaller --clean --noconfirm OpenLUFS.spec
from pathlib import Path
root = Path(SPECPATH)
import os, sys, PyQt6
# Keep unrelated native libraries on the host PATH out of dependency discovery.
# Windows 10 supplies its own UCRT/API-set DLLs; old copies can break Qt.
windows = Path(os.environ.get("SystemRoot", "C:/Windows"))
qt_bin = Path(PyQt6.__file__).parent / "Qt6/bin"
os.environ["PATH"] = os.pathsep.join(map(str, [windows/"System32", windows,
    Path(sys.executable).parent, Path(sys.base_prefix), qt_bin]))
a = Analysis([str(root/"norm.py")], pathex=[str(root)],
    binaries=[(str(root/"vendor/ffmpeg.exe"), "vendor"), (str(root/"vendor/mp3rgain.exe"), "vendor")],
    datas=[(str(root/"assets"), "assets"), (str(root/"licenses"), "licenses"),
           (str(root/"LICENSE"), "."), (str(root/"THIRD_PARTY_NOTICES.md"), "."),
           (str(root/"vendor/manifest.json"), "vendor"), (str(root/"vendor/mp3rgain-manifest.json"), "vendor")],
    hiddenimports=[], hookspath=[], runtime_hooks=[],
    excludes=["PyQt5", "PySide2", "PySide6", "scipy", "PIL", "tkinter", "librosa", "soundfile", "matplotlib", "torch", "pandas"],
    noarchive=False)
# Qt needs a newer MSVC runtime than some Python 3.12 installations bundle.
# Use Qt's backwards-compatible runtime consistently, including at extraction root.
import PyQt6
qt_bin = Path(PyQt6.__file__).parent / "Qt6/bin"
for runtime in ["VCRUNTIME140.dll", "VCRUNTIME140_1.dll"]:
    newer = qt_bin / runtime
    if newer.is_file():
        a.binaries = [(dest, str(newer) if Path(dest).name.lower() == runtime.lower() else src, kind)
                      for dest, src, kind in a.binaries]
a.binaries = [(dest, src, kind) for dest, src, kind in a.binaries
              if not Path(dest).name.lower().startswith("api-ms-win-")
              and Path(dest).name.lower() != "ucrtbase.dll"]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="OpenLUFS", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    icon=str(root/"assets/openlufs.ico"), version=str(root/"tools/version_info.txt"))
