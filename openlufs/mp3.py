"""Validate gain-floor warnings against MP3 Layer III side information.

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
