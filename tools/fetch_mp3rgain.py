"""Fetch the pinned, checksum-verified native direct-gain tool for this OS."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import os
import platform
import tarfile
import urllib.request
import zipfile
ROOT=Path(__file__).resolve().parents[1]


def platform_key(system=None,machine=None):
    system=system or platform.system();machine=(machine or platform.machine()).lower()
    if system=='Windows' and machine in {'amd64','x86_64'}:return 'windows-x86_64'
    if system=='Darwin' and machine in {'arm64','aarch64','x86_64','amd64'}:return 'darwin-universal'
    if system=='Linux' and machine in {'x86_64','amd64'}:return 'linux-x86_64'
    if system=='Linux' and machine in {'aarch64','arm64'}:return 'linux-aarch64'
    raise RuntimeError('No pinned mp3rgain binary for this OS/CPU. Install mp3rgain 3.12.1 or newer on PATH instead.')


def extract(blob,windows):
    if windows:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            name=next(name for name in archive.namelist() if Path(name).name=='mp3rgain.exe')
            return archive.read(name)
    with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as archive:
        member=next(m for m in archive.getmembers() if m.isfile() and Path(m.name).name=='mp3rgain')
        return archive.extractfile(member).read()


def main():
    manifest=json.loads((ROOT/'vendor/mp3rgain-manifest.json').read_text(encoding='utf-8'))
    key=platform_key();windows=key=='windows-x86_64'
    info=manifest if windows else manifest['platforms'][key]
    request=urllib.request.Request(info['url'],headers={'User-Agent':'OpenLUFS-build'})
    blob=urllib.request.urlopen(request,timeout=120).read()
    if hashlib.sha256(blob).hexdigest()!=info['archive_sha256']:raise RuntimeError('Gain tool archive checksum mismatch.')
    payload=extract(blob,windows)
    if hashlib.sha256(payload).hexdigest()!=info['sha256']:raise RuntimeError('Gain tool executable checksum mismatch.')
    destination=ROOT/'vendor'/('mp3rgain.exe' if windows else 'mp3rgain')
    destination.write_bytes(payload)
    if not windows:destination.chmod(destination.stat().st_mode|0o111)
    print('Verified mp3rgain',manifest['version'],'for',key)


if __name__=='__main__':main()
