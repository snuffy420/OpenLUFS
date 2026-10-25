"""Encoding profiles and metadata restoration for matching renders.

Audio-dependent stream tables/encoder delay are regenerated. User metadata is
restored from the source, including raw MP3/ADTS tags and MP4 metadata atoms.
"""
from copy import deepcopy
from pathlib import Path
import re
import shutil
import struct
import mutagen
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from .models import MP4_EXTENSIONS, OPUS_EXTENSIONS
from .containers import restore_metadata, non_audio_digest
from .ogg import inspect_opus, packets
from .mp3 import bitrate_properties


def tag_bounds(path):
    data=Path(path).read_bytes()
    start=0
    while data[start:start+3]==b'ID3':
        header=data[start:start+10]
        if len(header)!=10: raise ValueError('Truncated ID3 tag.')
        start+=10+sum((v&127)<<(7*(3-i)) for i,v in enumerate(header[6:10]))+(10 if header[5]&16 else 0)
        if start>len(data): raise ValueError('Invalid ID3 tag length.')
    end=len(data)
    if end>=128 and data[end-128:end-125]==b'TAG': end-=128
    if end>=32 and data[end-32:end-24]==b'APETAGEX':
        size=int.from_bytes(data[end-20:end-16],'little')
        if not 32<=size<=end-start: raise ValueError('Invalid APE tag size.')
        end-=size
        if end>=32 and data[end-32:end-24]==b'APETAGEX': end-=32
    return data,start,end


def adts_samples(path):
    data,start,end=tag_bounds(path)
    samples=0
    while start<end:
        header=data[start:start+7]
        if len(header)!=7 or header[0]!=255 or header[1]&246!=240:
            raise ValueError('Unsupported or truncated ADTS frame.')
        length=((header[3]&3)<<11)|(header[4]<<3)|(header[5]>>5)
        if length<(7 if header[1]&1 else 9) or start+length>end:
            raise ValueError('Invalid ADTS frame size.')
        samples+=1024*((header[6]&3)+1)
        start+=length
    return samples


def encoding_profile(source,before,engine):
    ext=source.suffix.lower()
    if before.codec.startswith('pcm_') or (ext=='.flac' and before.codec=='flac') or (ext in MP4_EXTENSIONS and before.codec=='alac'):
        return engine.pcm_encoding(source,before),{'lossy':False},[]
    notes=[]
    if ext=='.mp3' and before.codec=='mp3':
        info=MP3(source).info
        bitrate,mode=bitrate_properties(source,info,strict=True)
        kbps=round(bitrate/1000)
        if mode=='VBR':
            match=re.search(r'-V\s*(\d+(?:\.\d+)?)',info.encoder_settings)
            if match:
                quality=float(match[1])
            else:
                candidates=[245,225,190,175,165,130,115,100,85,65]
                quality=min(range(10),key=lambda q:abs(candidates[q]-kbps))
                notes.append('Original VBR quality was unavailable; the nearest LAME VBR quality was estimated from the source bitrate.')
            args=['-c:a','libmp3lame','-q:a',str(quality),'-compression_level','0']
            profile={'lossy':True,'mode':'VBR','quality':quality,'source_bitrate':bitrate}
            notes.append('VBR encoding mode is retained; average bitrate and file size can change after re-encoding.')
        else:
            # Mutagen reports UNKNOWN for many CBR files without a Xing/Info tag.
            allowed=[8,16,24,32,40,48,56,64,80,96,112,128,144,160,192,224,256,320]
            nominal=min(allowed,key=lambda b:abs(b-kbps))
            if mode!='ABR' and abs(nominal-kbps)>1:
                raise ValueError('The original MP3 bitrate cannot be reproduced by the bundled encoder.')
            if mode=='ABR':
                args=['-c:a','libmp3lame','-abr','1','-b:a',str(bitrate),'-compression_level','0']
                profile={'lossy':True,'mode':'ABR','target_bitrate':bitrate}
            else:
                args=['-c:a','libmp3lame','-b:a',f'{nominal}k','-compression_level','0']
                profile={'lossy':True,'mode':'CBR','target_bitrate':nominal*1000}
        return args+['-id3v2_version','0','-write_id3v1','0','-write_xing','1','-f','mp3'],profile,notes
    if before.codec=='aac' and ext in MP4_EXTENSIONS|{'.aac'}:
        if before.profile and before.profile not in {'LC','AAC LC'}:
            raise ValueError('Matching currently supports AAC-LC only; HE-AAC is not silently converted.')
        if ext in MP4_EXTENSIONS:
            info=MP4(source).info
            if getattr(info,'codec','') not in {'mp4a.40.2'}:
                raise ValueError('Matching currently supports AAC-LC only in MP4 containers.')
        else:
            data,start,_=tag_bounds(source)
            if data[start:start+1]!=b'\xff' or len(data)<start+3 or (data[start+2]>>6)!=1:
                raise ValueError('Matching currently supports raw ADTS AAC-LC only.')
        bitrate=before.bitrate
        if bitrate<=0: raise ValueError('Could not determine the source AAC bitrate.')
        notes.append('AAC uses the measured original bitrate as the encoder target; actual average bitrate and file size can vary.')
        return ['-c:a','aac','-profile:a','aac_low','-b:a',str(bitrate),'-f','adts' if ext=='.aac' else 'mp4'],{'lossy':True,'mode':'AAC-LC','target_bitrate':bitrate},notes
    if ext in OPUS_EXTENSIONS and before.codec=='opus':
        inspect_opus(source)
        lengths=[len(p) for i,p in enumerate(packets(source)) if i>=2]
        cbr=bool(lengths) and len(set(lengths[:-1] or lengths))==1
        bitrate=max(6000,min(512000,before.bitrate))
        notes.append('Opus uses the measured source bitrate as its encoder target; actual average bitrate and file size can vary.')
        return ['-c:a','libopus','-b:a',str(bitrate),'-vbr','off' if cbr else 'on','-application','audio','-compression_level','10','-f','opus'],{'lossy':True,'mode':'CBR' if cbr else 'VBR','target_bitrate':bitrate},notes
    raise ValueError('No supported matching renderer for this encoding; no conversion was performed.')


