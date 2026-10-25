"""Native helper discovery and writable installed/source preference paths."""
from pathlib import Path
import importlib.util
import os
import tempfile
import unittest
from unittest.mock import patch
from openlufs.paths import settings_path
from openlufs.engine import find_gain_tool
from test_audio import ROOT,WORK


class PlatformSetupTests(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(prefix='platform-',dir=WORK)
        self.root=Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def test_windows_portable_preferences_stay_beside_app(self):
        self.assertEqual(settings_path(self.root,'win32'),self.root/'OpenLUFS.settings.json')

    def test_installed_preferences_use_local_app_data(self):
        (self.root/'OpenLUFS.install.json').write_text('{}')
        local=self.root/'user-profile'
        self.assertEqual(settings_path(self.root,'win32',environ={'LOCALAPPDATA':str(local)}),local/'OpenLUFS/settings.json')

    def test_macos_and_linux_preferences_use_user_locations(self):
        home=self.root/'home'
        self.assertEqual(settings_path(self.root,'darwin',home=home),home/'Library/Application Support/OpenLUFS/settings.json')
        self.assertEqual(settings_path(self.root,'linux',home=home,environ={}),home/'.config/openlufs/settings.json')
        custom=self.root/'custom-config'
        self.assertEqual(settings_path(self.root,'linux',home=home,environ={'XDG_CONFIG_HOME':str(custom)}),custom/'openlufs/settings.json')
        self.assertEqual(settings_path(self.root,'linux',home=home,environ={'XDG_CONFIG_HOME':'relative'}),home/'.config/openlufs/settings.json')

    def test_gain_tool_override_and_path_discovery(self):
        binary=self.root/'mp3rgain';binary.write_bytes(b'fixture')
        with patch.dict(os.environ,{'OPENLUFS_MP3RGAIN':str(binary)}):
            self.assertEqual(find_gain_tool('linux'),binary.resolve())
        with patch.dict(os.environ,{'OPENLUFS_MP3RGAIN':''}),patch('openlufs.engine.resource_path',return_value=self.root/'missing'),patch('openlufs.engine.shutil.which',return_value=str(binary)):
            self.assertEqual(find_gain_tool('darwin'),binary)
        with patch.dict(os.environ,{'OPENLUFS_MP3RGAIN':str(self.root/'missing')}):
            with self.assertRaisesRegex(RuntimeError,'does not point'):find_gain_tool()

    def test_native_download_platform_mapping(self):
        spec=importlib.util.spec_from_file_location('fetch_native',ROOT/'tools/fetch_mp3rgain.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for system,cpu,key in [('Windows','AMD64','windows-x86_64'),('Darwin','arm64','darwin-universal'),('Darwin','x86_64','darwin-universal'),('Linux','x86_64','linux-x86_64'),('Linux','aarch64','linux-aarch64')]:
            self.assertEqual(module.platform_key(system,cpu),key)
        with self.assertRaises(RuntimeError):module.platform_key('Linux','i686')

    def test_shell_launchers_are_lf_and_support_both_modes(self):
        for name in ['setup.sh','run.sh']:
            data=(ROOT/name).read_bytes();self.assertNotIn(b'\r',data)
        self.assertIn('--no-venv',(ROOT/'setup.sh').read_text())
        self.assertIn('.python-deps',(ROOT/'run.sh').read_text())


if __name__=='__main__':unittest.main()
