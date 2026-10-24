"""Temporary, actual-output waveform previews with synchronized views."""
from pathlib import Path
import math
import shutil
import tempfile
import threading
from PyQt6.QtCore import Qt,QThread,pyqtSignal,QRectF,QPointF
from PyQt6.QtGui import QColor,QPainter,QPen,QPainterPath
from PyQt6.QtWidgets import (QDialog,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,
    QPushButton,QSlider,QProgressBar,QMessageBox,QSizePolicy)
from .engine import Engine,Cancelled
from .analysis_cache import source_stamp
from .waveforms import WaveformData,decode_waveforms,spectral_display


class PreviewWorker(QThread):
    def __init__(self,source,settings,folder,cache=None):
        super().__init__();self.source=Path(source);self.settings=settings;self.folder=Path(folder)
        self.cancel=threading.Event();self.cache=cache;self.outcome=None

    def run(self):
        try:
            stamp=source_stamp(self.source)
            engine=Engine(self.cancel)
            before=self.cache.measure(self.source,engine.analyze) if self.cache is not None else engine.analyze(self.source)
            required=before.duration*before.sample_rate*before.channels*4*9+32*1024**2
            if shutil.disk_usage(self.folder).free<required:
                raise ValueError(f'Preview needs approximately {required/1024**3:.1f} GB of temporary disk space.')
            destination=self.folder/('preview'+self.source.suffix)
            result=engine.normalize(self.source,destination,self.settings,before)
            original=decode_waveforms(engine,self.source,self.folder,'original',before)
            processed=decode_waveforms(engine,destination,self.folder,'processed',result.after)
            if source_stamp(self.source)!=stamp:raise ValueError('Source changed while building the preview; reopen it.')
            self.outcome={'result':result,'original':original,'processed':processed}
        except Cancelled:self.outcome={'cancelled':True}
        except Exception as error:self.outcome={'error':str(error)}


