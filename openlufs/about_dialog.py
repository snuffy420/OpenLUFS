"""Tabbed application information, processing help and Bitcoin donations."""
from PyQt6.QtCore import Qt,QSize
from PyQt6.QtGui import QIcon,QPixmap,QFont
from PyQt6.QtWidgets import (QApplication,QDialog,QDialogButtonBox,QHBoxLayout,
    QLabel,QLineEdit,QPushButton,QTabWidget,QTextBrowser,QVBoxLayout,QWidget,QSizePolicy)
from .engine import resource_path
from .help import ABOUT_HTML,HELP_HTML

# Supplied by the project owner; never substitute an example or third-party address.
DONATION_BTC_ADDRESS="bc1qz8877p6vusc22qrctdj4h7w0uk2l9l9h8lwphy"
DONATION_BTC_URI="bitcoin:"+DONATION_BTC_ADDRESS


class DonationPanel(QWidget):
    def minimumSizeHint(self):return QSize(0,0)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'adapt'):self.adapt(event.size().height())


class DonationQR(QLabel):
    def __init__(self,parent=None):
        super().__init__(parent);self.original=QPixmap();self.setMinimumSize(120,120)
        self.setMaximumHeight(205);self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Ignored)

    def set_code(self,pixmap):self.original=pixmap;self.refresh()

    def refresh(self):
        if not self.original.isNull():
            side=max(1,min(205,self.width(),self.height()))
            self.setPixmap(self.original.scaled(side,side,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation))

    def resizeEvent(self,event):super().resizeEvent(event);self.refresh()


class AboutDialog(QDialog):
    def __init__(self,parent=None,donation_address=None):
        super().__init__(parent)
        self.setObjectName("AboutDialog");self.setWindowTitle("About OpenLUFS")
        self.setMinimumSize(500,360)
        available=self.screen().availableGeometry()
        self.resize(min(760,available.width()-80),min(730,available.height()-80))
        layout=QVBoxLayout(self);layout.setContentsMargins(20,20,20,18);layout.setSpacing(14)
        self.tabs=QTabWidget();self.tabs.setObjectName("AboutTabs");layout.addWidget(self.tabs,1)
        self.about_content=self.browser(ABOUT_HTML,"AboutContent")
        self.help_content=self.browser(HELP_HTML,"HelpContent")
        self.tabs.addTab(self.about_content,"About");self.tabs.addTab(self.help_content,"Help")
        icon=QIcon(str(resource_path("assets/bitcoin.svg")))
        donate=self.donate_panel=DonationPanel();donate.setObjectName("DonationPanel");donate.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        donate.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Ignored)
        content=self.donation_layout=QVBoxLayout(donate);content.setContentsMargins(16,12,16,12);content.setSpacing(6)
        self.donation_heading=QWidget();self.donation_heading.setStyleSheet('background: transparent;');heading=QHBoxLayout(self.donation_heading);heading.setContentsMargins(0,0,0,0)
        mark=QLabel();mark.setPixmap(icon.pixmap(QSize(40,40)));heading.addWidget(mark)
        title=QLabel("Support OpenLUFS");title.setObjectName("PageTitle");title.setWordWrap(True);heading.addWidget(title,1);content.addWidget(self.donation_heading)
        self.donation_intro=QLabel("If OpenLUFS is useful to you, you can support its development with a Bitcoin donation. Donations are optional.")
        self.donation_intro.setWordWrap(True);content.addWidget(self.donation_intro)
        self.donation_network=QLabel("Bitcoin (BTC) address · Bitcoin network");self.donation_network.setWordWrap(True);content.addWidget(self.donation_network)
        self.donation_address=DONATION_BTC_ADDRESS if donation_address is None else donation_address
        self.address=QLineEdit();self.address.setObjectName("DonationAddress");self.address.setReadOnly(True)
        self.address.setAccessibleName("Bitcoin donation address");self.address.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font=QFont('Consolas');font.setPixelSize(14);self.address.setFont(font)
        self.address.setMinimumWidth(min(360,self.address.fontMetrics().horizontalAdvance(self.donation_address)+26));self.address.setMaximumWidth(500)
        self.address.setFixedHeight(44);self.address.setText(self.donation_address or "Donation address not configured yet.")
        address_row=QHBoxLayout();address_row.addStretch(1);address_row.addWidget(self.address,8);address_row.addStretch(1);content.addLayout(address_row)
        self.copy_button=QPushButton("Copy BTC address");self.copy_button.setEnabled(bool(self.donation_address))
        self.copy_button.setMaximumWidth(500);self.copy_button.setFixedHeight(40)
        self.copy_button.setStyleSheet('QPushButton { padding: 6px 16px; }')
        self.copy_button.clicked.connect(self.copy_address)
        copy_row=QHBoxLayout();copy_row.addStretch(1);copy_row.addWidget(self.copy_button,8);copy_row.addStretch(1);content.addLayout(copy_row)
        self.qr_label=DonationQR()
        self.qr_label.setAccessibleName("Bitcoin donation QR code")
        if self.donation_address==DONATION_BTC_ADDRESS:
            qr=QPixmap(str(resource_path("assets/donation-btc-qr.png")))
            if not qr.isNull():
                self.qr_label.set_code(qr)
        content.addWidget(self.qr_label,1)
        content.addStretch()
        self.tabs.addTab(donate,icon,"Donate BTC");donate.adapt=self.adapt_donation
        footer=QHBoxLayout()
        self.copy_status=QLabel("");self.copy_status.setObjectName("Muted");self.copy_status.setFixedHeight(20)
        footer.addWidget(self.copy_status,1)
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);close.rejected.connect(self.reject);footer.addWidget(close)
        layout.addLayout(footer)

    def adapt_donation(self,height):
        compact=height<320
        self.donation_heading.setVisible(not compact)
        self.donation_intro.setVisible(height>=450)
        self.donation_network.setVisible(not compact)
        self.donation_layout.setContentsMargins(12,4 if compact else 12,12,4 if compact else 12)
        self.address.setFixedHeight(36 if compact else 44)
        self.copy_button.setFixedHeight(32 if compact else 40)

    @staticmethod
    def browser(html,name):
        browser=QTextBrowser();browser.setObjectName(name);browser.setOpenExternalLinks(True)
        browser.setHtml(html);return browser

    def copy_address(self):
        if self.donation_address:
            QApplication.clipboard().setText(self.donation_address)
            self.copy_status.setText("BTC address copied.")
