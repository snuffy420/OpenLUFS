"""Preserve original metadata bytes while replacing only lossless PCM audio.

WAV/AIFF are cloned and their existing sample payload is overwritten in place.
FLAC retains every non-technical metadata block verbatim. STREAMINFO and the
seek index describe newly encoded frames and are updated from the render.
"""
import hashlib
from pathlib import Path
import shutil
import struct
from .models import WAV_EXTENSIONS, AIFF_EXTENSIONS, MP4_EXTENSIONS


def pcm_payload(path):
    with Path(path).open('rb') as f:
        header=f.read(12)
        wav=header[:4] in {b'RIFF',b'RF64'} and header[8:]==b'WAVE'
        aiff=header[:4]==b'FORM' and header[8:] in {b'AIFF',b'AIFC'}
        if not (wav or aiff):
            raise ValueError('Unsupported PCM container; originals are left untouched.')
        endian='little' if wav else 'big'
        rf64_data=None
        while True:
            raw=f.read(8)
            if len(raw)!=8: break
            name=raw[:4]; size=int.from_bytes(raw[4:],endian)
            start=f.tell()
            if name==b'ds64' and size>=28:
                data=f.read(28); rf64_data=int.from_bytes(data[8:16],'little'); f.seek(start)
            if wav and name==b'data':
                if size==0xffffffff:
                    if rf64_data is None: raise ValueError('RF64 data size is missing.')
                    size=rf64_data
                return start,size
            if aiff and name==b'SSND':
                data=f.read(8)
                if len(data)!=8: break
                offset=int.from_bytes(data[:4],'big')
                if size<8+offset: break
                return start+8+offset,size-8-offset
            f.seek(start+size+(size&1))
    raise ValueError('Could not locate the original PCM sample payload.')


def flac_parts(path):
    with Path(path).open('rb') as f:
        prefix=b''
        if f.read(3)==b'ID3':
            f.seek(0); header=f.read(10)
            size=sum((b&127)<<(7*(3-i)) for i,b in enumerate(header[6:10]))
            f.seek(0); prefix=f.read(10+size)
        else: f.seek(0)
        if f.read(4)!=b'fLaC': raise ValueError('Unsupported FLAC header.')
        blocks=[]
        while True:
            header=f.read(4)
            if len(header)!=4: raise ValueError('Truncated FLAC metadata.')
            length=int.from_bytes(header[1:],'big'); payload=f.read(length)
            if len(payload)!=length: raise ValueError('Truncated FLAC metadata.')
            blocks.append((header[0]&127,payload))
            if header[0]&128: return prefix,blocks,f.tell()


def restore_metadata(source, rendered):
    source,rendered=Path(source),Path(rendered)
    replacement=rendered.with_name(rendered.name+'.preserve')
    try:
        if source.suffix.lower() in WAV_EXTENSIONS | AIFF_EXTENSIONS:
            old_offset,old_size=pcm_payload(source)
            new_offset,new_size=pcm_payload(rendered)
            if old_size!=new_size:
                raise ValueError('Export sample count or storage depth changed; export rejected to preserve the original container.')
            shutil.copyfile(source,replacement)
            with rendered.open('rb') as audio,replacement.open('r+b') as output:
                audio.seek(new_offset); output.seek(old_offset)
                remaining=new_size
                while remaining:
                    chunk=audio.read(min(1024*1024,remaining))
                    if not chunk: raise ValueError('Truncated rendered samples.')
                    output.write(chunk); remaining-=len(chunk)
        elif source.suffix.lower()=='.flac':
            prefix,old_blocks,_=flac_parts(source)
            _,new_blocks,audio_offset=flac_parts(rendered)
            old_info=next(data for kind,data in old_blocks if kind==0)
            new_info=next(data for kind,data in new_blocks if kind==0)
            if old_info[10:18]!=new_info[10:18]:
                raise ValueError('FLAC sample count, channels, rate or bit depth changed; export rejected.')
            technical={kind:data for kind,data in new_blocks if kind in {0,3}}
            blocks=[]
            for kind,data in old_blocks:
                if kind in {0,3}:
                    if kind in technical: blocks.append((kind,technical[kind]))
                else: blocks.append((kind,data))
            with replacement.open('wb') as output,rendered.open('rb') as audio:
                output.write(prefix+b'fLaC')
                for index,(kind,data) in enumerate(blocks):
                    output.write(bytes([kind|(128 if index==len(blocks)-1 else 0)])+len(data).to_bytes(3,'big')+data)
                audio.seek(audio_offset); shutil.copyfileobj(audio,output)
        else:
            raise ValueError('No verified metadata-preserving renderer for this container.')
        rendered.unlink(); replacement.replace(rendered)
    finally:
        replacement.unlink(missing_ok=True)


def non_audio_digest(path):
    """Hash MP4 non-mdat atoms, or MP3/AAC leading/trailing tag bytes."""
    path=Path(path); digest=hashlib.sha256()
    with path.open('rb') as f:
        size=path.stat().st_size
        if path.suffix.lower() in MP4_EXTENSIONS:
            while f.tell()<size:
                start=f.tell(); header=f.read(8)
                if len(header)!=8: raise ValueError('Truncated MP4 atom.')
                length=int.from_bytes(header[:4],'big'); kind=header[4:]
                if length==1:
                    extended=f.read(8); length=int.from_bytes(extended,'big'); header+=extended
                elif length==0: length=size-start
                if length<len(header) or start+length>size: raise ValueError('Invalid MP4 atom size.')
                if kind!=b'mdat':
                    digest.update(header); remaining=length-len(header)
                    while remaining:
                        chunk=f.read(min(1024*1024,remaining)); digest.update(chunk); remaining-=len(chunk)
                f.seek(start+length)
        else:
            header=f.read(10)
            if header[:3]==b'ID3':
                length=10+sum((b&127)<<(7*(3-i)) for i,b in enumerate(header[6:10]))
                if header[5]&0x10: length+=10
                f.seek(0); digest.update(f.read(length))
            end=size
            if end>=128:
                f.seek(end-128); tail=f.read(128)
                if tail[:3]==b'TAG': digest.update(tail); end-=128
            if end>=32:
                f.seek(end-32); footer=f.read(32)
                if footer[:8]==b'APETAGEX':
                    length=int.from_bytes(footer[12:16],'little')
                    if not 32<=length<=end: raise ValueError('Invalid APE metadata size.')
                    start=end-length
                    if start>=32:
                        f.seek(start-32)
                        if f.read(8)==b'APETAGEX': start-=32
                    f.seek(start); digest.update(f.read(end-start))
    return digest.digest()
