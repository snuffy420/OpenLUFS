"""Sample-derived waveform envelopes and defined three-band analysis."""
from pathlib import Path
import numpy as np


def decode_waveforms(engine,path,folder,prefix,measurement):
    folder=Path(folder)
    paths={key:folder/f'{prefix}-{key}.f32' for key in ['full','low','mid','high']}
    low=min(200,measurement.sample_rate*.1);high=min(2500,measurement.sample_rate*.4)
    graph=f'[0:a:0]asplit=2[full][bands];[bands]acrossover=split={low} {high}:order=8th:precision=double[low][mid][high]'
    args=['-y','-threads','2','-i',path,'-filter_complex',graph]
    for key,destination in paths.items():
        args+=['-map',f'[{key}]','-c:a','pcm_f32le','-ar',measurement.sample_rate,'-f','f32le',destination]
    engine.run(args)
    size=paths['full'].stat().st_size
    if not size or size%(measurement.channels*4) or any(p.stat().st_size!=size for p in paths.values()):
        raise ValueError('Waveform sample streams did not align.')
    return {'paths':{key:str(value) for key,value in paths.items()},'rate':measurement.sample_rate,
            'channels':measurement.channels,'frames':size//(measurement.channels*4),'crossovers':[low,high]}


class WaveformData:
    def __init__(self,manifest):
        self.manifest=manifest;self.rate=manifest['rate'];self.channels=manifest['channels'];self.frames=manifest['frames']
        self.arrays={key:np.memmap(path,dtype='<f4',mode='r',shape=(self.frames,self.channels)) for key,path in manifest['paths'].items()}
        self.peak=0.
        for array in self.arrays.values():
            for start in range(0,self.frames,262144):
                self.peak=max(self.peak,float(np.max(np.abs(array[start:start+262144]))))

    @property
    def duration(self):return self.frames/self.rate

    def envelope(self,start,end,bins,channel=0,band='full',energy=False):
        start=max(0,min(self.frames-1,int(start)));end=max(start+1,min(self.frames,int(end)))
        bins=max(1,min(int(bins),end-start))
        offsets=np.linspace(0,end-start,bins+1,dtype=np.int64)[:-1]
        data=self.arrays[band][start:end,channel]
        minimum=np.minimum.reduceat(data,offsets);maximum=np.maximum.reduceat(data,offsets)
        if energy:
            counts=np.diff(np.r_[offsets,end-start])
            rms=np.sqrt(np.add.reduceat(np.square(data,dtype=np.float64),offsets)/counts)
            return minimum,maximum,rms
        return minimum,maximum

    def close(self):
        for array in self.arrays.values():array._mmap.close()
        self.arrays.clear()


def spectral_display(rms):
    """Return RGB colors and nested 3-band fractions from per-bin band RMS.

    Color uses relative power, never changes the full-band peak geometry.
    3-band draws blue full envelopes, orange mid+high interiors, white high cores.
    """
    power=np.square(np.asarray(rms,dtype=np.float64))
    total=power.sum(axis=1,keepdims=True)
    shares=np.divide(power,total,out=np.zeros_like(power),where=total>1e-24)
    brightness=np.sqrt(shares)
    brightness/=np.maximum(brightness.max(axis=1,keepdims=True),1e-12)
    rgb=np.rint(16+224*brightness).astype(np.uint8)
    rgb[total[:,0]<=1e-24]=16
    layers=np.sqrt(np.column_stack((shares[:,1]+shares[:,2],shares[:,2])))
    return rgb,layers
