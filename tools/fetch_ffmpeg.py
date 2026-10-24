"""Extract the pinned imageio-ffmpeg binary; no system installation is needed."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
def main():
    try:
        import imageio_ffmpeg
    except ImportError:
        raise SystemExit("Install requirements-build.txt first, or provide vendor/ffmpeg.exe yourself.")
    src=Path(imageio_ffmpeg.get_ffmpeg_exe())
    destination=ROOT/"vendor"/("ffmpeg.exe" if sys.platform=="win32" else "ffmpeg")
    destination.parent.mkdir(exist_ok=True)
    expected = json.loads((ROOT/"vendor/manifest.json").read_text(encoding="utf-8")) if (ROOT/"vendor/manifest.json").exists() else {}
    digest=hashlib.sha256(src.read_bytes()).hexdigest()
    if sys.platform=="win32" and expected.get("sha256") and digest!=expected["sha256"]:
        raise SystemExit("Pinned FFmpeg hash differs. Review the binary before updating the manifest.")
    shutil.copy2(src,destination)
    destination.chmod(destination.stat().st_mode|0o111)
    version=subprocess.run([str(destination),"-version"],capture_output=True,text=True,check=True).stdout
    manifest={"provider":"imageio-ffmpeg 0.6.0", "binary":destination.name,
              "sha256":hashlib.sha256(destination.read_bytes()).hexdigest(),"version":version,"source":"https://github.com/FFmpeg/FFmpeg/tree/n7.1","upstream_builds":"https://www.gyan.dev/ffmpeg/builds/"}
    (ROOT/"vendor/manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(destination)
if __name__=="__main__":
    main()
