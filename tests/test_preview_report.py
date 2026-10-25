"""Waveform accuracy, temporary-file lifetime, and readable report regressions."""
from pathlib import Path
import json
import tempfile
import unittest
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEventLoop,QTimer
from PyQt6.QtGui import QFontDatabase
from openlufs.engine import Engine
from openlufs.models import Settings
from openlufs.waveforms import WaveformData,decode_waveforms
from openlufs.preview import PreviewDialog
from openlufs.report_viewer import ReportDialog,export_report,load_report,rows
from openlufs.theme import STYLE
from test_audio import tone,WORK


class PreviewReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
        for f in ['C:/Windows/Fonts/segoeui.ttf','C:/Windows/Fonts/seguisb.ttf']:
            if Path(f).exists():QFontDatabase.addApplicationFont(f)
        cls.app.setStyle('Fusion');cls.app.setStyleSheet(STYLE)

    def setUp(self):
        WORK.mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(prefix='preview-tests-',dir=WORK);self.root=Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def wait(self,dialog):
        if dialog.worker.isRunning():
            loop=QEventLoop();dialog.worker.finished.connect(loop.quit);QTimer.singleShot(15000,loop.quit);loop.exec()
        self.app.processEvents();self.assertFalse(dialog.worker.isRunning())

    def test_peak_envelopes_preserve_every_sample_extremum(self):
        data=np.zeros((103,2),dtype='<f4');data[17,0]=1.7;data[31,0]=-1.3;data[57,1]=.9
        paths={}
        for band in ['full','low','mid','high']:
            path=self.root/(band+'.f32');data.tofile(path);paths[band]=str(path)
        view=WaveformData({'paths':paths,'rate':48000,'channels':2,'frames':103,'crossovers':[200,2500]})
        try:
            for bins in [1,7,64,103]:
                lower,upper=view.envelope(0,103,bins,0)
                self.assertAlmostEqual(float(lower.min()),-1.3,places=6);self.assertAlmostEqual(float(upper.max()),1.7,places=6)
            lower,upper=view.envelope(0,103,103,0)
            np.testing.assert_array_equal(lower,data[:,0]);np.testing.assert_array_equal(upper,data[:,0])
        finally:view.close()

    def test_frequency_bands_reflect_decoded_frequency_content(self):
        engine=Engine()
        for frequency,index in [(80,0),(1000,1),(8000,2)]:
            source=self.root/f'{frequency}.wav'
            engine.run(['-y','-f','lavfi','-i',f'sine=frequency={frequency}:sample_rate=48000:duration=1','-c:a','pcm_f32le',source])
            manifest=decode_waveforms(engine,source,self.root,str(frequency),engine.analyze(source));view=WaveformData(manifest)
            try:
                energy=[float(np.mean(np.square(view.arrays[band][4800:,0],dtype=np.float64))) for band in ['low','mid','high']]
                self.assertEqual(int(np.argmax(energy)),index)
            finally:view.close()

    def test_actual_preview_modes_share_scale_and_delete_every_temp_file(self):
        source=self.root/'source.wav';tone(source,.25,2)
        dialog=PreviewDialog(source,Settings(-20,-1),temp_parent=self.root)
        folder=dialog.temp_path;self.wait(dialog)
        self.assertFalse(dialog.worker.outcome.get('error'),dialog.worker.outcome)
        self.assertEqual(dialog.original.scale,dialog.processed.scale)
        self.assertTrue(folder.exists())
        dialog.resize(900,650);dialog.show();self.app.processEvents()
        for style in ['Normal','RGB','3-band']:
            dialog.style_combo.setCurrentText(style);self.app.processEvents()
            self.assertFalse(dialog.grab().isNull())
        dialog.zoom.setCurrentIndex(5);dialog.position.setValue(5000);self.app.processEvents()
        dialog.reject();self.app.processEvents();self.assertFalse(folder.exists())
        self.assertTrue(source.exists())

    def test_alac_preview_retains_codec_and_cleans_up(self):
        wav=self.root/'source.wav';tone(wav,.25,2)
        source=self.root/'source.m4a'
        Engine().run(['-y','-i',wav,'-c:a','alac','-sample_fmt','s32p','-bits_per_raw_sample','24',source])
        dialog=PreviewDialog(source,Settings(-24,-1),temp_parent=self.root)
        folder=dialog.temp_path;self.wait(dialog)
        self.assertFalse(dialog.worker.outcome.get('error'),dialog.worker.outcome)
        self.assertEqual((dialog.result.before.codec,dialog.result.after.codec),('alac','alac'))
        self.assertEqual(dialog.result.after.bits,24)
        dialog.reject();self.app.processEvents();self.assertFalse(folder.exists())

    def test_cancelled_preview_removes_temporary_directory(self):
        source=self.root/'source.wav';tone(source,.25,3)
        dialog=PreviewDialog(source,Settings(-20,-1),temp_parent=self.root)
        folder=dialog.temp_path;dialog.reject();self.wait(dialog);self.app.processEvents()
        self.assertFalse(folder.exists())

    def test_failed_preview_also_removes_temporary_files(self):
        source=self.root/'invalid.wav';source.write_bytes(b'not audio')
        dialog=PreviewDialog(source,Settings(),temp_parent=self.root);folder=dialog.temp_path
        self.wait(dialog)
        self.assertIn('error',dialog.worker.outcome);self.assertFalse(folder.exists());dialog.reject()

    def test_report_load_export_and_explicit_shortfall(self):
        doc={'version':'1.2.0','settings':{'target':-10,'ceiling':-1},'results':[{'source':'D:/Music/<test>.wav','destination':'D:/Output/track.wav','before':{'integrated':-8},'after':{'integrated':-13.84,'true_peak':-1.02},'gain_db':-5.84,'mode':'Gain capped','warnings':['Peak headroom constrained the gain.']}], 'errors':[{'source':'failed.mp3','error':'test error'}]}
        path=self.root/'report.json';path.write_text(json.dumps(doc),encoding='utf-8')
        self.assertAlmostEqual(rows(load_report(path))[0]['difference'],-3.84)
        dialog=ReportDialog(path);self.assertEqual(dialog.table.rowCount(),2)
        self.assertIn('has not matched',dialog.details.toPlainText())
        for kind in ['csv','html','json']:
            out=self.root/('export.'+kind);export_report(out,doc,kind);self.assertTrue(out.stat().st_size>20)
        self.assertIn('&lt;test&gt;', (self.root/'export.html').read_text())
        dialog.close()


class SpectralDisplayTests(unittest.TestCase):
    def test_frequency_colors_and_nested_layers(self):
        from openlufs.waveforms import spectral_display
        import numpy as np
        rgb,layers=spectral_display([[1,0,0],[0,1,0],[0,0,1],[1,1,1],[0,0,0]])
        self.assertEqual(rgb[:3].argmax(axis=1).tolist(),[0,1,2])
        np.testing.assert_allclose(layers[:3],[[0,0],[1,0],[1,1]])
        self.assertTrue(np.all((layers>=0)&(layers<=1)))
        self.assertTrue(np.all(layers[:,1]<=layers[:,0]))
        np.testing.assert_array_equal(rgb[-1],[16,16,16])


if __name__=='__main__':unittest.main()
