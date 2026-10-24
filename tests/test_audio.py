"""Integration tests with real audio, actual encoders, and independent metering."""
from array import array
import hashlib
import math
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import threading
import time
import unittest
import wave

from mutagen.wave import WAVE
from mutagen.id3 import TIT2, TXXX, PRIV
from openlufs.engine import Cancelled, Engine, find_ffmpeg
from openlufs.models import Settings, discover, plan_outputs

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/".test-output"


def tone(path, amplitude=0.25, seconds=5, rate=48000, channels=2, transient=False):
    values=array("h")
    for i in range(int(seconds*rate)):
        value=amplitude*math.sin(2*math.pi*997*i/rate)
        if transient and i%(rate//2)<120:
            value=0.90*math.sin(2*math.pi*3100*i/rate)
        for c in range(channels):
            values.append(round(32767*value*(1 if c==0 else 0.72)))
    with wave.open(str(path),"wb") as output:
        output.setparams((channels,2,rate,0,"NONE","not compressed"))
        output.writeframes(values.tobytes())


def decode(path):
    raw=subprocess.run([find_ffmpeg(),"-v","error","-i",str(path),"-f","f64le","-c:a","pcm_f64le","-"],capture_output=True,check=True).stdout
    samples=array("d"); samples.frombytes(raw)
    return samples



from openlufs.containers import pcm_payload, flac_parts, non_audio_digest

class AudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORK.mkdir(exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='audio-',dir=WORK)
        cls.folder=Path(cls.temp.name); cls.engine=Engine()
        cls.source=cls.folder/'Reference stereo.wav'; tone(cls.source)
        cls.transient=cls.folder/'Transient stereo.wav'; tone(cls.transient,0.05,6,transient=True)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def output(self,name): return self.folder/(self._testMethodName+name)

    def assert_constant_gain(self,source,result,tolerance=0.00004):
        a,b=decode(source),decode(result.destination)
        self.assertEqual(len(a),len(b))
        gain=10**(result.gain_db/20)
        self.assertLess(max(abs(y-x*gain) for x,y in zip(a,b)),tolerance)
        self.assertLessEqual(result.after.true_peak,-1)

    def test_default_requires_original_format_without_limiter(self):
        self.assertEqual(Settings().output_format,'source')
        self.assertFalse(Settings().allow_limiter)
        with self.assertRaises(ValueError): Settings(output_format='wav')
        self.assertTrue(Settings(allow_limiter=True).allow_limiter)
        for value in [float('nan'),float('inf'),-60,1]:
            with self.assertRaises(ValueError): Settings(target=value)

    def test_gain_only_preserves_dynamics_and_source(self):
        original=hashlib.sha256(self.source.read_bytes()).digest()
        result=self.engine.normalize(self.source,self.output('.wav'),Settings(-23,-1))
        self.assertEqual(result.mode,'Gain only')
        self.assertEqual(result.after.bits,16)
        self.assertAlmostEqual(result.after.integrated,-23,delta=0.100001)
        self.assert_constant_gain(self.source,result)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).digest(),original)

    def test_peak_headroom_caps_gain_without_limiting(self):
        result=self.engine.normalize(self.transient,self.output('.wav'),Settings(-14,-1))
        self.assertEqual(result.mode,'Gain capped')
        self.assertLess(result.after.integrated,-14.1)
        self.assertTrue(any('headroom' in w for w in result.warnings))
        self.assert_constant_gain(self.transient,result)

    def test_wav_24_and_32_bit_storage_retained(self):
        for bits in [24,32]:
            with self.subTest(bits=bits):
                source=self.output(f'-{bits}.wav')
                self.engine.run(['-y','-i',self.source,'-c:a',f'pcm_s{bits}le',source])
                result=self.engine.normalize(source,self.output(f'-out{bits}.wav'),Settings(-20,-1))
                self.assertEqual(result.after.bits,bits)
                self.assert_constant_gain(source,result,2/2**(bits-1))

    def test_float_and_mono_44100_retained(self):
        mono=self.output('-mono.wav'); tone(mono,rate=44100,channels=1)
        source=self.output('-float.wav'); self.engine.run(['-y','-i',mono,'-c:a','pcm_f32le',source])
        result=self.engine.normalize(source,self.output('.wav'),Settings(-20,-1))
        self.assertEqual((result.after.sample_rate,result.after.channels,result.after.codec),(44100,1,'pcm_f32le'))
        self.assert_constant_gain(source,result,1e-6)

    def test_mp3_cbr_bitrate_tags_and_audio_without_reencoding(self):
        from mutagen.mp3 import MP3
        for bitrate in [128,320]:
            with self.subTest(bitrate=bitrate):
                source=self.output(f'-{bitrate}.mp3')
                self.engine.run(['-y','-i',self.source,'-c:a','libmp3lame','-b:a',f'{bitrate}k',source])
                tags=MP3(source); tags.tags.add(TIT2(encoding=3,text=['Original title']))
                tags.tags.add(PRIV(owner='OpenLUFS.cues',data=b'private cue data'))
                tags.tags.add(TXXX(encoding=3,desc='REPLAYGAIN_TRACK_GAIN',text=['+4 dB'])); tags.save()
                source_hash=hashlib.sha256(source.read_bytes()).digest()
                result=self.engine.normalize(source,self.output(f'-out{bitrate}.mp3'),Settings(-20,-1))
                out=MP3(result.destination)
                self.assertEqual(result.mode,'Direct gain')
                self.assertEqual(out.info.bitrate,bitrate*1000)
                self.assertEqual(out.info.bitrate_mode,MP3(source).info.bitrate_mode)
                self.assertEqual(non_audio_digest(source),non_audio_digest(result.destination))
                self.assertEqual(str(out.tags['TIT2']),'Original title')
                self.assertEqual(out.tags.getall('PRIV')[0].data,b'private cue data')
                self.assertIn('TXXX:REPLAYGAIN_TRACK_GAIN',out.tags)
                self.assertAlmostEqual(result.after.integrated,-20,delta=0.86)
                self.assert_constant_gain(source,result,2e-6)
                self.assertEqual(hashlib.sha256(source.read_bytes()).digest(),source_hash)
                self.assertEqual(source.stat().st_size,Path(result.destination).stat().st_size)

    def test_mp3_empty_blocks_can_attenuate_without_false_failure(self):
        from mutagen.mp3 import MP3
        source=self.output('-unsupported-clamp-title-empty-start.mp3')
        self.engine.run(['-y','-i',self.source,'-c:a','libmp3lame','-b:a','320k',source])
        data=source.read_bytes(); offset=MP3(source).info.frame_offset
        header=int.from_bytes(data[offset:offset+4],'big')
        size=144000*320//48000+((header>>9)&1)
        # A zero-data Layer III frame has empty granules with global_gain=0.
        source.write_bytes(data[:offset]+data[offset:offset+4]+bytes(size-4)+data[offset:])
        digest=hashlib.sha256(source.read_bytes()).digest()
        result=self.engine.normalize(source,self.output('-empty-out.mp3'),Settings(-23,-1))
        self.assertEqual(result.mode,'Direct gain')
        self.assertTrue(any('empty MP3 blocks' in w for w in result.warnings))
        self.assert_constant_gain(source,result,2e-6)
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(),digest)
        self.assertEqual(non_audio_digest(source),non_audio_digest(result.destination))

    def test_mp3_nonempty_gain_floor_is_still_rejected(self):
        from openlufs.mp3 import silent_clamp_count
        from mutagen.mp3 import MP3
        source=self.output('-nonempty.mp3')
        self.engine.run(['-y','-i',self.source,'-c:a','libmp3lame','-b:a','320k',source])
        data=source.read_bytes(); offset=MP3(source).info.frame_offset
        header=int.from_bytes(data[offset:offset+4],'big'); size=144000*320//48000+((header>>9)&1)
        frame=bytearray(data[offset:offset+4]+bytes(size-4))
        # Set part2_3_length=1 while leaving global_gain=0 in the first granule.
        bit=4*8+20+11; frame[bit//8]|=1<<(7-bit%8)
        source.write_bytes(data[:offset]+frame+data[offset:])
        from unittest.mock import patch
        from types import SimpleNamespace
        # Inspect the intentionally crafted frame instead of letting Mutagen
        # resynchronize past its synthetic one-bit payload.
        with patch('openlufs.mp3.MP3',return_value=SimpleNamespace(info=SimpleNamespace(frame_offset=offset))):
            with self.assertRaisesRegex(ValueError,'non-silent block'):
                silent_clamp_count(source,source,-1,1)

    def test_mp3_vbr_bitrate_mode_and_frame_sizes_retained(self):
        source=self.output('-vbr.mp3')
        self.engine.run(['-y','-i',self.source,'-c:a','libmp3lame','-q:a','2',source])
        result=self.engine.normalize(source,self.output('.mp3'),Settings(-18,-1))
        self.assertEqual(result.before.bitrate,result.after.bitrate)
        self.assertEqual(result.before.bitrate_mode,result.after.bitrate_mode)
        self.assertEqual(source.stat().st_size,Path(result.destination).stat().st_size)
        self.assert_constant_gain(source,result,2e-6)

    def test_mp3_peak_safe_gain_steps_do_not_limit(self):
        source=self.output('-peaks.mp3')
        self.engine.run(['-y','-i',self.transient,'-c:a','libmp3lame','-b:a','320k',source])
        result=self.engine.normalize(source,self.output('.mp3'),Settings(-10,-1))
        self.assertLess(result.after.integrated,-10.8)
        self.assertLessEqual(result.after.true_peak,-1)
        self.assertTrue(any('headroom' in w for w in result.warnings))
        self.assert_constant_gain(source,result,2e-6)

    def test_aac_m4a_keeps_all_non_audio_atoms(self):
        from mutagen.mp4 import MP4
        source=self.output('-source.m4a')
        self.engine.run(['-y','-i',self.source,'-c:a','aac','-b:a','256k',source])
        tags=MP4(source); tags['\xa9nam']=['Original AAC title']; tags['----:com.openlufs:cue']=[b'private payload']; tags.save()
        result=self.engine.normalize(source,self.output('.m4a'),Settings(-20,-1))
        self.assertEqual(result.mode,'Direct gain')
        self.assertEqual(non_audio_digest(source),non_audio_digest(result.destination))
        self.assertEqual(MP4(result.destination)['----:com.openlufs:cue'],[b'private payload'])
        self.assert_constant_gain(source,result,3e-6)

    def test_raw_aac_keeps_original_format(self):
        source=self.output('-source.aac')
        self.engine.run(['-y','-i',self.source,'-c:a','aac','-b:a','192k',source])
        result=self.engine.normalize(source,self.output('.aac'),Settings(-20,-1))
        self.assertEqual(result.mode,'Direct gain')
        self.assertEqual(source.stat().st_size,Path(result.destination).stat().st_size)
        self.assert_constant_gain(source,result,3e-6)

    def test_wav_unknown_chunks_and_id3_are_unchanged(self):
        source=self.output('-source.wav'); tone(source)
        tags=WAVE(source); tags.add_tags(); tags.tags.add(TIT2(encoding=3,text=['Original']))
        tags.tags.add(PRIV(owner='cue',data=b'private')); tags.tags.add(TXXX(encoding=3,desc='REPLAYGAIN_TRACK_GAIN',text=['+4 dB'])); tags.save()
        raw=source.read_bytes(); extra=b'XTRA'+struct.pack('<I',16)+b'unknown metadata'
        raw=raw+extra; raw=raw[:4]+struct.pack('<I',len(raw)-8)+raw[8:]; source.write_bytes(raw)
        result=self.engine.normalize(source,self.output('.wav'),Settings(-20,-1))
        before=source.read_bytes(); after=Path(result.destination).read_bytes()
        offset,size=pcm_payload(source)
        self.assertEqual(before[:offset],after[:offset])
        self.assertEqual(before[offset+size:],after[offset+size:])
        self.assertIn('TXXX:REPLAYGAIN_TRACK_GAIN',WAVE(result.destination).tags)

    def test_flac_metadata_blocks_and_24_bits_retained(self):
        from mutagen.flac import FLAC,Picture
        source=self.output('-source.flac')
        self.engine.run(['-y','-i',self.source,'-sample_fmt','s32','-bits_per_raw_sample','24',source])
        tags=FLAC(source); tags['title']='Artwork test'; tags['replaygain_track_gain']='+6 dB'
        picture=Picture(); picture.type=3; picture.mime='image/png'; picture.data=(ROOT/'assets/mark.png').read_bytes(); tags.add_picture(picture); tags.save()
        result=self.engine.normalize(source,self.output('.flac'),Settings(-20,-1))
        self.assertEqual(result.after.bits,24)
        old=[block for block in flac_parts(source)[1] if block[0] not in {0,3}]
        new=[block for block in flac_parts(result.destination)[1] if block[0] not in {0,3}]
        self.assertEqual(old,new)
        self.assertEqual(FLAC(result.destination).pictures[0].data,picture.data)
        self.assert_constant_gain(source,result,2/2**23)

    def test_aiff_24_bit_and_metadata_retained(self):
        from mutagen.aiff import AIFF
        source=self.output('-source.aiff')
        self.engine.run(['-y','-i',self.source,'-c:a','pcm_s24be',source])
        tags=AIFF(source); tags.add_tags(); tags.tags.add(PRIV(owner='cue',data=b'AIFF cue')); tags.save()
        result=self.engine.normalize(source,self.output('.aiff'),Settings(-20,-1))
        self.assertEqual(result.after.bits,24)
        offset,size=pcm_payload(source); before=source.read_bytes(); after=Path(result.destination).read_bytes()
        self.assertEqual(before[:offset],after[:offset]); self.assertEqual(before[offset+size:],after[offset+size:])
        self.assert_constant_gain(source,result,2/2**23)

    def test_no_conversion_or_unsupported_lossy_encode(self):
        with self.assertRaisesRegex(ValueError,'original file format'):
            self.engine.normalize(self.source,self.output('.flac'))
        source=self.output('-unsupported.ogg')
        self.engine.run(['-y','-i',self.source,'-c:a','libvorbis',source])
        dest=self.output('.ogg')
        with self.assertRaisesRegex(ValueError,'No verified lossless'):
            self.engine.normalize(source,dest)
        self.assertFalse(dest.exists())

    def test_measurement_against_independent_ebur128(self):
        m=self.engine.analyze(self.source)
        text=self.engine.run(['-i',self.source,'-af','ebur128=peak=true','-f','null','-']).split('Summary:')[-1]
        self.assertAlmostEqual(m.integrated,float(re.search(r'I:\s*([-\d.]+) LUFS',text)[1]),delta=0.15)
        self.assertAlmostEqual(m.true_peak,float(re.search(r'Peak:\s*([-\d.]+) dBFS',text)[1]),delta=0.15)

    def test_silence_and_multichannel_rejected(self):
        silent=self.output('-silent.wav'); tone(silent,0)
        with self.assertRaisesRegex(ValueError,'Silence'): self.engine.normalize(silent,self.output('.wav'))
        surround=self.output('-surround.wav'); self.engine.run(['-y','-f','lavfi','-i','anullsrc=r=48000:cl=5.1','-t','1',surround])
        with self.assertRaisesRegex(ValueError,'mono and stereo'): self.engine.analyze(surround)

    def test_no_overwrite_and_destination_race(self):
        with self.assertRaises(ValueError): self.engine.normalize(self.source,self.source)
        dest=self.output('.wav')
        def reserve(stage):
            if stage=='Verifying export': dest.write_bytes(b'external')
        with self.assertRaises(FileExistsError): self.engine.normalize(self.source,dest,Settings(-20,-1),progress=reserve)
        self.assertEqual(dest.read_bytes(),b'external')
        self.assertFalse(list(self.folder.glob('.openlufs-*')))

    def test_cancel_running_process_and_partial_cleanup(self):
        event=threading.Event(); engine=Engine(event); timer=threading.Timer(0.3,event.set); timer.start(); started=time.monotonic()
        try:
            with self.assertRaises(Cancelled): engine.run(['-re','-f','lavfi','-i','sine=duration=60','-f','null','-'])
        finally: timer.cancel()
        self.assertLess(time.monotonic()-started,3)
        event.clear(); dest=self.output('.wav')
        def progress(stage):
            if stage=='Applying gain': event.set()
        with self.assertRaises(Cancelled): engine.normalize(self.source,dest,Settings(-23,-1),progress=progress)
        self.assertFalse(dest.exists()); self.assertFalse(list(self.folder.glob('.openlufs-*')))

    def test_source_extension_collision_and_output_exclusion(self):
        root=self.output('-library'); (root/'a').mkdir(parents=True); (root/'b').mkdir()
        tone(root/'a/same.wav',seconds=1); tone(root/'b/same.wav',seconds=1)
        out=root/'exports'; out.mkdir(); tone(out/'existing.wav',seconds=1)
        files=discover([root,root/'a/same.wav'],exclude=out); self.assertEqual(len(files),2)
        planned=plan_outputs(files,out,'source'); self.assertNotEqual(planned[0][1],planned[1][1])
        self.assertEqual(plan_outputs(files,out,'source',root)[0][1],out/'a/same.wav')
        self.assertEqual(plan_outputs([Path('test.aac')],out,'source')[0][1].suffix,'.aac')

    def test_readonly_source_and_original_modified_time(self):
        import os,stat
        source=self.output('-readonly.wav'); tone(source,seconds=3)
        os.utime(source,(1600000000,1600000000)); source.chmod(stat.S_IREAD)
        try:
            result=self.engine.normalize(source,self.output('.wav'),Settings(-20,-1))
            self.assertEqual(Path(result.destination).stat().st_mtime_ns,source.stat().st_mtime_ns)
            self.assert_constant_gain(source,result)
        finally:
            source.chmod(stat.S_IREAD|stat.S_IWRITE)

    def test_16_bit_wav_flac_aiff_preserve_native_properties(self):
        for ext,codec in [('wav','pcm_s16le'),('aiff','pcm_s16be'),('flac','flac')]:
            with self.subTest(ext=ext):
                source=self.output('-native.'+ext)
                self.engine.run(['-y','-i',self.source,'-c:a',codec,'-sample_fmt','s16',source])
                before=self.engine.analyze(source)
                result=self.engine.normalize(source,self.output('.'+ext),Settings(-20,-1))
                self.assertEqual((result.after.codec,result.after.bits,result.after.sample_rate,result.after.channels),(before.codec,16,48000,2))
                self.assert_constant_gain(source,result)

    def test_nearest_safe_mp3_step_is_not_unnecessarily_reduced(self):
        source=self.output('-safe.mp3'); wav=self.output('-tone.wav'); tone(wav,0.4,4)
        self.engine.run(['-y','-i',wav,'-c:a','libmp3lame','-b:a','320k',source])
        before=self.engine.analyze(source); step=20*math.log10(2**0.25)
        settings=Settings(before.integrated+step,before.true_peak+step+0.015)
        result=self.engine.normalize(source,self.output('.mp3'),settings)
        self.assertAlmostEqual(result.gain_db,step,places=6)
        self.assertLessEqual(result.after.true_peak,settings.ceiling)

    def test_opus_gain_preserves_audio_packets_tags_and_bitrate(self):
        from mutagen.oggopus import OggOpus
        from openlufs.ogg import inspect_opus,pages,ogg_crc
        for ext in ['opus','ogg','oga']:
            with self.subTest(ext=ext):
                source=self.output('-input.'+ext)
                self.engine.run(['-y','-i',self.source,'-c:a','libopus','-b:a','192k','-f','opus',source])
                tags=OggOpus(source); tags['title']=['Original title']; tags['custom_cue']=['private cue data']; tags.save()
                before=inspect_opus(source)
                result=self.engine.normalize(source,self.output('.'+ext),Settings(-20,-1))
                after=inspect_opus(result.destination)
                self.assertEqual(before.audio_digest,after.audio_digest)
                self.assertEqual(before.comments,after.comments)
                self.assertEqual(result.before.bitrate,result.after.bitrate)
                self.assertEqual(result.mode,'Header gain')
                self.assertAlmostEqual(result.after.integrated,-20,delta=0.100001)
                self.assert_constant_gain(source,result,3e-6)
                for _,header,lacing,payload in pages(result.destination):
                    raw=bytearray(header+lacing+payload); saved=int.from_bytes(raw[22:26],'little'); raw[22:26]=bytes(4)
                    self.assertEqual(ogg_crc(raw),saved)

    def test_opus_updates_r128_references_and_retains_private_tags(self):
        from mutagen.oggopus import OggOpus
        from openlufs.ogg import inspect_opus
        source=self.output('-input.opus')
        self.engine.run(['-y','-i',self.source,'-c:a','libopus',source])
        tags=OggOpus(source); tags['R128_TRACK_GAIN']=['123']; tags['R128_ALBUM_GAIN']=['-456']; tags['PRIVATE']=['original']; tags.save()
        before=inspect_opus(source)
        result=self.engine.normalize(source,self.output('.opus'),Settings(-20,-1))
        after=inspect_opus(result.destination); steps=after.gain_q8-before.gain_q8
        exported=OggOpus(result.destination)
        self.assertEqual(exported['R128_TRACK_GAIN'],[str(123-steps)])
        self.assertEqual(exported['R128_ALBUM_GAIN'],[str(-456-steps)])
        self.assertEqual(exported['PRIVATE'],['original'])
        self.assertEqual(before.audio_digest,after.audio_digest)
        self.assertTrue(any('references were updated' in item for item in result.warnings))

    def test_additional_source_extensions_retain_their_container(self):
        for ext,kind,codec in [('wave','wav','pcm_s16le'),('aifc','aiff','pcm_f32be'),('m4b','mp4','aac'),('m4r','mp4','aac'),('mp4','mp4','aac')]:
            with self.subTest(ext=ext):
                source=self.output('-input.'+ext)
                self.engine.run(['-y','-i',self.source,'-c:a',codec,'-f',kind,source])
                result=self.engine.normalize(source,self.output('.'+ext),Settings(-20,-1))
                self.assertEqual(Path(result.destination).suffix,'.'+ext)
                self.assertEqual(result.before.codec,result.after.codec)
                self.assert_constant_gain(source,result,3e-5)

if __name__=='__main__': unittest.main()
