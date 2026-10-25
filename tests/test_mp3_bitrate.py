"""Bitrate modes must agree in analysis, direct gain and matching renders."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest
from mutagen.mp3 import MP3,BitrateMode
from mutagen.id3 import TIT2
from openlufs.engine import Engine
from openlufs.mp3 import bitrate_properties,mp3_layout
from openlufs.render_formats import encoding_profile
from openlufs.models import Settings
from test_audio import WORK,tone


class Mp3BitrateTests(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix="mp3-bitrate-",dir=WORK)
        self.root=Path(self.temp.name);self.engine=Engine()

    def tearDown(self):self.temp.cleanup()

    def synthetic(self,rates,padding=False,info_frame=False):
        tables=[0,32,40,48,56,64,80,96,112,128,160,192,224,256,320]
        frames=[]
        for i,rate in enumerate(rates):
            pad=(i%2) if padding else 0
            header=0xffe00000|(3<<19)|(1<<17)|(1<<16)|(tables.index(rate)<<12)|(pad<<9)
            frame=bytearray((144000*rate//44100)+pad)
            frame[:4]=header.to_bytes(4,"big")
            if info_frame and i==0:frame[36:40]=b"Info"
            frames.append(frame)
        path=self.root/"frames.mp3";path.write_bytes(b"".join(frames))
        return path,SimpleNamespace(frame_offset=0,bitrate=rates[0]*1000,bitrate_mode=BitrateMode.UNKNOWN)

    def test_padding_does_not_turn_cbr_into_vbr(self):
        source,info=self.synthetic([320]*6,padding=True)
        self.assertEqual(bitrate_properties(source,info),(320000,"CBR"))

    def test_ordinary_first_frame_is_not_discarded(self):
        source,info=self.synthetic([128,320,320])
        self.assertEqual(mp3_layout(source,info)[0],{128,320})
        self.assertEqual(bitrate_properties(source,info)[1],"VBR")

    def test_actual_info_frame_is_excluded(self):
        source,info=self.synthetic([128,320,320],info_frame=True)
        self.assertEqual(bitrate_properties(source,info),(320000,"CBR"))

    def test_truncation_stays_unknown_and_cannot_select_a_renderer(self):
        source,info=self.synthetic([320]*2)
        source.write_bytes(source.read_bytes()[:-1])
        self.assertEqual(bitrate_properties(source,info)[1],"UNKNOWN")
        with self.assertRaisesRegex(ValueError,"truncated"):
            bitrate_properties(source,info,strict=True)

    def test_explicit_vbr_and_abr_are_preserved(self):
        for mode in [BitrateMode.VBR,BitrateMode.ABR]:
            info=SimpleNamespace(bitrate=190000,bitrate_mode=mode)
            with patch("openlufs.mp3.mp3_layout") as scan:
                self.assertEqual(bitrate_properties(self.root/"unused.mp3",info),(190000,str(mode).replace('BitrateMode.','')))
                scan.assert_not_called()

    def test_headerless_cbr_analysis_direct_gain_and_renderer_agree(self):
        wav=self.root/"reference.wav";tone(wav,seconds=3,rate=44100)
        for kbps in [128,320]:
            with self.subTest(kbps=kbps):
                source=self.root/f"cbr-{kbps}.mp3"
                self.engine.run(['-y','-i',wav,'-c:a','libmp3lame','-b:a',f'{kbps}k','-write_xing','0',source])
                tags=MP3(source);tags.tags.add(TIT2(encoding=3,text=['Test title']));tags.save()
                self.assertEqual(MP3(source).info.bitrate_mode,BitrateMode.UNKNOWN)
                before=self.engine.analyze(source)
                self.assertEqual((before.bitrate,before.bitrate_mode),(kbps*1000,"CBR"))
                args,profile,notes=encoding_profile(source,before,self.engine)
                self.assertEqual(profile['mode'],"CBR");self.assertIn(f'{kbps}k',args)
                result=self.engine.normalize(source,self.root/f"output-{kbps}.mp3",Settings(-24,-1),before)
                self.assertEqual(result.after.bitrate,kbps*1000)
                self.assertEqual(result.after.bitrate_mode,"CBR")
                self.assertEqual(str(MP3(result.destination).tags['TIT2']),"Test title")

    def test_headerless_vbr_is_not_misclassified_from_first_frame(self):
        wav=self.root/"reference.wav";tone(wav,seconds=3,rate=44100,transient=True)
        source=self.root/"vbr.mp3"
        self.engine.run(['-y','-i',wav,'-c:a','libmp3lame','-q:a','2','-write_xing','0',source])
        self.assertEqual(MP3(source).info.bitrate_mode,BitrateMode.UNKNOWN)
        before=self.engine.analyze(source)
        self.assertEqual(before.bitrate_mode,"VBR")
        _,profile,_=encoding_profile(source,before,self.engine)
        self.assertEqual(profile['mode'],"VBR")


if __name__=="__main__":unittest.main()
