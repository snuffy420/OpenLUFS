"""Build, verify and package OpenLUFS; archive tools are build-time only."""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openlufs import __version__

SOURCE_DIRS=['openlufs','assets','tools','tests','docs','licenses','vendor','.github']
SOURCE_FILES=['norm.py','CHANGELOG.md','README.md','LICENSE','THIRD_PARTY_NOTICES.md','requirements.txt','requirements-build.txt','pyproject.toml','.gitignore','OpenLUFS.spec','setup.ps1','Run OpenLUFS.cmd']


def run(*args):subprocess.run([sys.executable,*args],cwd=ROOT,check=True)


def sevenzip():
    command=shutil.which('7z') or shutil.which('7za')
    installed=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'7-Zip/7z.exe'
    if command:return command
    if installed.is_file():return str(installed)
    raise SystemExit('Packaging requires 7-Zip on the build machine. OpenLUFS itself does not need it.')


def copy_source(destination,include_binaries):
    destination.mkdir(parents=True,exist_ok=True)
    for name in SOURCE_FILES:shutil.copy2(ROOT/name,destination/name)
    ignored=['__pycache__','*.pyc','*.pyo']
    for name in SOURCE_DIRS:
        extras=['*.exe'] if name=='vendor' and not include_binaries else []
        shutil.copytree(ROOT/name,destination/name,ignore=shutil.ignore_patterns(*(ignored+extras)))
    return destination


def archive(tool,stage,folder,destination):
    subprocess.run([tool,'a','-t7z','-mx=5','-mmt=2','-bd','-bso0','-bsp0',str(destination),folder],cwd=stage,check=True)
    subprocess.run([tool,'t','-bd','-bso0','-bsp0',str(destination)],check=True)
    if destination.stat().st_size==0:raise RuntimeError('Empty archive')


def package():
    tool=sevenzip();temp_root=(ROOT/'.build-temp').resolve();temp_root.mkdir(exist_ok=True)
    releases=ROOT/'releases';releases.mkdir(exist_ok=True)
    prefix=f'OpenLUFS-{__version__}'
    with tempfile.TemporaryDirectory(prefix='package-',dir=temp_root) as folder:
        stage=Path(folder).resolve()
        if not stage.is_relative_to(temp_root):raise RuntimeError('Invalid staging directory')
        portable=stage/'OpenLUFS';portable.mkdir()
        for name in ['README.md','CHANGELOG.md','LICENSE','THIRD_PARTY_NOTICES.md']:
            shutil.copy2(ROOT/name,portable/name)
        shutil.copy2(ROOT/'dist/OpenLUFS.exe',portable/'OpenLUFS.exe')
        for name in ['licenses','docs','assets']:shutil.copytree(ROOT/name,portable/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copy2(ROOT/'vendor/manifest.json',portable/'ffmpeg-manifest.json')
        shutil.copy2(ROOT/'vendor/mp3rgain-manifest.json',portable/'mp3rgain-manifest.json')
        source=copy_source(stage/(prefix+'-source'),True)
        outputs=[]
        for directory,name in [(portable,prefix+'-windows-x64-portable.7z'),(source,prefix+'-source.7z')]:
            candidate=stage/name
            archive(tool,stage,directory.name,candidate)
            final=releases/name;os.replace(candidate,final);outputs.append(final)
        upload_base=ROOT/'GitHub';upload_base.mkdir(exist_ok=True)
        upload=upload_base/prefix
        suffix=2
        while upload.exists():upload=upload_base/f'{prefix}-{suffix}';suffix+=1
        copy_source(upload,False)
        checks=[]
        for item in outputs:
            text=hashlib.sha256(item.read_bytes()).hexdigest()+'  '+item.name+'\n'
            item.with_suffix(item.suffix+'.sha256').write_text(text,encoding='ascii')
            item.with_suffix(item.suffix+'.sha').write_text(text,encoding='ascii')
            checks.append(text)
            print(f'{item}: {item.stat().st_size/1024**2:.1f} MiB')
        (releases/'SHA256SUMS.txt').write_text(''.join(checks),encoding='ascii')
        print('GitHub source folder:',upload)


def main():
    temp=ROOT/'.build-temp';temp.mkdir(exist_ok=True)
    os.environ['TEMP']=str(temp);os.environ['TMP']=str(temp)
    sevenzip()
    if '--package-only' not in sys.argv:
        if not (ROOT/'vendor/ffmpeg.exe').exists():run('tools/fetch_ffmpeg.py')
        if not (ROOT/'vendor/mp3rgain.exe').exists():run('tools/fetch_mp3rgain.py')
        run('tools/generate_donation_qr.py')
        run('-m','unittest','discover','-s','tests','-v')
        run('tools/render_screenshots.py')
        run('-m','PyInstaller','--clean','--noconfirm','OpenLUFS.spec')
        run('tools/check_bundle.py')
    package()

if __name__=='__main__':main()
