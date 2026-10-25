"""Build the branded x64 installer using a project-local verified Inno compiler."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,urllib.request
ROOT=Path(__file__).resolve().parents[1]


def compiler():
    configured=os.environ.get('OPENLUFS_ISCC')
    if configured:
        path=Path(configured)
        if not path.is_file():raise RuntimeError('OPENLUFS_ISCC does not point to ISCC.exe.')
        return path
    folder=ROOT/'.build-tools/InnoSetup7';command=folder/'ISCC.exe'
    if command.is_file():return command
    if os.name!='nt':raise RuntimeError('Windows installer creation requires Windows.')
    manifest=json.loads((ROOT/'vendor/inno-manifest.json').read_text(encoding='utf-8'))
    blob=urllib.request.urlopen(manifest['url'],timeout=120).read()
    if hashlib.sha256(blob).hexdigest()!=manifest['sha256']:raise RuntimeError('Inno Setup download checksum mismatch.')
    download=ROOT/'.build-tools'/('innosetup-'+manifest['version']+'-x64.exe')
    download.parent.mkdir(exist_ok=True);download.write_bytes(blob)
    subprocess.run([str(download),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER','/PORTABLE=1','/NOICONS','/TASKS=','/DIR='+str(folder)],check=True,timeout=120)
    if not command.is_file():raise RuntimeError('Portable Inno compiler preparation failed.')
    return command


def build(payload,destination,version):
    payload=Path(payload).resolve();destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
    if not (payload/'OpenLUFS.exe').is_file():raise RuntimeError('Verified portable payload is missing.')
    subprocess.run([str(compiler()),'--quiet','--define=PayloadDir='+str(payload),'--define=BuildVersion='+version,
                    '--output-dir='+str(destination),str(ROOT/'installer/OpenLUFS.iss')],check=True)
    result=destination/f'OpenLUFS-{version}-windows-x64-setup.exe'
    if not result.is_file():raise RuntimeError('Installer was not generated.')
    return result


if __name__=='__main__':
    if len(sys.argv)!=4:raise SystemExit('Usage: build_installer.py PORTABLE_PAYLOAD OUTPUT_DIRECTORY VERSION')
    print(build(sys.argv[1],sys.argv[2],sys.argv[3]))
