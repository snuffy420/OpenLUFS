"""Writable preference locations for portable, installed and Unix source runs."""
import os
import sys
from pathlib import Path


def settings_path(base,platform_name=None,home=None,environ=None):
    base=Path(base);platform_name=platform_name or sys.platform
    home=Path.home() if home is None else Path(home)
    environ=os.environ if environ is None else environ
    if platform_name=='darwin':return home/'Library/Application Support/OpenLUFS/settings.json'
    if platform_name!='win32':
        config=Path(environ.get('XDG_CONFIG_HOME') or home/'.config')
        if not config.is_absolute():config=home/'.config'
        return config/'openlufs/settings.json'
    if (base/'OpenLUFS.install.json').is_file():
        local=Path(environ.get('LOCALAPPDATA') or home/'AppData/Local')
        return local/'OpenLUFS/settings.json'
    return base/'OpenLUFS.settings.json'
