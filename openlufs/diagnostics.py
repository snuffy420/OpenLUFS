"""Exercise both processing backends inside the actual frozen release."""
from array import array
import json,math,platform,sys,tempfile,wave
from pathlib import Path
from . import __version__
from .containers import non_audio_digest
from .engine import Engine
from .models import Settings
from .ogg import inspect_opus


def run(destination):
    destination=Path(destination).resolve()
    report={"ok":False,"version":__version__,"python":platform.python_version(),"platform":sys.platform,"machine":platform.machine(),"frozen":bool(getattr(sys,"frozen",False))}
    try:
        with tempfile.TemporaryDirectory(prefix='openlufs-selftest-',dir=destination.parent) as folder:
            root=Path(folder); source=root/'source.wav'
            values=array('h',(int(5000*math.sin(2*math.pi*997*i/48000)) for i in range(48000*4)))
            with wave.open(str(source),'wb') as f:
                f.setparams((1,2,48000,0,'NONE','not compressed')); f.writeframes(values.tobytes())
            engine=Engine(); wav24=root/'24-bit.wav'
            engine.run(['-y','-i',source,'-c:a','pcm_s24le',wav24])
            pcm=engine.normalize(wav24,root/'normalized.wav',Settings(-20,-1))
            from mutagen.mp4 import MP4
            alac_source=root/'24-bit.m4a'
            engine.run(['-y','-i',wav24,'-c:a','alac','-sample_fmt','s32p','-bits_per_raw_sample','24',alac_source])
            tags=MP4(alac_source);tags['©nam']=['ALAC self-test'];tags['----:com.openlufs:cue']=[b'private data'];tags.save()
            alac=engine.normalize(alac_source,root/'normalized.m4a',Settings(-20,-1))
            report['alac']=alac.to_dict()
            alac_ok=(alac.after.codec=='alac' and alac.after.bits==24 and alac.after.sample_rate==48000
                     and alac.after.channels==1 and abs(alac.after.integrated+20)<=.100001
                     and alac.after.true_peak<=-1 and dict(MP4(alac_source).tags)==dict(MP4(alac.destination).tags))
            mp3=root/'320.mp3'; engine.run(['-y','-i',source,'-c:a','libmp3lame','-b:a','320k',mp3])
            direct=engine.normalize(mp3,root/'normalized.mp3',Settings(-23,-1))
            opus=root/'source.opus'; engine.run(['-y','-i',source,'-c:a','libopus','-b:a','128k',opus])
            header=engine.normalize(opus,root/'normalized.opus',Settings(-23,-1))
            from .batch import process_batch
            import threading
            batch_sources=[wav24,alac_source,mp3,opus]
            concurrent,errors=process_batch([(item,root/'parallel'/item.name) for item in batch_sources],Settings(-23,-1),threading.Event(),workers=2)
            report['parallel_batch']=(not errors and len(concurrent)==4 and
                [Path(result.source).name for result in concurrent]==[item.name for item in batch_sources])
            report['opus']=header.to_dict()
            opus_ok=(inspect_opus(opus).audio_digest==inspect_opus(header.destination).audio_digest
                     and header.mode=='Header gain' and abs(header.after.integrated+23)<=0.100001
                     and header.after.true_peak<=-1)
            report['pcm']=pcm.to_dict(); report['mp3']=direct.to_dict()
            report['ok']=(report['parallel_batch'] and alac_ok and opus_ok and pcm.after.bits==24 and abs(pcm.after.integrated+20)<=0.100001 and pcm.after.true_peak<=-1
                and abs(direct.gain_db)>1 and direct.after.bitrate==320000 and direct.mode=='Direct gain' and direct.after.true_peak<=-1
                and mp3.stat().st_size==Path(direct.destination).stat().st_size
                and non_audio_digest(mp3)==non_audio_digest(direct.destination))
        from PyQt6.QtWidgets import QApplication
        from .gui import MainWindow
        from .theme import STYLE
        app=QApplication.instance() or QApplication([]); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
        window=MainWindow(); report['preferences_location']=str(window.config_path); report['qt']=True; report['assets']=not window.windowIcon().isNull()
        report['window_chrome']=(not window.custom_chrome or hasattr(window,'title_bar') and len(window.window_chrome.handles)==8)
        report['ok']=report['ok'] and report['assets'] and report['window_chrome']; window.deleteLater(); app.processEvents()
        app.setQuitOnLastWindowClosed(False)
        from .about_dialog import AboutDialog,DONATION_BTC_ADDRESS
        about=AboutDialog();about.show();app.processEvents()
        report['about_help']=about.tabs.count()==3 and 'Gain capped' in about.help_content.toPlainText()
        about.tabs.setCurrentIndex(2);app.processEvents()
        report['donation_qr']=(about.address.text()==DONATION_BTC_ADDRESS
                               and not about.qr_label.pixmap().isNull()
                               and not about.tabs.tabIcon(2).isNull())
        about.reject();report['ok']=report['ok'] and report['about_help'] and report['donation_qr']

        from .preview import PreviewDialog
        from .report_viewer import ReportDialog,export_report
        from PyQt6.QtCore import QEventLoop,QTimer
        with tempfile.TemporaryDirectory(prefix='openlufs-ui-selftest-',dir=destination.parent) as folder:
            root=Path(folder);source=root/'source.wav'
            with wave.open(str(source),'wb') as output:
                output.setparams((1,2,48000,0,'NONE','not compressed'));output.writeframes(values.tobytes())
            preview=PreviewDialog(source,Settings(-20,-1),temp_parent=root)
            temporary=preview.temp_path
            if preview.worker.isRunning():
                loop=QEventLoop();preview.worker.finished.connect(loop.quit);QTimer.singleShot(60000,loop.quit);loop.exec()
            app.processEvents()
            if preview.worker.isRunning():
                preview.worker.cancel.set();preview.worker.wait(10000)
                raise RuntimeError('Frozen preview timed out')
            report['preview']=bool(preview.worker.outcome and preview.worker.outcome.get('result'))
            for style in ['Normal','RGB','3-band']:
                preview.style_combo.setCurrentText(style);preview.show();app.processEvents()
                if preview.grab().isNull():raise RuntimeError('Frozen waveform rendering failed')
            preview.reject();app.processEvents();report['preview_cleanup']=not temporary.exists()
            batch=root/'batch.json'
            batch.write_text(json.dumps({'settings':{'target':-20,'ceiling':-1},'results':[preview.result.to_dict()],'errors':[]}),encoding='utf-8')
            viewer=ReportDialog(batch);report['report_viewer']=viewer.table.rowCount()==1
            export_report(root/'report.csv',viewer.document,'csv');viewer.close()
            report['ok']=report['ok'] and report['preview'] and report['preview_cleanup'] and report['report_viewer']
    except Exception as error:
        report['error']=str(error); report['ok']=False
    destination.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    return 0 if report['ok'] else 1
