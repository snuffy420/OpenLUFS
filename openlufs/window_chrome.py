"""Seamless Windows title bar using Qt's system move/resize operations."""
from PyQt6.QtCore import Qt,QEvent,QPointF,QRectF
from PyQt6.QtGui import QColor,QPainter,QPen,QShortcut,QKeySequence
from PyQt6.QtWidgets import QWidget,QHBoxLayout,QLabel,QAbstractButton,QMenu

BACKGROUND='#101416'


class CaptionButton(QAbstractButton):
    def __init__(self,action,parent=None):
        super().__init__(parent);self.action=action;self.setFixedSize(46,32)
        self.setAccessibleName(action.capitalize());self.setToolTip(action.capitalize())
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        hovered=self.underMouse() or self.hasFocus()
        background='#a8271d' if self.action=='close' and self.isDown() else '#c42b1c' if self.action=='close' and hovered else '#33443f' if self.isDown() else '#25302f' if hovered else BACKGROUND
        painter.fillRect(self.rect(),QColor(background));painter.setPen(QPen(QColor('#e6eceb'),1.2))
        x=self.width()/2;y=self.height()/2
        if self.action=='minimize':painter.drawLine(QPointF(x-5,y),QPointF(x+5,y))
        elif self.action=='close':
            painter.drawLine(QPointF(x-5,y-5),QPointF(x+5,y+5));painter.drawLine(QPointF(x+5,y-5),QPointF(x-5,y+5))
        elif self.window().isMaximized():
            painter.drawRect(QRectF(x-2,y-6,8,8));painter.fillRect(QRectF(x-5,y-3,8,8),QColor(background));painter.drawRect(QRectF(x-5,y-3,8,8))
        else:painter.drawRect(QRectF(x-5,y-5,10,10))


class TitleBar(QWidget):
    def __init__(self,window):
        super().__init__(window);self.owner=window;self.setObjectName('Header')
        self.window_controls=QWidget(self);self.window_controls.setFixedSize(138,32)
        row=QHBoxLayout(self.window_controls);row.setContentsMargins(0,0,0,0);row.setSpacing(0)
        self.minimize=CaptionButton('minimize');self.maximize=CaptionButton('maximize');self.close_button=CaptionButton('close')
        row.setSpacing(0)
        for control in [self.minimize,self.maximize,self.close_button]:row.addWidget(control)
        self.minimize.clicked.connect(window.showMinimized);self.maximize.clicked.connect(self.toggle_maximized)
        self.close_button.clicked.connect(window.close)
        window.installEventFilter(self)
        QShortcut(QKeySequence('Alt+Space'),window,activated=lambda:self.show_menu(self.mapToGlobal(self.rect().bottomLeft())))

    def toggle_maximized(self):
        self.owner.showNormal() if self.owner.isMaximized() else self.owner.showMaximized()

    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.WindowStateChange:
            text='Restore' if self.owner.isMaximized() else 'Maximize'
            self.maximize.setAccessibleName(text);self.maximize.setToolTip(text);self.maximize.update()
        return super().eventFilter(watched,event)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            handle=self.owner.windowHandle()
            if handle is not None and handle.startSystemMove():event.accept();return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self.toggle_maximized();event.accept()
        else:super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self,event):
        self.show_menu(event.globalPos())

    def show_menu(self,position):
        menu=QMenu(self)
        restore=menu.addAction('Restore',self.owner.showNormal);restore.setEnabled(self.owner.isMaximized())
        menu.addAction('Minimize',self.owner.showMinimized)
        maximize=menu.addAction('Maximize',self.owner.showMaximized);maximize.setEnabled(not self.owner.isMaximized())
        menu.addSeparator();menu.addAction('Close',self.owner.close);menu.exec(position)


class ResizeHandle(QWidget):
    def __init__(self,window,edges,cursor):
        super().__init__(window);self.edges=edges;self.setCursor(cursor)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            handle=self.window().windowHandle()
            if handle is not None and handle.startSystemResize(self.edges):event.accept();return
        super().mousePressEvent(event)


class WindowChrome:
    def __init__(self,window):
        self.window=window;self.handles=[]
        left=Qt.Edge.LeftEdge;right=Qt.Edge.RightEdge;top=Qt.Edge.TopEdge;bottom=Qt.Edge.BottomEdge
        for edges,cursor in [(top,Qt.CursorShape.SizeVerCursor),(bottom,Qt.CursorShape.SizeVerCursor),
            (left,Qt.CursorShape.SizeHorCursor),(right,Qt.CursorShape.SizeHorCursor),
            (top|left,Qt.CursorShape.SizeFDiagCursor),(bottom|right,Qt.CursorShape.SizeFDiagCursor),
            (top|right,Qt.CursorShape.SizeBDiagCursor),(bottom|left,Qt.CursorShape.SizeBDiagCursor)]:
            self.handles.append(ResizeHandle(window,edges,cursor))
        window.installEventFilter(self.filter(window))
        self.arrange()

    def filter(self,window):
        from PyQt6.QtCore import QObject
        owner=self
        class Filter(QObject):
            def eventFilter(self,watched,event):
                if event.type() in {QEvent.Type.Resize,QEvent.Type.WindowStateChange,QEvent.Type.Show}:
                    owner.arrange()
                return False
        self.events=Filter(window);return self.events

    def arrange(self):
        w=self.window.width();h=self.window.height();b=6
        rects=[(b,0,w-2*b,b),(b,h-b,w-2*b,b),(0,b,b,h-2*b),(w-b,b,b,h-2*b),
               (0,0,b,b),(w-b,h-b,b,b),(w-b,0,b,b),(0,h-b,b,b)]
        for handle,rect in zip(self.handles,rects):
            handle.setGeometry(*rect);handle.setVisible(not self.window.isMaximized() and not self.window.isFullScreen());handle.raise_()
