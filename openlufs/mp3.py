"""MP3 frame inspection for bitrate detection and safe encoded gain.

A granule with part2_3_length == 0 carries no scale-factor or Huffman data;
its spectral coefficients are zero. Saturating its unused gain cannot change
its sound. Non-empty granules must still receive the exact requested gain.
"""
from pathlib import Path
from mutagen.mp3 import MP3


def read_bits(data, offset, width):
    end = offset+width
    if offset < 0 or end > len(data)*8:
        raise ValueError('Truncated MP3 side information.')
    return (int.from_bytes(data, 'big') >> (len(data)*8-end)) & ((1 << width)-1)


def silent_clamp_count(source, destination, steps, frames_expected):
    original = Path(source).read_bytes()
    output = Path(destination).read_bytes()
    if len(original) != len(output):
        raise ValueError('MP3 frame layout changed.')
    position = MP3(source).info.frame_offset
    frames = count = 0
    while position+4 <= len(original):
        header = int.from_bytes(original[position:position+4], 'big')
        version, layer = (header >> 19) & 3, (header >> 17) & 3
        index, rate_index = (header >> 12) & 15, (header >> 10) & 3
        if header >> 21 != 2047 or version == 1 or layer != 1 or index in {0,15} or rate_index == 3:
            break
        rate = [44100,48000,32000][rate_index] // (1 if version == 3 else 2 if version == 2 else 4)
        bitrates = ([0,32,40,48,56,64,80,96,112,128,160,192,224,256,320] if version == 3
                    else [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160])
        size = (144000 if version == 3 else 72000)*bitrates[index]//rate + ((header >> 9) & 1)
        channels = 1 if ((header >> 6) & 3) == 3 else 2
        offset = position+4+(0 if (header >> 16) & 1 else 2)
        length = (17 if channels == 1 else 32) if version == 3 else (9 if channels == 1 else 17)
        if position+size > len(original) or offset+length > position+size:
            raise ValueError('Truncated MP3 frame.')
        before, after = original[offset:offset+length], output[offset:offset+length]
        start = 9+(5 if channels == 1 else 3)+4*channels if version == 3 else 8+channels
        for item in range(channels*(2 if version == 3 else 1)):
            at = start+item*(59 if version == 3 else 63)
            part_length = read_bits(before, at, 12)
            gain = read_bits(before, at+21, 8)
            changed = gain+steps
            actual = read_bits(after, at+21, 8)
            if changed < 0:
                if part_length != 0 or read_bits(before, at+12, 9) != 0 or actual != 0:
                    raise ValueError('MP3 gain would saturate a non-silent block; exact constant gain is unavailable.')
                count += 1
            elif changed > 255 or actual != changed:
                raise ValueError('MP3 encoded gain did not match the requested constant adjustment.')
        frames += 1
        position += size
    if frames != frames_expected or count == 0:
        raise ValueError('Could not verify every MP3 frame involved in the gain warning.')
    return count


def mp3_layout(source, info=None):
    """Inspect complete MPEG Layer III frames, ignoring an actual Xing/Info frame.

    Padding bytes are part of frame lengths, not bitrate changes. An ordinary first
    audio frame is never discarded: it can establish that the stream is variable.
    """
    info=info if info is not None else MP3(source).info
    rates=set();total_bytes=0;seconds=0.;frames=0
    with Path(source).open('rb') as stream:
        stream.seek(0,2);end=stream.tell()
        if end>=128:
            stream.seek(end-128)
            if stream.read(3)==b'TAG':end-=128
        if end>=32:
            stream.seek(end-32);footer=stream.read(32)
            if footer[:8]==b'APETAGEX':
                size=int.from_bytes(footer[12:16],'little')
                if not 32<=size<=end:raise ValueError('Invalid MP3 APE tag size.')
                end-=size
                if end>=32:
                    stream.seek(end-32)
                    if stream.read(8)==b'APETAGEX':end-=32
        position=info.frame_offset
        while position<end:
            stream.seek(position);raw=stream.read(4)
            header=int.from_bytes(raw,'big')
            version=(header>>19)&3;index=(header>>12)&15;rate_index=(header>>10)&3
            valid=len(raw)==4 and header>>21==2047 and version!=1 and (header>>17)&3==1 and index not in {0,15} and rate_index!=3
            if not valid:
                # Some otherwise valid files end in zero padding outside the audio.
                stream.seek(position)
                if all(not any(chunk) for chunk in iter(lambda:stream.read(65536),b'')):break
                raise ValueError('Cannot determine MP3 bitrate mode: invalid or incomplete audio frame.')
            rate=[44100,48000,32000][rate_index]//(1 if version==3 else 2 if version==2 else 4)
            table=[0,32,40,48,56,64,80,96,112,128,160,192,224,256,320] if version==3 else [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160]
            bitrate=table[index]
            size=(144000 if version==3 else 72000)*bitrate//rate+((header>>9)&1)
            if position+size>end:raise ValueError('Cannot determine MP3 bitrate mode: truncated audio frame.')
            metadata_frame=False
            if frames==0:
                channels=1 if ((header>>6)&3)==3 else 2
                side=(17 if channels==1 else 32) if version==3 else (9 if channels==1 else 17)
                stream.seek(position+4+(0 if (header>>16)&1 else 2)+side)
                metadata_frame=stream.read(4) in {b'Xing',b'Info'}
                if size>=40:
                    stream.seek(position+36)
                    metadata_frame=metadata_frame or stream.read(4)==b'VBRI'
            if not metadata_frame:
                rates.add(bitrate);total_bytes+=size;seconds+=(1152 if version==3 else 576)/rate
            frames+=1;position+=size
    if not rates or seconds<=0:raise ValueError('Cannot determine original MP3 frame bitrate settings.')
    return rates,round(total_bytes*8/seconds)


def bitrate_properties(source, info=None, strict=False):
    """Share metadata/frame-derived bitrate detection between analysis and export.

    Trust explicit encoder CBR/VBR/ABR modes. If the mode is absent, inspect frames:
    constant nominal rates mean CBR; varying rates mean VBR for export purposes.
    Historical ABR versus VBR cannot be recovered from frame variation alone.
    """
    info=info if info is not None else MP3(source).info
    bitrate=int(getattr(info,'bitrate',0) or 0)
    value=getattr(info,'bitrate_mode',None)
    mode=getattr(value,'name',str(value) if value is not None else '').replace('BitrateMode.','').upper()
    if mode in {'CBR','VBR','ABR'}:return bitrate,mode
    try:
        rates,average=mp3_layout(source,info)
    except (OSError,ValueError):
        if strict:raise
        return bitrate,'UNKNOWN'
    return (next(iter(rates))*1000,'CBR') if len(rates)==1 else (average,'VBR')
