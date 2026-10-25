"""Real ALAC exports preserve codec, storage depth, samples and MP4 user metadata."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from dataclasses import replace
from mutagen.mp4 import MP4,MP4Cover
from openlufs.engine import Engine
from openlufs.models import Settings
from openlufs.render_formats import atoms,box
from test_audio import tone,decode,WORK,ROOT


class AlacTests(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='alac-',dir=WORK)
        self.root=Path(self.temp.name);self.engine=Engine()

    def tearDown(self):self.temp.cleanup()

    def source(self,bits=24,rate=44100,channels=2,transient=False,ext='.m4a',chapters=False):
        wav=self.root/'reference.wav';tone(wav,.05 if transient else .25,4,rate=rate,channels=channels,transient=transient)
        source=self.root/('source'+ext)
        extra=[]
        if chapters:
            metadata=self.root/'chapters.txt'
            metadata.write_text(';FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=2000\ntitle=Intro\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=2000\nEND=4000\ntitle=Main\n',encoding='utf-8')
            extra=['-i',metadata,'-map','0:a:0','-map_chapters','1']
        self.engine.run(['-y','-i',wav,*extra,'-af','volume=-0.137dB:precision=double','-c:a','alac',
                         '-sample_fmt','s16p' if bits==16 else 's32p','-bits_per_raw_sample',str(bits),'-f','mp4',source])
        tags=MP4(source);tags['©nam']=['ALAC reference'];tags['©ART']=['Test artist']
        tags['----:com.openlufs:cue']=[b'private cue data']
        tags['covr']=[MP4Cover((ROOT/'assets/mark.png').read_bytes(),imageformat=MP4Cover.FORMAT_PNG)]
        tags.save()
        with source.open('ab') as out:out.write(box(b'uuid',b'0123456789abcdef'+b'private root metadata'))
        return source

    def metadata(self,path):
        result=[]
        for kind,data,h in atoms(Path(path).read_bytes()):
            if kind==b'uuid':result.append(data)
            if kind==b'moov':
                result.extend(child for name,child,_ in atoms(data[h:]) if name in {b'udta',b'meta',b'uuid'})
        return result

    def assert_preserved(self,source,result,bits,rate,channels):
        self.assertEqual((result.after.codec,result.after.bits,result.after.sample_rate,result.after.channels),('alac',bits,rate,channels))
        self.assertEqual(dict(MP4(source).tags),dict(MP4(result.destination).tags))
        self.assertEqual(self.metadata(source),self.metadata(result.destination))
        self.assertEqual(len(decode(source)),len(decode(result.destination)))
        self.assertLessEqual(result.after.true_peak,-1)

    def test_constant_gain_depth_rate_channels_and_metadata(self):
        for bits,rate,channels in [(16,44100,1),(16,48000,2),(24,44100,2),(24,96000,1)]:
            with self.subTest(bits=bits,rate=rate,channels=channels):
                source=self.source(bits,rate,channels)
                checksum=hashlib.sha256(source.read_bytes()).digest()
                result=self.engine.normalize(source,self.root/f'output-{bits}-{rate}.m4a',Settings(-24,-1))
                self.assert_preserved(source,result,bits,rate,channels)
                self.assertEqual(result.mode,'Gain only')
                self.assertFalse(result.processing['reencoded'])
                self.assertAlmostEqual(result.after.integrated,-24,delta=.100001)
                gain=10**(result.gain_db/20)
                error=max(abs(b-a*gain) for a,b in zip(decode(source),decode(result.destination)))
                self.assertLess(error,2/(2**(bits-1)))
                self.assertEqual(hashlib.sha256(source.read_bytes()).digest(),checksum)

    def test_limiter_retains_alac_depth_and_chapters(self):
        for bits in [16,24]:
            with self.subTest(bits=bits):
                source=self.source(bits,transient=True,chapters=True)
                self.assertEqual([c.title for c in MP4(source).chapters],['Intro','Main'])
                result=self.engine.normalize(source,self.root/f'limited-{bits}.m4a',Settings(-10,-1,allow_limiter=True))
                self.assert_preserved(source,result,bits,44100,2)
                self.assertAlmostEqual(result.after.integrated,-10,delta=.100001)
                self.assertTrue(result.processing['limited']);self.assertFalse(result.processing['reencoded'])
                self.assertFalse(any('lossy generation' in note for note in result.warnings))
                self.assertEqual([(c.start,c.title) for c in MP4(source).chapters],[(c.start,c.title) for c in MP4(result.destination).chapters])

    def test_mp4_metadata_keeps_media_offsets_and_bytes(self):
        from openlufs.render_formats import file_atoms,mp4_metadata
        source=self.source();rendered=self.root/'rendered.m4a'
        self.engine.run(['-y','-i',source,'-map','0:a:0','-map_metadata','-1','-c:a','alac','-sample_fmt','s32p','-bits_per_raw_sample','24',rendered])
        media=[entry for entry in file_atoms(rendered) if entry[0]==b'mdat']
        before=rendered.read_bytes()
        mp4_metadata(source,rendered)
        after=rendered.read_bytes()
        self.assertEqual(media,[entry for entry in file_atoms(rendered) if entry[0]==b'mdat'])
        for _,position,size,_,_ in media:self.assertEqual(before[position:position+size],after[position:position+size])
        self.assertEqual(self.metadata(source),self.metadata(rendered))

    def test_peak_only_safe_copy_is_byte_identical(self):
        source=self.source()
        result=self.engine.normalize(source,self.root/'copy.m4a',Settings(-10,-1,allow_limiter=True,normalize_lufs=False))
        self.assertEqual(result.mode,'Unchanged')
        self.assertEqual(source.read_bytes(),Path(result.destination).read_bytes())

    def test_mp4_container_extensions_are_retained(self):
        original=self.source(16)
        for extension in ['.m4b','.m4r','.mp4']:
            with self.subTest(extension=extension):
                source=self.root/('input'+extension);shutil.copyfile(original,source)
                result=self.engine.normalize(source,self.root/('output'+extension),Settings(-24,-1))
                self.assertEqual(Path(result.destination).suffix,extension)
                self.assert_preserved(source,result,16,44100,2)

    def test_unsupported_alac_depth_is_rejected(self):
        source=self.source()
        before=self.engine.analyze(source)
        for bits in [20,32]:
            destination=self.root/f'unsupported-{bits}.m4a'
            with self.assertRaisesRegex(ValueError,'16-bit and 24-bit'):
                self.engine.normalize(source,destination,Settings(-24,-1),replace(before,bits=bits))
            self.assertFalse(destination.exists())


if __name__=='__main__':unittest.main()
