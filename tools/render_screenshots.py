"""Capture the real Qt UI using generated test audio and actual processing."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEventLoop,QTimer
from PyQt6.QtGui import QFontDatabase
from openlufs.gui import MainWindow
from openlufs.theme import STYLE
from test_audio import tone
from openlufs.engine import Engine

app=QApplication([])
for font in ['C:/Windows/Fonts/segoeui.ttf','C:/Windows/Fonts/seguisb.ttf']:
    if Path(font).exists(): QFontDatabase.addApplicationFont(font)
app.setStyle('Fusion'); app.setStyleSheet(STYLE)
from unittest.mock import patch
with patch.object(MainWindow, 'load_settings'):
    window=MainWindow()
window.config_path=ROOT/'.test-output/screenshot-settings.json'
window.target.setValue(-12); window.ceiling.setValue(-1)
window.output.clear(); window.show(); app.processEvents()
window.grab().save(str(ROOT/'docs/screenshot-library.png'))
window.grab().save(str(ROOT/'docs/screenshot-titlebar.png'))
with tempfile.TemporaryDirectory(prefix='screenshots-',dir=ROOT/'.test-output') as folder:
    folder=Path(folder)
    engine=Engine()
    reference=folder/'Reference 24-bit.wav'
    temp=folder/'temporary.wav'; tone(temp,amplitude=0.25,seconds=6)
    engine.run(['-y','-i',temp,'-c:a','pcm_s24le',reference])
    tone(temp,amplitude=0.035,seconds=6)
    mp3=folder/'Quiet 320 kbps.mp3'
    engine.run(['-y','-i',temp,'-c:a','libmp3lame','-b:a','320k',mp3])
    temp.unlink()
    # Reproducible stereo rhythm with separate bass, mid and treble sections.
    import numpy as np
    import wave
    rate=48000; t=np.arange(rate*12)/rate; beat=t%.5
    kick=np.sin(2*np.pi*(58*t-9*np.exp(-beat*25)))*np.exp(-beat*14)
    bass=.18*np.sin(2*np.pi*110*t)*(t<8)
    mids=.12*np.sin(2*np.pi*740*t)*np.maximum(0,np.sin(2*np.pi*2*t))*(t>3)
    rng=np.random.default_rng(2026)
    noise=rng.standard_normal(len(t)); treble=np.r_[0,np.diff(noise)]
    hats=.035*treble*np.exp(-(t%.25)*65)*(t>7)
    signal=.32*kick+bass+mids+hats
    signal*=.38+.55*np.sin(np.pi*t/12)**2
    signal[rate*5:rate*5+8]=.96
    stereo=np.column_stack((signal,signal*.94+.015*np.sin(2*np.pi*1210*t)*(t>4)))
    transient=folder/'Rhythm study 16-bit.wav'
    with wave.open(str(transient),'wb') as audio:
        audio.setnchannels(2);audio.setsampwidth(2);audio.setframerate(rate)
        audio.writeframes(np.rint(stereo*32767).astype('<i2').tobytes())
    alac=folder/'Reference 24-bit ALAC.m4a'
    engine.run(['-y','-i',reference,'-c:a','alac','-sample_fmt','s32p','-bits_per_raw_sample','24',alac])
    window.append_files([mp3,reference,transient,alac])
    window.output.setText(str(folder/'Normalized'))
    window.target.setValue(-12)
    window.table.selectRow(2);app.processEvents()
    window.grab().save(str(ROOT/'docs/screenshot-settings.png'))
    window.limiter_enabled.setChecked(True)
    app.processEvents();window.grab().save(str(ROOT/'docs/screenshot-limiter.png'))
    window.normalize_enabled.setChecked(False)
    app.processEvents();window.grab().save(str(ROOT/'docs/screenshot-peak-only.png'))
    window.normalize_enabled.setChecked(True);window.limiter_enabled.setChecked(False)
    window.normalize()
    loop=QEventLoop()
    window.worker.finished.connect(loop.quit)
    QTimer.singleShot(60000,loop.quit)
    loop.exec(); app.processEvents()
    if window.busy(): raise SystemExit('Screenshot processing timed out')
    if '4 exported' not in window.status.text(): raise SystemExit(window.status.text())
    window.table.selectRow(3); app.processEvents()
    window.grab().save(str(ROOT/'docs/screenshot-results.png'))
    from openlufs.report_viewer import ReportDialog
    report=ReportDialog(window.report,window);report.resize(1100,730);report.show();app.processEvents()
    report.grab().save(str(ROOT/'docs/screenshot-report.png'));report.close()
    from openlufs.preview import PreviewDialog
    from openlufs.models import Settings
    preview=PreviewDialog(transient,Settings(-12,-1),window,temp_parent=folder)
    if preview.worker.isRunning():
        loop=QEventLoop();preview.worker.finished.connect(loop.quit);QTimer.singleShot(60000,loop.quit);loop.exec()
    app.processEvents()
    if preview.worker.isRunning() or preview.worker.outcome.get('error'):raise SystemExit('Preview screenshot failed')
    preview.resize(1100,750);preview.show();app.processEvents()
    for style,name in [('Normal','preview'),('RGB','preview-rgb'),('3-band','preview-3band')]:
        preview.style_combo.setCurrentText(style);app.processEvents()
        preview.grab().save(str(ROOT/f'docs/screenshot-{name}.png'))
    path=preview.temp_path;preview.reject();app.processEvents()
    if path.exists():raise SystemExit('Screenshot preview did not clean up')
from openlufs.about_dialog import AboutDialog
about=AboutDialog(window);about.show();app.processEvents()
for index,name in [(0,'about'),(1,'help'),(2,'donate')]:
    about.tabs.setCurrentIndex(index);app.processEvents()
    about.grab().save(str(ROOT/f'docs/screenshot-{name}.png'))
about.reject()
window.closing=False
window.close()
print('Captured empty library and verified results screenshots')
