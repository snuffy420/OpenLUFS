"""Fetch the pinned, checksum-verified direct-gain tool."""
from pathlib import Path
import hashlib,io,json,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'vendor/mp3rgain-manifest.json').read_text(encoding='utf-8'))
request=urllib.request.Request(manifest['url'],headers={'User-Agent':'OpenLUFS-build'})
blob=urllib.request.urlopen(request,timeout=120).read()
if hashlib.sha256(blob).hexdigest()!=manifest['archive_sha256']: raise SystemExit('Gain tool archive checksum mismatch')
with zipfile.ZipFile(io.BytesIO(blob)) as archive:
    name=next(n for n in archive.namelist() if n.endswith('mp3rgain.exe'))
    payload=archive.read(name)
if hashlib.sha256(payload).hexdigest()!=manifest['sha256']: raise SystemExit('Gain tool executable checksum mismatch')
(ROOT/'vendor/mp3rgain.exe').write_bytes(payload)
print('Verified mp3rgain',manifest['version'])
