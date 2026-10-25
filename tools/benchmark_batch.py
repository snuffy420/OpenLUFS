"""Compare serial/parallel batches using generated audio and identical-output checks."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openlufs.batch import process_batch
from openlufs.engine import Engine
from openlufs.models import Settings
from openlufs.parallel import worker_count


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tracks',type=int,default=8)
    parser.add_argument('--seconds',type=int,default=45)
    args=parser.parse_args()
    if not 2<=args.tracks<=32 or not 2<=args.seconds<=120:parser.error('Use 2–32 tracks and 2–120 seconds.')
    work=ROOT/'.test-output';work.mkdir(exist_ok=True)
    engine=Engine()
    with tempfile.TemporaryDirectory(prefix='benchmark-',dir=work) as directory:
        folder=Path(directory);reference=folder/'reference.wav'
        engine.run(['-y','-f','lavfi','-i',f'anoisesrc=color=pink:amplitude=0.25:sample_rate=48000:duration={args.seconds}:seed=420',
                    '-ac','2','-c:a','pcm_s24le',reference])
        sources=[]
        profiles=[('.wav',['-c:a','pcm_s24le']),('.flac',['-c:a','flac','-sample_fmt','s32','-bits_per_raw_sample','24']),
                  ('.mp3',['-c:a','libmp3lame','-b:a','320k']),('.m4a',['-c:a','alac','-sample_fmt','s32p','-bits_per_raw_sample','24'])]
        templates=[]
        for index,(extension,encoding) in enumerate(profiles):
            source=folder/f'template-{index}{extension}'
            engine.run(['-y','-i',reference,*encoding,source]);templates.append(source)
        for index in range(args.tracks):
            template=templates[index%4];source=folder/(f'track-{index:02d}'+template.suffix)
            shutil.copyfile(template,source);sources.append(source)
        timings={};outputs={}
        for name,jobs in [('serial',1),('parallel',None)]:
            planned=[(source,folder/name/source.name) for source in sources]
            started=time.perf_counter()
            results,errors=process_batch(planned,Settings(-18,-1),threading.Event(),workers=jobs)
            timings[name]=time.perf_counter()-started
            if errors or len(results)!=len(sources):raise RuntimeError(str(errors))
            outputs[name]=[result.destination for result in results]
        def audio_hash(path):
            return engine.run(['-v','error','-i',path,'-map','0:a:0','-c:a','pcm_f32le','-f','hash','-hash','sha256','-']).strip()
        identical=all(audio_hash(a)==audio_hash(b) for a,b in zip(outputs['serial'],outputs['parallel']))
        if not identical:raise RuntimeError('Serial and parallel audio differed.')
        report={'tracks':len(sources),'seconds_per_track':args.seconds,'workers':worker_count(len(sources)),
                'serial_seconds':round(timings['serial'],3),'parallel_seconds':round(timings['parallel'],3),
                'speedup':round(timings['serial']/timings['parallel'],2),'decoded_audio_identical':identical}
        (work/'benchmark-latest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))


if __name__=='__main__':main()
