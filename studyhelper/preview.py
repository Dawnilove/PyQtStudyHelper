"""Live preview of the .ui with a red highlight over the selected widget."""
import io
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from PyQt5 import uic
from PyQt5.QtCore import QEvent, QObject, QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (QLabel, QLayout, QScrollArea, QScrollBar, QTabBar, QVBoxLayout,
                             QWidget)

from . import theme


def sanitized_ui(ui_path) -> bytes:
    """The .ui as the preview needs it — nothing that would import or call the student's code.

    - custom (promoted) widgets -> their base class (<extends>), so their module isn't imported
    - <connections> removed: Designer connections to slots that only exist in Main.py would fail
    - <resources> removed: *_rc modules aren't imported (icons from .qrc just don't show)
    """
    root = ET.parse(ui_path).getroot()
    ext = {cw.findtext("class"): (cw.findtext("extends") or "QWidget")
           for cw in root.findall("customwidgets/customwidget")}
    for w in root.iter("widget"):
        cls, seen = w.get("class"), set()
        while cls in ext and cls not in seen:
            seen.add(cls)
            cls = ext[cls]
        w.set("class", cls)
    for tag in ("customwidgets", "connections", "resources", "slots"):
        for e in root.findall(tag):
            root.remove(e)
    return ET.tostring(root, encoding="utf-8")


def load_for_preview(ui_path):
    """uic.loadUi on the sanitized .ui; relative image paths still resolve from the .ui folder."""
    old = os.getcwd()
    try:
        os.chdir(Path(ui_path).parent)
        return uic.loadUi(io.BytesIO(sanitized_ui(ui_path)))
    finally:
        os.chdir(old)


BLOCKED = {QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick,
           QEvent.ContextMenu, QEvent.KeyPress, QEvent.KeyRelease}


class _Overlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.rect_ = QRect()
        self.label = ""

    def paintEvent(self, e):
        if self.rect_.isNull():
            return
        p = QPainter(self)
        r = self.rect_.adjusted(-2, -2, 2, 2)
        p.fillRect(r, QColor(220, 40, 40, 30))
        p.setPen(QPen(QColor(220, 40, 40), 2))
        p.drawRect(r)
        if self.label:
            fm = p.fontMetrics()
            w, h = fm.horizontalAdvance(self.label) + 8, fm.height() + 2
            y = r.top() - h if r.top() - h >= 0 else r.bottom() + 1
            tag = QRect(r.left(), y, w, h)
            p.fillRect(tag, QColor(220, 40, 40))
            p.setPen(Qt.white)
            p.drawText(tag, Qt.AlignCenter, self.label)


class PreviewPane(QScrollArea):
    """Shows the real widgets from uic.loadUi(). Clicks select instead of acting."""
    widgetClicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.host = QWidget()
        self.host.setObjectName("__preview_host")
        self._lay = QVBoxLayout(self.host)
        self._lay.setContentsMargins(16, 24, 16, 16)
        self._lay.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setWidget(self.host)
        self.overlay = _Overlay(self.host)
        self.host.installEventFilter(self)
        self.root = None
        self.names: set[str] = set()
        self._sel = None
        self._palette = None
        # a .ui always looks the way it was designed (light), also when the app uses the dark theme
        self.set_fixed_palette(theme.light_palette())

    def showEvent(self, e):
        # being put into a (dark) window can hand the inner widgets the window's palette again
        if self._palette is not None:
            self.set_fixed_palette(self._palette)
        super().showEvent(e)

    def set_fixed_palette(self, pal):
        """Give the preview its own colours (so a dark app theme doesn't change how the .ui looks)."""
        self._palette = pal
        for o in (self, self.viewport(), self.host):
            o.setPalette(pal)
        if self.root is not None:
            for o in [self.root] + self.root.findChildren(QWidget):
                o.setPalette(pal)

    def load(self, ui_path, names) -> str | None:
        """(Re)load the preview. Returns an error message or None."""
        if self.root is not None:
            self.root.setParent(None)
            self.root.deleteLater()
            self.root = None
        self.names = set(names)
        if ui_path is None:
            self.root = QLabel("연결된 .ui 파일이 없어요.")
            self._lay.addWidget(self.root)
            return None
        try:
            w = load_for_preview(ui_path)
        except Exception as e:  # broken/half-saved .ui…
            w = QLabel(f"미리보기를 만들 수 없어요:\n{type(e).__name__}: {e}")
            w.setWordWrap(True)
            self.root = w
            self._lay.addWidget(w)
            return str(e)
        designed = w.size()                       # the geometry set in Designer
        w.setParent(self.host, Qt.Widget)
        # A form without a layout (widgets placed at fixed x/y) has no size hint and would
        # collapse to 0×0 inside our layout — keep it at the size it has in Designer.
        w.setMinimumSize(designed.boundedTo(w.maximumSize()))
        self._lay.addWidget(w)
        self.root = w
        if self._palette is not None:
            for o in [w] + w.findChildren(QWidget):
                o.setPalette(self._palette)
        for o in [w] + w.findChildren(QWidget):
            o.installEventFilter(self)
            if not isinstance(o, (QTabBar, QScrollBar)):
                o.setFocusPolicy(Qt.NoFocus)
        w.show()
        self.overlay.raise_()
        self.select(self._sel)
        return None

    def find(self, name) -> QObject | None:
        if self.root is None or not name:
            return None
        if self.root.objectName() == name:
            return self.root
        return self.root.findChild(QObject, name)

    def rect_of(self, name) -> QRect:
        obj = self.find(name)
        if isinstance(obj, QWidget) and obj.isVisibleTo(self.host):
            return QRect(obj.mapTo(self.host, QPoint(0, 0)), obj.size())
        if isinstance(obj, QLayout) and obj.parentWidget() is not None:
            g = obj.geometry()
            return QRect(obj.parentWidget().mapTo(self.host, g.topLeft()), g.size())
        return QRect()

    def select(self, name):
        self._sel = name
        self.overlay.setGeometry(self.host.rect())
        self.overlay.rect_ = self.rect_of(name)
        self.overlay.label = name or ""
        self.overlay.raise_()
        self.overlay.update()
        if not self.overlay.rect_.isNull():
            c = self.overlay.rect_.center()
            self.ensureVisible(c.x(), c.y(), self.overlay.rect_.width() // 2 + 20,
                               self.overlay.rect_.height() // 2 + 30)

    def eventFilter(self, obj, ev):
        t = ev.type()
        if obj is self.host:
            if t in (QEvent.Resize, QEvent.LayoutRequest):
                self.select(self._sel)
            return False
        if t in BLOCKED:
            if t == QEvent.MouseButtonPress:
                o = obj
                while o is not None and o is not self.host:
                    if o.objectName() in self.names:
                        self.widgetClicked.emit(o.objectName())
                        break
                    o = o.parent()
            # tab bars still work so pages hidden behind other tabs can be shown
            return not isinstance(obj, (QTabBar, QScrollBar))
        if t in (QEvent.Resize, QEvent.Move, QEvent.Show, QEvent.Hide):
            self.overlay.rect_ = self.rect_of(self._sel)
            self.overlay.update()
        return False