class WaveformCanvas(QWidget):
    def __init__(self,title,parent=None):
        super().__init__(parent);self.title=title;self.data=None;self.waveform_style='Normal';self.start=0.;self.seconds=0.;self.scale=1.;self._cache={}
        self.setMinimumHeight(140)
        self.setToolTip('Both views share one linear amplitude scale. Full-track envelopes retain every decoded sample peak in each display bin. RGB uses low/mid/high RMS energy for color; 3-band combines blue bass, orange mids and white highs within one waveform per channel.')

    def set_view(self,start,seconds,style):
        self.start=start;self.seconds=seconds;self.waveform_style=style;self.update()

    def envelopes(self,channel,band,bins,energy=False):
        start=int(self.start*self.data.rate);end=min(self.data.frames,int((self.start+self.seconds)*self.data.rate))
        key=(start,end,bins,channel,band,energy)
        if key not in self._cache:
            if len(self._cache)>36:self._cache.clear()
            self._cache[key]=self.data.envelope(start,end,bins,channel,band,energy)
        return self._cache[key]

    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor('#141b1e'))
        painter.setPen(QColor('#e6eceb'));painter.drawText(14,23,self.title)
        if self.data is None:return
        area=QRectF(72,38,max(1,self.width()-88),max(1,self.height()-65))
        lane_height=area.height()/self.data.channels
        bins=max(1,int(area.width()*self.devicePixelRatioF()))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing,False)
        for channel in range(self.data.channels):
            middle=area.top()+(channel+.5)*lane_height;half=lane_height*.43/self.scale
            painter.setPen(QColor('#344145'));painter.drawLine(QPointF(area.left(),middle),QPointF(area.right(),middle))
            name=('L' if channel==0 else 'R') if self.data.channels==2 else ('Mono' if self.data.channels==1 else str(channel+1))
            painter.setPen(QColor('#8a9b9b'));painter.drawText(12,int(middle),name)
            lower,upper=self.envelopes(channel,'full',bins)
            rgb=layers=None
            if self.waveform_style!='Normal':
                import numpy as np
                rms=np.stack([self.envelopes(channel,key,bins,True)[2] for key in ['low','mid','high']],axis=1)
                rgb,layers=spectral_display(rms)
            count=len(lower);step=area.width()/count
            sample_view=(min(self.data.frames,int((self.start+self.seconds)*self.data.rate))-int(self.start*self.data.rate))<area.width()
            previous=None
            for index,(minimum,maximum) in enumerate(zip(lower,upper)):
                color=QColor('#65e4bd') if self.waveform_style=='Normal' else QColor(*map(int,rgb[index])) if self.waveform_style=='RGB' else QColor('#328cfa')
                x=area.left()+(index+.5)*step
                painter.setPen(QPen(color,max(.7,step) if not sample_view else 1))
                if sample_view:
                    # At sample zoom retain the actual connected samples in every style.
                    point=QPointF(x,middle-float(maximum)*half)
                    if previous is not None:painter.drawLine(previous,point)
                    previous=point
                else:
                    painter.drawLine(QPointF(x,middle-float(maximum)*half),QPointF(x,middle-float(minimum)*half))
                    if self.waveform_style=='3-band':
                        # Nested spectral colors stay inside the measured full envelope.
                        # These are relative energy indicators, not isolated-band amplitudes.
                        for fraction,shade in zip(layers[index],['#f2a34b','#f1f5fa']):
                            if fraction<.015:continue
                            painter.setPen(QPen(QColor(shade),max(.7,step)))
                            center=(float(maximum)+float(minimum))*.5
                            radius=(float(maximum)-float(minimum))*.5
                            painter.drawLine(QPointF(x,middle-(center+radius*fraction)*half),QPointF(x,middle-(center-radius*fraction)*half))
            painter.setPen(QPen(QColor('#52625d'),1,Qt.PenStyle.DotLine))
            for sign in [-1,1]:painter.drawLine(QPointF(area.left(),middle+sign*half),QPointF(area.right(),middle+sign*half))
        painter.setPen(QColor('#8a9b9b'))
        for index in range(6):
            time=self.start+self.seconds*index/5
            painter.drawText(QRectF(min(self.width()-54,max(0,area.left()+index*area.width()/5-27)),area.bottom()+7,54,18),Qt.AlignmentFlag.AlignCenter,f'{int(time)//60}:{time%60:04.1f}')


