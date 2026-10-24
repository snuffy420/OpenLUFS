"""End-to-end matching/limiting tests using actual codecs and container metadata."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from mutagen.id3 import TIT2,PRIV
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.oggopus import OggOpus
from openlufs.engine import Engine
from openlufs.models import Settings
from openlufs.containers import non_audio_digest,pcm_payload
from openlufs.render_formats import atoms,box
from test_audio import tone,WORK,decode


class MatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORK.mkdir(exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='matching-',dir=WORK)
        cls.root=Path(cls.temp.name);cls.engine=Engine()
        cls.reference=cls.root/'transients.wav';tone(cls.reference,.05,6,transient=True)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def result(self,source,label):
        checksum=hashlib.sha256(source.read_bytes()).digest()
        r=self.engine.normalize(source,self.root/(label+source.suffix),Settings(-10,-1,allow_limiter=True))
        self.assertLessEqual(abs(r.after.integrated+10),.100001)
        self.assertLessEqual(r.after.true_peak,-1)
        self.assertEqual((r.before.codec,r.before.sample_rate,r.before.channels),(r.after.codec,r.after.sample_rate,r.after.channels))
        self.assertTrue(r.processing['limited'])
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(),checksum)
        return r

    def test_pcm_and_flac_limit_at_original_depth_and_length(self):
        for ext,codec,bits in [('wav','pcm_s16le',16),('wav','pcm_s24le',24),('wav','pcm_f32le',32),('aiff','pcm_s16be',16),('aiff','pcm_s24be',24),('aifc','pcm_f32be',32),('flac','flac',16),('flac','flac',24)]:
            with self.subTest(ext=ext,codec=codec,bits=bits):
                source=self.root/f'input-{codec}-{bits}.{ext}'
                args=['-c:a',codec]
                if ext=='flac':args+=['-sample_fmt','s16' if bits==16 else 's32','-bits_per_raw_sample',str(bits)]
                if ext=='aifc':args+=['-f','aiff']
                self.engine.run(['-y','-i',self.reference,*args,source])
                if ext=='flac':
                    tags=FLAC(source);tags['private']=['retained'];tags.save()
                r=self.result(source,f'output-{codec}-{bits}')
                self.assertEqual(r.after.bits,bits)
                self.assertFalse(r.processing['reencoded'])
                self.assertEqual(len(decode(source)),len(decode(r.destination)))
                if ext=='flac':self.assertEqual(FLAC(r.destination)['private'],['retained'])
                else:
                    old_offset,size=pcm_payload(source);new_offset,new_size=pcm_payload(r.destination)
                    old=source.read_bytes();new=Path(r.destination).read_bytes()
                    self.assertEqual(old_offset,new_offset);self.assertEqual(size,new_size)
                    self.assertEqual(old[:old_offset],new[:old_offset]);self.assertEqual(old[old_offset+size:],new[old_offset+size:])

    def test_mp3_cbr_and_vbr_matching_preserves_tags(self):
        for mode,encoding in [('320',['-b:a','320k']),('128',['-b:a','128k']),('vbr',['-q:a','2'])]:
            with self.subTest(mode=mode):
                source=self.root/f'input-{mode}.mp3'
                self.engine.run(['-y','-i',self.reference,'-c:a','libmp3lame',*encoding,source])
                tags=MP3(source);tags.tags.add(TIT2(encoding=3,text=['Original title']));tags.tags.add(PRIV(owner='private.cue',data=b'unchanged'));tags.save()
                r=self.result(source,'output-'+mode)
                self.assertTrue(r.processing['reencoded'])
                self.assertEqual(non_audio_digest(source),non_audio_digest(r.destination))
                if mode!='vbr':self.assertEqual(r.after.bitrate,int(mode)*1000)
                else:self.assertEqual(r.after.bitrate_mode,'VBR')

    def test_aac_raw_and_mp4_metadata(self):
        for ext in ['aac','m4a','m4b','m4r','mp4']:
            with self.subTest(ext=ext):
                source=self.root/('input.'+ext)
                self.engine.run(['-y','-i',self.reference,'-c:a','aac','-b:a','192k','-f','adts' if ext=='aac' else 'mp4',source])
                if ext!='aac':
                    tags=MP4(source);tags['\xa9nam']=['Original title'];tags['----:com.openlufs:private']=[b'cue payload'];tags.save()
                    with source.open('ab') as f:f.write(box(b'uuid',b'1234567890123456original private metadata'))
                r=self.result(source,'output-'+ext)
                self.assertTrue(r.processing['reencoded'])
                if ext!='aac':
                    self.assertEqual(dict(MP4(source).tags),dict(MP4(r.destination).tags))
                    self.assertIn(b'original private metadata',Path(r.destination).read_bytes())

    def test_opus_matching_retains_comments(self):
        for ext in ['opus','ogg','oga']:
            with self.subTest(ext=ext):
                source=self.root/('input.'+ext)
                self.engine.run(['-y','-i',self.reference,'-c:a','libopus','-b:a','192k','-f','opus',source])
                tags=OggOpus(source);tags['title']=['Original title'];tags['private_cue']=['value'];tags.save()
                r=self.result(source,'output-'+ext)
                self.assertTrue(r.processing['reencoded'])
                self.assertEqual(dict(OggOpus(source).tags),dict(OggOpus(r.destination).tags))

    def test_limiter_leaves_quieter_passages_at_constant_gain(self):
        source=self.root/'quiet-passages.wav'
        self.engine.run(['-y','-i',self.reference,'-c:a','pcm_f32le',source])
        r=self.result(source,'quiet-passages-output')
        old,new=decode(source),decode(r.destination)
        gain=10**(r.gain_db/20)
        # The transient starts each half second. Check well after the release,
        # and before the next lookahead window, on both linked channels.
        start=int(.2*48000)*2;end=int(.3*48000)*2
        self.assertLess(max(abs(new[i]-old[i]*gain) for i in range(start,end)),.0003)

    def test_peak_only_does_not_raise_quiet_passages_toward_lufs(self):
        source=self.root/'peak-only.wav';tone(source,.05,4,transient=True)
        r=self.engine.normalize(source,self.root/'peak-only-output.wav',Settings(-6,-6,allow_limiter=True,normalize_lufs=False))
        self.assertEqual(r.gain_db,0)
        self.assertFalse(r.processing['matching']);self.assertTrue(r.processing['limited'])
        self.assertLessEqual(r.after.true_peak,-6)
        self.assertLessEqual(r.after.integrated,r.before.integrated+.05)
        old,new=decode(source),decode(r.destination)
        start=int(.2*48000)*2;end=int(.3*48000)*2
        self.assertLess(max(abs(old[i]-new[i]) for i in range(start,end)),.0001)

    def test_peak_only_copies_safe_source_and_both_disabled_are_rejected(self):
        source=self.root/'already-safe.wav';tone(source,.25,2)
        r=self.engine.normalize(source,self.root/'already-safe-out.wav',Settings(-6,-1,allow_limiter=True,normalize_lufs=False))
        self.assertEqual(source.read_bytes(),Path(r.destination).read_bytes());self.assertEqual(r.mode,'Unchanged')
        with self.assertRaisesRegex(ValueError,'Enable LUFS'):
            self.engine.normalize(source,self.root/'disabled.wav',Settings(normalize_lufs=False))
        self.assertFalse((self.root/'disabled.wav').exists())

    def test_direct_gain_is_used_when_it_already_matches(self):
        source=self.root/'safe.wav';tone(source,.25,4)
        r=self.engine.normalize(source,self.root/'safe-output.wav',Settings(-20,-1,allow_limiter=True))
        self.assertFalse(r.processing['reencoded']);self.assertFalse(r.processing['limited'])
        self.assertEqual(r.mode,'Gain only')
        self.assertLessEqual(abs(r.after.integrated+20),.100001)

if __name__=='__main__':unittest.main()
