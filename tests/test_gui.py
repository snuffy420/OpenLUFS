import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
import tempfile
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEventLoop,QTimer,Qt
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QFontDatabase
from openlufs.gui import MainWindow,Worker
from openlufs.theme import STYLE
from test_audio import tone,WORK

class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORK.mkdir(exist_ok=True)
        cls.app=QApplication.instance() or QApplication([])
        for font in ['C:/Windows/Fonts/segoeui.ttf','C:/Windows/Fonts/seguisb.ttf']:
            if Path(font).exists(): QFontDatabase.addApplicationFont(font)
        cls.app.setQuitOnLastWindowClosed(False)
        cls.app.setStyle('Fusion'); cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='gui-',dir=WORK)
        self.folder=Path(self.temp.name)
        from unittest.mock import patch
        with patch.object(MainWindow,"load_settings"):
            self.window=MainWindow()
        self.window.config_path=self.folder/'settings.json'
        self.window.output.setText(str(self.folder/'exports'))

    def tearDown(self):
        if self.window.busy():
            self.window.worker.cancel.set()
            self.wait()
        self.window.close(); self.app.processEvents(); self.temp.cleanup()

    def wait(self):
        worker=self.window.worker
        if worker is None: return
        loop=QEventLoop(); worker.finished.connect(loop.quit)
        timer=QTimer(); timer.setSingleShot(True); timer.timeout.connect(loop.quit); timer.start(15000)
        loop.exec(); timer.stop(); self.app.processEvents()
        self.assertFalse(self.window.busy(),'GUI worker did not stop')

    def test_real_analyze_and_normalize_workflow(self):
        path=self.folder/'track.wav'; tone(path,seconds=4)
        self.window.append_files([path]); self.window.target.setValue(-18)
        self.window.analyze(); self.wait()
        self.assertEqual(self.window.table.item(0,5).text(),'Analyzed')
        self.assertEqual(self.window.table.item(0,3).text(),'—')
        self.window.normalize(); self.wait()
        self.assertIn('1 exported',self.window.status.text())
        self.assertTrue(self.window.report_button.isEnabled())
        self.assertTrue(Path(self.window.report).exists())
        self.assertAlmostEqual(float(self.window.table.item(0,3).text()),-18,delta=0.100001)
        self.window.analyze()
        self.assertEqual(self.window.table.item(0,3).text(),'—')
        self.wait()

    def test_analyze_then_normalize_reuses_input_but_verifies_output(self):
        from unittest.mock import patch
        from openlufs.engine import Engine
        original=Engine.analyze
        calls=[]
        def measured(engine,path):
            calls.append(Path(path).resolve())
            return original(engine,path)
        path=self.folder/'cached.wav'; tone(path,seconds=4)
        self.window.append_files([path]); self.window.target.setValue(-18)
        with patch.object(Engine,'analyze',measured):
            self.window.analyze(); self.wait()
            self.window.normalize(); self.wait()
            self.assertEqual(calls.count(path.resolve()),1)
            self.assertTrue(any(p!=path.resolve() for p in calls),'Export was not verified')
            self.assertIn('1 exported',self.window.status.text())
            tone(path,amplitude=0.1,seconds=4)
            self.window.normalize(); self.wait()
            self.assertEqual(calls.count(path.resolve()),2,'Changed source reused stale analysis')
            self.assertIn('1 exported',self.window.status.text())

    def test_parallel_results_update_the_correct_track_rows(self):
        from openlufs.engine import Engine
        paths=[self.folder/f'parallel-{i}.wav' for i in range(3)]
        expected=[]
        for path,amplitude in zip(paths,[.025,.11,.35]):
            tone(path,amplitude=amplitude,seconds=3)
            expected.append(Engine().analyze(path).integrated)
        self.window.append_files(paths);self.window.target.setValue(-24)
        self.window.normalize();self.wait()
        self.assertIn('3 exported',self.window.status.text())
        self.assertEqual(self.window.completed_rows,{0,1,2});self.assertEqual(self.window.active_rows,set())
        for row,value in enumerate(expected):
            self.assertAlmostEqual(float(self.window.table.item(row,2).text()),value,places=2)
            self.assertAlmostEqual(float(self.window.table.item(row,3).text()),-24,delta=.100001)

    def test_failed_track_is_reported_without_export(self):
        path=self.folder/'silent.wav'; tone(path,amplitude=0,seconds=4)
        self.window.append_files([path]); self.window.normalize(); self.wait()
        self.assertIn('0 exported',self.window.status.text())
        self.assertIn('1 failed',self.window.status.text())
        self.assertEqual(self.window.table.item(0,5).text(),'Failed')
        self.assertFalse((self.folder/'exports/silent.wav').exists())

    def test_duplicate_import_and_remove(self):
        path=self.folder/'track.wav'; tone(path,seconds=1)
        self.window.append_files([path,path])
        self.assertEqual(self.window.table.rowCount(),1)
        self.window.table.selectRow(0); self.window.remove_selected()
        self.assertEqual(self.window.table.rowCount(),0)
        self.assertFalse(self.window.normalize_button.isEnabled())

    def test_typed_target_and_settings_roundtrip(self):
        self.window.target.setValue(-17.5)
        self.window.save_settings()
        self.window.target.setValue(-14)
        self.window.load_settings()
        self.assertEqual(self.window.target.value(),-17.5)


    def test_processing_choices_are_saved_and_restored(self):
        self.assertFalse(self.window.limiter_enabled.isChecked())
        self.window.normalize_enabled.setChecked(False)
        self.window.limiter_enabled.setChecked(True)
        self.window.preview_style='RGB'
        self.window.save_settings()
        self.window.normalize_enabled.setChecked(True)
        self.window.limiter_enabled.setChecked(False)
        self.window.load_settings()
        self.assertFalse(self.window.normalize_enabled.isChecked())
        self.assertTrue(self.window.limiter_enabled.isChecked())
        self.assertEqual(self.window.preview_style,'RGB')

    def test_preview_active_style_and_current_settings(self):
        from unittest.mock import patch,MagicMock
        self.assertEqual(self.window.preview_button.objectName(),self.window.add_button.objectName())
        self.assertFalse(self.window.preview_button.isEnabled())
        paths=[self.folder/'first.wav',self.folder/'selected.wav']
        self.window.append_files(paths);self.window.table.selectRow(1)
        self.assertTrue(self.window.preview_button.isEnabled())
        for normalize,limiter in [(True,False),(True,True),(False,True)]:
            self.window.normalize_enabled.setChecked(normalize)
            self.window.limiter_enabled.setChecked(limiter)
            self.window.target.lineEdit().setText('-10.5  LUFS')
            self.window.ceiling.lineEdit().setText('-0.8  dBTP')
            fake=MagicMock();fake.style_combo.currentText.return_value='RGB'
            with patch('openlufs.preview.PreviewDialog',return_value=fake) as dialog:
                self.window.preview()
                source,settings=dialog.call_args.args[:2]
                self.assertEqual(source,paths[1])
                self.assertEqual((settings.target,settings.ceiling),(-10.5,-.8))
                self.assertEqual((settings.normalize_lufs,settings.allow_limiter),(normalize,limiter))
        self.window.normalize_enabled.setChecked(False);self.window.limiter_enabled.setChecked(False)
        self.assertFalse(self.window.preview_button.isEnabled())

    def test_scan_root_equal_to_output_is_not_hidden(self):
        path=self.folder/'track.wav'; tone(path,seconds=1)
        self.window.output.setText(str(self.folder))
        self.window.scan([self.folder]); self.wait()
        self.assertEqual(self.window.files,[path])

    def test_directly_editable_target_and_ceiling(self):
        self.window.show(); self.app.processEvents()
        self.window.target.setFocus(); self.window.target.selectAll()
        QTest.keyClicks(self.window.target.lineEdit(), "-11.5")
        QTest.keyClick(self.window.target.lineEdit(), Qt.Key.Key_Return)
        self.assertEqual(self.window.target.value(), -11.5)
        self.window.ceiling.setFocus(); self.window.ceiling.selectAll()
        QTest.keyClicks(self.window.ceiling.lineEdit(), "-1.5")
        QTest.keyClick(self.window.ceiling.lineEdit(), Qt.Key.Key_Return)
        self.assertEqual(self.window.ceiling.value(), -1.5)

    def test_controls_do_not_collapse_at_small_window_sizes(self):
        self.window.show()
        for width,height in [(1220,830),(1030,730),(900,620),(780,520)]:
            with self.subTest(size=(width,height)):
                self.window.resize(width,height); self.app.processEvents()
                self.assertGreaterEqual(self.window.target.height(),58)
                self.assertEqual(self.window.ceiling.height(), self.window.target.height())
                self.assertEqual(self.window.ceiling.lineEdit().font().pixelSize(), self.window.target.lineEdit().font().pixelSize())
                for control in [self.window.target,self.window.ceiling]:
                    edit=control.lineEdit()
                    self.assertGreaterEqual(edit.height(),edit.fontMetrics().height())
                    self.window.content_scroll.ensureWidgetVisible(control)
                    self.app.processEvents()
                    center=control.mapTo(self.window.content_scroll.viewport(),control.rect().center())
                    self.assertTrue(self.window.content_scroll.viewport().rect().contains(center))
                self.assertGreaterEqual(self.window.report_button.height(),38)

    def test_extra_panel_copy_and_meter_badge_removed(self):
        from PyQt6.QtWidgets import QLabel
        texts=[widget.text() for widget in self.window.findChildren(QLabel)]
        for unwanted in ["MP3 bitrate and VBR retained.", "Exports are new files.", "BS.1770 · LUFS", "Constant gain · Dynamics preserved"]:
            self.assertFalse(any(unwanted in text for text in texts))

    def test_compact_types_with_full_file_picker(self):
        from openlufs.models import SUPPORTED,AUDIO_FILE_FILTER
        displayed=self.window.supported_label.text()
        for main in ['WAV','AIFF','FLAC','ALAC','MP3','M4A','AAC','Opus']:
            self.assertIn(main,displayed)
        self.assertIn('FLAC · ALAC',displayed)
        self.assertNotIn('M4B',displayed)
        for extension in SUPPORTED:
            self.assertIn('*'+extension,AUDIO_FILE_FILTER)
            self.assertIn(extension[1:].upper(),self.window.supported_label.toolTip().upper())

    def test_header_and_panel_controls_reflow(self):
        from PyQt6.QtWidgets import QComboBox,QLabel
        self.assertEqual(self.window.findChildren(QComboBox), [])
        self.assertNotIn('Audio library',[w.text() for w in self.window.findChildren(QLabel)])
        panel=self.window.normalization_panel
        self.assertTrue(panel.isAncestorOf(self.window.count_label))
        self.assertTrue(panel.isAncestorOf(self.window.analyze_button))
        self.assertEqual(self.window.count_label.text(),'0 tracks')
        path=self.folder/'track.wav'; tone(path,seconds=1)
        self.window.append_files([path])
        self.assertEqual(self.window.count_label.text(),'1 track')
        self.window.show()
        for width in [1220,780,1220]:
            self.window.resize(width,830); self.app.processEvents()
            header=self.window.about_button.parentWidget()
            self.assertTrue(header.isAncestorOf(self.window.add_button))
            for control in [self.window.add_button,self.window.folder_button,self.window.remove_button,self.window.clear_button,self.window.about_button]:
                center=control.mapTo(header,control.rect().center())
                self.assertTrue(header.rect().contains(center))
            a=self.window.analyze_button.mapTo(panel,self.window.analyze_button.rect().center())
            b=self.window.report_button.mapTo(panel,self.window.report_button.rect().center())
            self.assertLess(a.y(),b.y())

    def test_compact_details_and_aligned_panels_without_page_scroll(self):
        from PyQt6.QtWidgets import QLabel
        self.assertTrue(any(label.text()=='TRACK DETAILS'
                            for label in self.window.details_panel.findChildren(QLabel)))
        self.window.show()
        for populated in [False,True]:
            if populated:
                self.window.append_files([self.folder/f'track {n}.wav' for n in range(12)])
                self.window.table.selectRow(0)
                self.window.detail.setPlainText('Track.wav\nSource: -12 LUFS · -1 dBTP\n44,100 Hz · 2 channels · 24-bit')
            for size in [(1220,830),(1280,720),(1030,730)]:
                with self.subTest(size=size,populated=populated):
                    self.window.resize(*size); self.app.processEvents()
                    stack=self.window.stack.geometry()
                    details=self.window.details_panel.geometry()
                    panel=self.window.normalization_panel.geometry()
                    self.assertEqual(stack.top(),panel.top())
                    self.assertEqual(details.bottom(),panel.bottom())
                    self.assertEqual(details.top()-stack.bottom()-1,10)
                    self.assertEqual(self.window.content_scroll.verticalScrollBar().maximum(),0)
                    if populated:
                        self.assertEqual(self.window.detail.verticalScrollBar().maximum(),0)

    def test_seamless_title_bar_and_window_actions(self):
        if not self.window.custom_chrome:self.skipTest('Windows title bar')
        self.window.show();self.app.processEvents();bar=self.window.title_bar
        self.assertEqual(bar.grab().toImage().pixelColor(4,4).name(),'#101416')
        QTest.mouseClick(bar.maximize,Qt.MouseButton.LeftButton);self.app.processEvents()
        self.assertTrue(self.window.isMaximized());self.assertEqual(bar.maximize.accessibleName(),'Restore')
        self.assertTrue(all(not handle.isVisible() for handle in self.window.window_chrome.handles))
        QTest.mouseClick(bar.maximize,Qt.MouseButton.LeftButton);self.app.processEvents()
        self.assertFalse(self.window.isMaximized());self.assertEqual(bar.maximize.accessibleName(),'Maximize')
        self.assertTrue(all(handle.isVisible() for handle in self.window.window_chrome.handles))
        QTest.mouseClick(bar.minimize,Qt.MouseButton.LeftButton);self.app.processEvents()
        self.assertTrue(self.window.isMinimized());self.window.showNormal();self.app.processEvents()
        QTest.mouseClick(bar.close_button,Qt.MouseButton.LeftButton);self.app.processEvents()
        self.assertFalse(self.window.isVisible())

    def test_title_drag_and_all_resize_edges_use_system_operations(self):
        if not self.window.custom_chrome:self.skipTest('Windows title bar')
        from unittest.mock import patch
        from PyQt6.QtGui import QWindow
        self.window.show();self.app.processEvents()
        with patch.object(QWindow,'startSystemMove',return_value=True) as move:
            QTest.mouseClick(self.window.title_bar,Qt.MouseButton.LeftButton)
            move.assert_called_once()
        from PyQt6.QtWidgets import QLabel
        self.assertEqual([label.text() for label in self.window.title_bar.findChildren(QLabel)].count('OpenLUFS'),1)
        self.assertIs(self.window.brand.parentWidget(),self.window.title_bar)
        self.assertEqual(len(self.window.window_chrome.handles),8)
        for handle in self.window.window_chrome.handles:
            with patch.object(QWindow,'startSystemResize',return_value=True) as resize:
                QTest.mouseClick(handle,Qt.MouseButton.LeftButton)
                resize.assert_called_once_with(handle.edges)

    def test_about_includes_settings_and_all_formats(self):
        from unittest.mock import patch
        from PyQt6.QtWidgets import QDialog,QTextBrowser
        def inspect(dialog):
            browser=dialog.help_content
            self.assertEqual([dialog.tabs.tabText(i) for i in range(dialog.tabs.count())],["About","Help","Donate BTC"])
            content=browser.toPlainText()
            for text in ['LUFS','dBTP','−12','−1 dBTP','Gain capped','WAV','AIFF','FLAC','ALAC','MP3','AAC','Opus','rounding','Vorbis']:
                self.assertIn(text,content)
            self.assertGreater(browser.document().characterCount(),1000)
            for status in ['Gain only','Direct gain','Header gain','Gain capped','Peak limited','Limited + encoded','Re-encoded','Unchanged','Failed','Cancelled','UNKNOWN','−13.04','−10 LUFS']:
                self.assertIn(status,content)
            return 0
        with patch.object(QDialog,'exec',inspect):
            self.window.about()

if __name__=='__main__': unittest.main()
