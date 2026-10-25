import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch
from PyQt6.QtCore import Qt,QPoint,QRect
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication
from openlufs.about_dialog import AboutDialog,DONATION_BTC_ADDRESS,DONATION_BTC_URI
from openlufs.theme import STYLE
from test_audio import WORK


class AboutDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        for font in ['C:/Windows/Fonts/segoeui.ttf','C:/Windows/Fonts/seguisb.ttf']:
            if Path(font).exists():QFontDatabase.addApplicationFont(font)
        cls.app.setQuitOnLastWindowClosed(False);cls.app.setStyleSheet(STYLE)
        WORK.mkdir(exist_ok=True)

    def test_creator_credit_and_github_link(self):
        dialog=AboutDialog()
        try:
            self.assertIn('© 2026 zerØ software',dialog.about_content.toPlainText())
            self.assertIn('snuffy420',dialog.about_content.toPlainText())
            self.assertIn('href="https://github.com/snuffy420"',dialog.about_content.toHtml())
            self.assertTrue(dialog.about_content.openExternalLinks())
        finally:dialog.reject()

    def test_donation_address_and_copy_are_exact(self):
        dialog=AboutDialog()
        try:
            self.assertEqual(dialog.address.text(),"bc1qz8877p6vusc22qrctdj4h7w0uk2l9l9h8lwphy")
            self.assertTrue(dialog.copy_button.isEnabled());self.assertTrue(dialog.address.isReadOnly())
            clipboard=MagicMock()
            with patch("openlufs.about_dialog.QApplication.clipboard",return_value=clipboard):
                dialog.copy_address()
            clipboard.setText.assert_called_once_with(DONATION_BTC_ADDRESS)
            self.assertEqual(dialog.copy_status.text(),"BTC address copied.")
        finally:dialog.reject()

    def test_visible_qr_decodes_to_exact_bitcoin_uri(self):
        try:
            import zxingcpp
            from PIL import Image
        except ImportError:self.skipTest("Independent QR validation needs requirements-build.txt")
        dialog=AboutDialog()
        try:
            pixmap=dialog.qr_label.pixmap();self.assertFalse(pixmap.isNull())
            with tempfile.TemporaryDirectory(prefix="donation-qr-",dir=WORK) as directory:
                path=Path(directory)/"qr.png";self.assertTrue(pixmap.save(str(path)))
                decoded=zxingcpp.read_barcode(Image.open(path))
                self.assertIsNotNone(decoded);self.assertEqual(decoded.text,DONATION_BTC_URI)
                dialog.resize(500,360);dialog.tabs.setCurrentIndex(2);dialog.show();self.app.processEvents()
                self.assertTrue(dialog.qr_label.pixmap().save(str(path)))
                decoded=zxingcpp.read_barcode(Image.open(path))
                self.assertIsNotNone(decoded);self.assertEqual(decoded.text,DONATION_BTC_URI)
        finally:dialog.reject()

    def test_all_tabs_remain_accessible_at_small_sizes(self):
        dialog=AboutDialog();dialog.show()
        try:
            for size in [(760,730),(500,360)]:
                dialog.resize(*size);self.app.processEvents()
                for index in range(3):
                    dialog.tabs.setCurrentIndex(index);self.app.processEvents()
                    self.assertFalse(dialog.grab().isNull())
                panel=dialog.tabs.widget(2)
                for widget in [dialog.address,dialog.copy_button,dialog.qr_label]:
                    center=widget.mapTo(panel,widget.rect().center())
                    self.assertTrue(panel.rect().contains(center))
                    self.assertTrue(panel.rect().contains(QRect(widget.mapTo(panel,QPoint(0,0)),widget.size())) )
                self.assertLessEqual(dialog.address.width(),500)
        finally:dialog.reject()
    def test_copy_confirmation_does_not_shift_or_scroll_donation_panel(self):
        from PyQt6.QtWidgets import QScrollArea
        dialog=AboutDialog();dialog.tabs.setCurrentIndex(2);dialog.show();self.app.processEvents()
        try:
            before=[widget.geometry() for widget in [dialog.address,dialog.copy_button,dialog.qr_label]]
            with patch('openlufs.about_dialog.QApplication.clipboard',return_value=MagicMock()):dialog.copy_address()
            self.app.processEvents()
            self.assertEqual(before,[widget.geometry() for widget in [dialog.address,dialog.copy_button,dialog.qr_label]])
            self.assertEqual(dialog.donate_panel.findChildren(QScrollArea),[])
            self.assertEqual(dialog.address.alignment(),Qt.AlignmentFlag.AlignCenter)
            self.assertGreater(dialog.copy_status.y(),dialog.tabs.geometry().bottom())
        finally:dialog.reject()


if __name__=="__main__":unittest.main()