def atoms(data):
    position=0
    while position<len(data):
        if len(data)-position<8: raise ValueError('Truncated MP4 metadata atom.')
        size=int.from_bytes(data[position:position+4],'big'); header=8
        if size==1:
            if len(data)-position<16: raise ValueError('Truncated extended MP4 atom.')
            size=int.from_bytes(data[position+8:position+16],'big');header=16
        elif size==0:size=len(data)-position
        if size<header or position+size>len(data): raise ValueError('Invalid MP4 metadata atom.')
        yield data[position+4:position+8],data[position:position+size],header
        position+=size


def box(kind,payload):
    return struct.pack('>I4s',len(payload)+8,kind)+payload


def file_atoms(path):
    """Read MP4 root headers without loading the media payload into memory."""
    with Path(path).open('rb') as stream:
        stream.seek(0,2);end=stream.tell();position=0
        while position<end:
            stream.seek(position);raw=stream.read(8);header=8
            if len(raw)!=8:raise ValueError('Truncated MP4 metadata atom.')
            size=int.from_bytes(raw[:4],'big')
            if size==1:
                extended=stream.read(8);header=16
                if len(extended)!=8:raise ValueError('Truncated extended MP4 atom.')
                size=int.from_bytes(extended,'big')
            elif size==0:size=end-position
            if size<header or position+size>end:raise ValueError('Invalid MP4 metadata atom.')
            yield raw[4:8],position,size,header,raw[:4]==bytes(4)
            position+=size


def mp4_metadata(source,rendered):
    # Media stays in place. Change the rendered moov into a free atom, then append
    # its rebuilt metadata. Existing audio/chapter chunk offsets remain valid.
    source,rendered=Path(source),Path(rendered)
    old_atoms=list(file_atoms(source));new_atoms=list(file_atoms(rendered))
    def movie(path,items):
        item=next((entry for entry in items if entry[0]==b'moov'),None)
        if item is None:raise ValueError('MP4 movie metadata is missing.')
        _,position,size,header,_=item
        with path.open('rb') as stream:
            stream.seek(position+header);return stream.read(size-header)
    old_moov=movie(source,old_atoms);new_moov=movie(rendered,new_atoms)
    metadata={b'udta',b'meta',b'uuid'}
    technical={b'mvhd',b'trak',b'mvex',b'iods',b'free',b'skip'}
    preserved=[data for kind,data,_ in atoms(old_moov) if kind not in technical]
    body=b''.join(data for kind,data,_ in atoms(new_moov) if kind not in metadata)+b''.join(preserved)
    excluded={b'ftyp',b'styp',b'moov',b'mdat',b'free',b'skip',b'wide',b'sidx',b'mfra',b'moof',b'pdin',b'prft'}
    for _,_,size,_,open_ended in new_atoms:
        if open_ended and size>0xffffffff:
            raise ValueError('Cannot safely append metadata after an oversized open-ended MP4 atom.')
    with rendered.open('r+b') as out,source.open('rb') as original:
        for kind,position,size,_,open_ended in new_atoms:
            if open_ended:
                out.seek(position);out.write(size.to_bytes(4,'big'))
            if kind==b'moov':
                out.seek(position+4);out.write(b'free')
        out.seek(0,2);out.write(box(b'moov',body))
        for kind,position,size,_,_ in old_atoms:
            if kind in excluded:continue
            original.seek(position);remaining=size
            while remaining:
                chunk=original.read(min(1024*1024,remaining))
                if not chunk:raise ValueError('Truncated MP4 user metadata.')
                out.write(chunk);remaining-=len(chunk)
    if dict(MP4(source).tags or {})!=dict(MP4(rendered).tags or {}):
        raise ValueError('MP4 user metadata changed; export rejected.')


def restore_render_metadata(source,rendered):
    source,rendered=Path(source),Path(rendered)
    ext=source.suffix.lower()
    if ext in {'.mp3','.aac'}:
        old,start,end=tag_bounds(source)
        new,begin,finish=tag_bounds(rendered)
        if ext=='.mp3':
            # Retain the new stream's Xing/LAME delay/padding header, not the old one.
            begin=MP3(rendered).info.frame_offset
            start=MP3(source).info.frame_offset
        rendered.write_bytes(old[:start]+new[begin:finish]+old[end:])
        if non_audio_digest(source)!=non_audio_digest(rendered):
            raise ValueError('Original encoded-file tags changed; export rejected.')
    elif ext in MP4_EXTENSIONS:
        mp4_metadata(source,rendered)
    elif ext in OPUS_EXTENSIONS:
        original=OggOpus(source);output=OggOpus(rendered)
        output.clear();output.update(deepcopy(original.tags or {}));output.save()
        if dict(original.tags or {})!=dict(OggOpus(rendered).tags or {}):
            raise ValueError('Opus user metadata changed; export rejected.')
    else:
        restore_metadata(source,rendered)