class PreviewDialog(QDialog):
    def __init__(self,source,settings,parent=None,cache=None,temp_parent=None,style='Normal'):
        super().__init__(parent);self.setWindowTitle('OpenLUFS · Waveform preview');self.setMinimumSize(700,530)
        available=self.screen().availableGeometry();self.resize(min(1160,available.width()-60),min(820,available.height()-60))
        self.temporary=tempfile.TemporaryDirectory(prefix='.OpenLUFS-preview-',dir=temp_parent)
        self.temp_path=Path(self.temporary.name);self.cleaned=False;self.close_pending=False;self.datasets=[];self.duration=0
        layout=QVBoxLayout(self);layout.setContentsMargins(20,20,20,18);layout.setSpacing(12)
        top=QHBoxLayout();title=QLabel(Path(source).name);title.setObjectName('PageTitle');title.setWordWrap(True);title.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred);top.addWidget(title,1)
        self.style_combo=QComboBox();self.style_combo.addItems(['Normal','RGB','3-band']);self.style_combo.setCurrentText(style);top.addWidget(self.style_combo)
        self.zoom=QComboBox()
        for text,value in [('Full track',0),('30 seconds',30),('10 seconds',10),('1 second',1),('100 ms',.1),('10 ms',.01),('1 ms',.001)]:self.zoom.addItem(text,value)
        top.addWidget(self.zoom);layout.addLayout(top)
        self.summary=QLabel('Processing preview…');self.summary.setWordWrap(True);layout.addWidget(self.summary)
        self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.setFixedHeight(5);self.progress.setTextVisible(False);layout.addWidget(self.progress)
        self.original=WaveformCanvas('Original');self.processed=WaveformCanvas('Processed');layout.addWidget(self.original,1);layout.addWidget(self.processed,1)
        navigation=QHBoxLayout();navigation.addWidget(QLabel('Position'));self.position=QSlider(Qt.Orientation.Horizontal);self.position.setRange(0,10000);navigation.addWidget(self.position,1);layout.addLayout(navigation)
        footer=QHBoxLayout();self.hint=hint=QLabel('Shared linear scale · dotted lines = ± full scale · bands: low <200 Hz, mid 200–2500 Hz, high >2500 Hz');hint.setObjectName('Muted');hint.setWordWrap(True);footer.addWidget(hint,1)
        close=QPushButton('Close preview');close.clicked.connect(self.reject);footer.addWidget(close);layout.addLayout(footer)
        for control in [self.style_combo,self.zoom]:control.currentIndexChanged.connect(self.update_views)
        self.position.valueChanged.connect(self.update_views)
        self.worker=PreviewWorker(source,settings,self.temp_path,cache);self.worker.finished.connect(self.ready);self.worker.start()

    def update_views(self,*args):
        if not self.datasets:return
        legend={'Normal':'Green: full waveform', 'RGB':'Red: bass · green: mids · blue: highs', '3-band':'Blue: bass · orange: mids · white: highs (layered)'}
        self.hint.setText('Shared linear scale · dotted lines = ± full scale · '+legend[self.style_combo.currentText()])
        seconds=min(self.duration,float(self.zoom.currentData()) or self.duration)
        start=max(0,self.duration-seconds)*self.position.value()/10000
        self.position.setEnabled(seconds<self.duration)
        for canvas in [self.original,self.processed]:canvas.set_view(start,seconds,self.style_combo.currentText())

    def ready(self):
        outcome=self.worker.outcome or {'error':'Preview did not finish.'}
        if self.close_pending or outcome.get('cancelled'):
            self.reject();return
        if outcome.get('error'):
            self.summary.setText('Preview could not be generated: '+outcome['error']);self.progress.hide();self.cleanup();return
        try:
            for key in ['original','processed']:self.datasets.append(WaveformData(outcome[key]))
            self.original.data,self.processed.data=self.datasets
            scale=max(1.,*(data.peak for data in self.datasets))*1.03
            self.original.scale=self.processed.scale=scale
            self.duration=max(data.duration for data in self.datasets)
            low,high=outcome['original']['crossovers']
            self.hint.setText(f'Shared linear scale · dotted lines = ± full scale · low <{low:g} Hz · mid {low:g}–{high:g} Hz · high >{high:g} Hz')
            r=outcome['result'];self.result=r
            target=self.worker.settings.target;difference=r.after.integrated-target
            text=f'Original {r.before.integrated:.2f} LUFS / {r.before.true_peak:.2f} dBTP  →  Processed {r.after.integrated:.2f} LUFS / {r.after.true_peak:.2f} dBTP · {r.mode}'
            if self.worker.settings.normalize_lufs and abs(difference)>.100001:text+=f' · {abs(difference):.2f} LU '+('below' if difference<0 else 'above')+' target; not matched'
            self.summary.setText(text);self.progress.hide();self.update_views()
        except Exception as error:
            self.summary.setText('Preview could not be displayed: '+str(error));self.cleanup()

    def cleanup(self):
        if self.cleaned:return
        self.original.data=self.processed.data=None
        self.original._cache.clear();self.processed._cache.clear()
        for data in self.datasets:data.close()
        self.datasets.clear()
        self.temporary.cleanup();self.cleaned=True

    def reject(self):
        if self.worker.isRunning():
            self.close_pending=True;self.worker.cancel.set();self.summary.setText('Cancelling preview and removing temporary files…');return
        self.cleanup();super().reject()

    def closeEvent(self,event):
        if self.worker.isRunning():
            self.close_pending=True;self.worker.cancel.set();self.summary.setText('Cancelling preview and removing temporary files…');event.ignore()
        else:self.cleanup();super().closeEvent(event)
