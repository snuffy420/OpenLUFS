"""Ogg Opus output-gain editing without changing encoded audio packets.

RFC 7845 defines the Q7.8 gain field and requires R128 tags to be adjusted
when this field changes. Other comments and artwork are retained.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct


def pages(path):
    with Path(path).open('rb') as f:
        serial=None
        while True:
            start=f.tell(); header=f.read(27)
            if not header: return
            if len(header)!=27 or header[:4]!=b'OggS' or header[4]!=0:
                raise ValueError('Invalid Ogg page.')
            current=header[14:18]
            if serial is None: serial=current
            elif current!=serial: raise ValueError('Chained or multiplexed Ogg streams are not supported.')
            lacing=f.read(header[26])
            payload=f.read(sum(lacing))
            if len(lacing)!=header[26] or len(payload)!=sum(lacing):
                raise ValueError('Truncated Ogg page.')
            yield start,header,lacing,payload


def packets(path):
    packet=bytearray()
    for _,header,lacing,payload in pages(path):
        offset=0
        for count in lacing:
            packet.extend(payload[offset:offset+count]); offset+=count
            if len(packet)>64*1024*1024: raise ValueError('Ogg metadata packet exceeds the supported size.')
            if count<255:
                yield bytes(packet); packet.clear()
    if packet: raise ValueError('Truncated Ogg packet.')


def read_comments(packet):
    if packet[:8]!=b'OpusTags': raise ValueError('Opus comment header is missing.')
    position=8
    def take_string():
        nonlocal position
        if position+4>len(packet): raise ValueError('Truncated Opus comments.')
        size=int.from_bytes(packet[position:position+4],'little'); position+=4
        data=packet[position:position+size]; position+=size
        if len(data)!=size: raise ValueError('Truncated Opus comments.')
        return data
    vendor=take_string()
    if position+4>len(packet): raise ValueError('Truncated Opus comments.')
    count=int.from_bytes(packet[position:position+4],'little'); position+=4
    if count>(len(packet)-position)//4: raise ValueError('Invalid Opus comment count.')
    comments=[]
    for _ in range(count):
        text=take_string()
        key,separator,value=text.partition(b'=')
        comments.append((key.lower(),value) if separator else (b'',text))
    return vendor,comments


@dataclass
class OpusInfo:
    gain_q8: int
    audio_digest: bytes
    header: bytes
    vendor: bytes
    comments: list


def inspect_opus(path):
    iterator=iter(packets(path))
    header=next(iterator,b'')
    if len(header)<19 or header[:8]!=b'OpusHead':
        raise ValueError('This Ogg file is not Opus. Vorbis has no equivalent output-gain header and is not normalized without re-encoding.')
    gain=struct.unpack_from('<h',header,16)[0]
    normalized=header[:16]+b'\0\0'+header[18:]
    vendor,comments=read_comments(next(iterator,b''))
    digest=hashlib.sha256()
    for packet in iterator:
        digest.update(len(packet).to_bytes(4,'little')); digest.update(packet)
    return OpusInfo(gain,digest.digest(),normalized,vendor,comments)


def ogg_crc(data):
    crc=0
    for byte in data:
        crc^=byte<<24
        for _ in range(8):
            crc=((crc<<1)^0x04c11db7) & 0xffffffff if crc&0x80000000 else (crc<<1)&0xffffffff
    return crc


def apply_opus_gain(path, steps):
    """steps are signed units of 1/256 dB, relative to the original header."""
    path=Path(path); before=inspect_opus(path)
    gain=before.gain_q8+steps
    if not -32768<=gain<=32767: raise ValueError('The requested Opus gain is outside its header range.')
    _,header,lacing,payload=next(pages(path))
    if payload[:8]!=b'OpusHead' or len(payload)<19:
        raise ValueError('The Opus header must be complete in the first page.')
    page=bytearray(header+lacing+payload); offset=len(header)+len(lacing)
    struct.pack_into('<h',page,offset+16,gain)
    page[22:26]=b'\0'*4; struct.pack_into('<I',page,22,ogg_crc(page))
    with path.open('r+b') as f: f.write(page)
    r128={}
    for key,value in before.comments:
        if key in {b'r128_track_gain',b'r128_album_gain'}:
            if key in r128: raise ValueError('Duplicate R128 gain tags are unsupported.')
            try: adjusted=int(value)-steps
            except ValueError: raise ValueError('Malformed R128 gain tag.')
            if not -32768<=adjusted<=32767: raise ValueError('Adjusted R128 gain is outside the supported range.')
            r128[key.decode('ascii')]=adjusted
    if r128:
        from mutagen.oggopus import OggOpus
        metadata=OggOpus(path)
        for key,value in r128.items(): metadata[key]=[str(value)]
        metadata.save()
    after=inspect_opus(path)
    exclude={b'r128_track_gain',b'r128_album_gain'}
    original_tags=sorted(item for item in before.comments if item[0] not in exclude)
    exported_tags=sorted(item for item in after.comments if item[0] not in exclude)
    if (before.audio_digest!=after.audio_digest or before.header!=after.header
        or before.vendor!=after.vendor or original_tags!=exported_tags or after.gain_q8!=gain):
        raise ValueError('Opus audio packets or original descriptive metadata changed; export rejected.')
    actual={key.decode('ascii'):value for key,value in after.comments if key in exclude}
    if any(actual.get(key)!=str(value).encode('ascii') for key,value in r128.items()):
        raise ValueError('Opus R128 gain references could not be updated safely.')
    return ['Existing R128 playback-gain references were updated for the changed Opus header gain.'] if r128 else []
