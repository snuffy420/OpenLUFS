"""Test production installer in an isolated per-user folder, then uninstall it."""
from pathlib import Path
import json,os,struct,subprocess,sys,tempfile,winreg,uuid,time,shutil
ROOT=Path(__file__).resolve().parents[1]
KEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6AD6510C-6D8E-4320-B936-82DE68D63130}_is1'


def registered():
    try:
        return winreg.OpenKey(winreg.HKEY_CURRENT_USER,KEY,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY)
    except FileNotFoundError:return None


def main():
    setup=Path(sys.argv[1]).resolve()
    raw=setup.read_bytes();offset=int.from_bytes(raw[60:64],'little')
    if raw[offset:offset+4]!=b'PE\0\0' or int.from_bytes(raw[offset+4:offset+6],'little')!=0x8664:
        raise RuntimeError('Setup is not a native x64 executable.')
    existing=registered()
    if existing:
        existing.Close();raise RuntimeError('An installed per-user OpenLUFS already exists; refusing to alter it during testing.')
    with tempfile.TemporaryDirectory(prefix='installer-test-',dir=ROOT/'.test-output') as folder:
        root=Path(folder).resolve();app=root/'OpenLUFS';group='OpenLUFS install test '+uuid.uuid4().hex[:8]
        command=[str(setup),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER','/DIR='+str(app),'/GROUP='+group,'/TASKS=','/LOG='+str(root/'install.log')]
        try:
            subprocess.run(command,check=True,timeout=180)
            if not (app/'OpenLUFS.exe').is_file() or not (app/'OpenLUFS.install.json').is_file():raise RuntimeError('Installed payload or marker missing.')
            key=registered()
            if key is None:raise RuntimeError('Installed Apps registration missing.')
            with key:
                location=winreg.QueryValueEx(key,'InstallLocation')[0]
                uninstall=winreg.QueryValueEx(key,'UninstallString')[0]
                version=winreg.QueryValueEx(key,'DisplayVersion')[0]
            if Path(location).resolve()!=app or version!='1.3.0':raise RuntimeError('Unexpected installer registration.')
            report=root/'diagnostics.json';env=os.environ.copy();env['LOCALAPPDATA']=str(root/'user-data')
            subprocess.run([str(app/'OpenLUFS.exe'),'--diagnostics',str(report)],env=env,check=True,timeout=120)
            data=json.loads(report.read_text(encoding='utf-8'))
            if not data['ok'] or Path(data['preferences_location'])!=root/'user-data/OpenLUFS/settings.json':raise RuntimeError('Installed app diagnostics or writable preferences failed.')
            print('x64 installer payload, Installed Apps registration and installed app: passed',flush=True)
        finally:
            executable=app/'unins000.exe'
            if executable.is_file():subprocess.run([str(executable),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(root/'uninstall.log')],check=True,timeout=120)
        key=registered()
        if key:
            key.Close();raise RuntimeError('Uninstall registration remained after uninstall.')
        if (app/'OpenLUFS.exe').exists():raise RuntimeError('Installed executable remained after uninstall.')
        print('Uninstaller cleanup and Installed Apps removal: passed',flush=True)
        # Inno's final self-removal process can briefly retain its log handle.
        if not root.is_relative_to((ROOT/'.test-output').resolve()):raise RuntimeError('Unexpected test cleanup path.')
        deadline=time.monotonic()+10
        while root.exists():
            try:shutil.rmtree(root)
            except PermissionError:
                if time.monotonic()>=deadline:raise
                time.sleep(.2)


if __name__=='__main__':main()
