STYLE = """
QMainWindow, QWidget { background: #101416; color: #e6eceb; font-family: 'Segoe UI', 'Helvetica Neue', 'Arial'; font-size: 13px; }
QWidget#Header { border-bottom: 1px solid #293133; }
QLabel#Brand { font-size: 26px; font-weight: 650; letter-spacing: -1px; }
QLabel#Muted { color: #8a9b9b; }
QLabel#Section { color: #9eafad; font-size: 11px; font-weight: 650; letter-spacing: 1.5px; }
QLabel#PageTitle { font-size: 23px; font-weight: 600; }
QLabel#BigNumber { font-size: 30px; color: #65e4bd; font-weight: 600; }
QLabel#Badge { color: #65e4bd; background: #18352d; border: 1px solid #295445; border-radius: 10px; padding: 4px 12px; }
QFrame#Panel, QWidget#Panel { background: #171d20; border: 1px solid #2b3538; border-radius: 12px; }
QFrame#Panel QLabel, QFrame#Panel QCheckBox { background: transparent; }
QPushButton { background: #222b2e; border: 1px solid #354145; border-radius: 7px; padding: 10px 16px; min-height: 18px; font-weight: 550; }
QPushButton:hover { background: #2b373a; border-color: #657874; }
QPushButton:pressed { background: #344541; }
QPushButton:disabled { color: #5e6e6f; background: #1a2225; border-color: #2a3437; }
QPushButton#Primary { color: #0b241c; background: #65e4bd; border-color: #65e4bd; font-weight: 650; }
QPushButton#Primary:hover { background: #87efcf; }
QPushButton#Primary:disabled { background: #29443b; color: #6b8f82; border-color: #29443b; }
QPushButton#Quiet { background: transparent; border-color: #293538; color: #a9bab7; }
QPushButton#Cancel { color: #f2b8a7; border-color: #6a4540; }
QLineEdit, QComboBox, QDoubleSpinBox { border: 1px solid #354145; background: #101719; border-radius: 7px; padding: 9px; color: #e6eceb; min-height: 18px; selection-background-color: #2e755f; }
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border-color: #65e4bd; }
QDoubleSpinBox { min-height: 24px; }
QComboBox { min-height: 22px; }
QDoubleSpinBox#Target { min-height: 42px; font-size: 24px; font-weight: 600; color: #65e4bd; padding: 7px 9px; }
QComboBox::drop-down, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { border: none; width: 22px; }
QDoubleSpinBox#Target QLineEdit { font-size: 24px; font-weight: 600; color: #65e4bd; }
QDoubleSpinBox QLineEdit { border: none; background: transparent; padding: 0; min-height: 0; color: #e6eceb; }
QComboBox QAbstractItemView { background: #1d282b; color: #e6eceb; selection-background-color: #2c5749; selection-color: #ffffff; outline: none; }
QComboBox QAbstractItemView::item { min-height: 24px; padding: 6px 8px; }
QScrollArea, QScrollArea > QWidget > QWidget { background: #101416; border: none; }
QScrollBar:horizontal { background: #141a1d; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: #3b4c48; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QCheckBox { spacing: 9px; color: #b7c6c3; }
QCheckBox::indicator { width: 15px; height: 15px; border-radius: 4px; background: #11191c; border: 1px solid #52635f; }
QCheckBox::indicator:checked { background: #65e4bd; border: 1px solid #65e4bd; image: url(:/none); }
QTableWidget { border: 1px solid #2b3538; border-radius: 10px; background: #141a1d; gridline-color: #263033; outline: none; selection-background-color: #223d34; }
QTableWidget::item { padding: 8px; border-bottom: 1px solid #232d30; }
QTableWidget::item:selected { background: #223d34; color: #f0fcf8; }
QHeaderView::section { background: #1b2427; color: #90a4a0; border: none; border-bottom: 1px solid #34413f; padding: 11px 8px; font-size: 11px; font-weight: 600; }
QPlainTextEdit { border: 1px solid #2b3538; border-radius: 8px; background: #111719; color: #a5b9b4; padding: 10px; font-size: 12px; }
QProgressBar { background: #202b2d; border: none; border-radius: 3px; height: 5px; text-align: center; }
QProgressBar::chunk { background: #65e4bd; border-radius: 3px; }
QScrollBar:vertical { background: #141a1d; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #3b4c48; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: #233730; color: #effaf6; border: 1px solid #496f5f; padding: 6px; }
QSplitter::handle { background: #101416; width: 14px; }
"""

from .engine import resource_path
STYLE = STYLE.replace("url(:/none)", 'url("' + resource_path("assets/check.svg").as_posix() + '")')
STYLE += ('QComboBox::down-arrow, QDoubleSpinBox::down-arrow { width: 14px; height: 14px; image: url("' + resource_path("assets/chevron.svg").as_posix() + '"); }'
          'QDoubleSpinBox::up-arrow { width: 14px; height: 14px; image: url("' + resource_path("assets/up.svg").as_posix() + '"); }')

STYLE += "QTextBrowser#AboutContent { background: #171d20; border: 1px solid #2b3538; border-radius: 8px; padding: 16px; color: #e6eceb; }"

STYLE += "QPlainTextEdit#TrackDetails { background: transparent; border: none; padding: 0; }"

STYLE += """
QTabWidget#AboutTabs::pane { background: #171d20; border: 1px solid #2b3538; border-radius: 8px; top: -1px; }
QTabBar::tab { background: #101719; color: #9eafad; border: 1px solid #2b3538; padding: 10px 16px; margin-right: 5px; border-top-left-radius: 7px; border-top-right-radius: 7px; }
QTabBar::tab:selected { background: #18352d; color: #65e4bd; border-color: #295445; }
QTabBar::tab:hover { color: #e6eceb; background: #222e2d; }
QTextBrowser#HelpContent { background: #171d20; border: none; padding: 16px; color: #e6eceb; }
QWidget#DonationPanel, QWidget#DonationPanel QLabel { background: #171d20; }
QLineEdit#DonationAddress { font-family: 'Consolas', monospace; color: #65e4bd; font-size: 14px; }
"""

STYLE += "QWidget#WindowTitleBar, QWidget#WindowTitleBar QLabel { background: #101416; border: none; } QLabel#WindowCaption { color: #e6eceb; font-weight: 600; padding: 0 8px; }"
