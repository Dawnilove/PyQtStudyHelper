"""작은 선 아이콘 모음. Drawn with QPainter (no image files), in the theme's colours, so they match
each other and stay readable in the dark theme. All shapes are on a 24×24 grid."""
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap

from . import theme

SIZE = 48                      # drawn at 2× so they stay sharp on high-DPI screens


def _folder(p: QPainterPath):
    p.moveTo(3, 6.5)
    p.lineTo(9.2, 6.5)
    p.lineTo(11.2, 8.5)
    p.lineTo(21, 8.5)
    p.lineTo(21, 18.5)
    p.lineTo(3, 18.5)
    p.closeSubpath()


def _draw(name, pt: QPainter, color: QColor):
    pen = QPen(color, 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    pt.setPen(pen)
    pt.setBrush(Qt.NoBrush)
    path = QPainterPath()
    if name == "open":
        _folder(path)
        pt.drawPath(path)
    elif name == "folders":                                   # folder with a plus: manage study folders
        _folder(path)
        pt.drawPath(path)
        pt.drawLine(QPointF(12, 11), QPointF(12, 16))
        pt.drawLine(QPointF(9.5, 13.5), QPointF(14.5, 13.5))
    elif name == "save":
        pt.drawRoundedRect(QRectF(4, 4, 16, 16), 2.5, 2.5)
        pt.drawRect(QRectF(8, 4, 8, 5))
        pt.drawRoundedRect(QRectF(7.5, 13, 9, 7), 1, 1)
    elif name == "designer":                                  # a layout grid
        pt.drawRoundedRect(QRectF(3.5, 4.5, 17, 15), 2.5, 2.5)
        pt.drawLine(QPointF(3.5, 9), QPointF(20.5, 9))
        pt.drawLine(QPointF(9.5, 9), QPointF(9.5, 19.5))
    elif name == "run":
        path.moveTo(7.5, 5)
        path.lineTo(19, 12)
        path.lineTo(7.5, 19)
        path.closeSubpath()
        pt.setBrush(QBrush(color))
        pt.drawPath(path)
    elif name == "stop":
        pt.setBrush(QBrush(color))
        pt.drawRoundedRect(QRectF(6.5, 6.5, 11, 11), 2, 2)
    elif name == "ai":                                        # sparkles
        def star(cx, cy, r, k=0.28):
            s = QPainterPath()
            s.moveTo(cx, cy - r)
            s.quadTo(cx + r * k, cy - r * k, cx + r, cy)
            s.quadTo(cx + r * k, cy + r * k, cx, cy + r)
            s.quadTo(cx - r * k, cy + r * k, cx - r, cy)
            s.quadTo(cx - r * k, cy - r * k, cx, cy - r)
            return s
        pt.setBrush(QBrush(color))
        pt.drawPath(star(10, 13, 7.5))
        pt.drawPath(star(18.5, 5.5, 3.2))
    elif name == "challenge":                                 # a flag
        pt.drawLine(QPointF(6, 4), QPointF(6, 20.5))
        path.moveTo(6, 5)
        path.lineTo(18, 5)
        path.lineTo(15.5, 8.75)
        path.lineTo(18, 12.5)
        path.lineTo(6, 12.5)
        pt.drawPath(path)
    elif name == "help":
        pt.drawEllipse(QRectF(3, 3, 18, 18))
        f = QFont("Segoe UI")
        f.setBold(True)
        f.setPixelSize(13)
        pt.setFont(f)
        pt.drawText(QRectF(3, 3, 18, 18.5), Qt.AlignCenter, "?")
    elif name == "refresh":
        pt.drawArc(QRectF(4.5, 4.5, 15, 15), 60 * 16, 270 * 16)
        path.moveTo(15.8, 3.2)
        path.lineTo(16.2, 7.6)
        path.lineTo(11.8, 7.9)
        pt.drawPath(path)
    elif name == "find":
        pt.drawEllipse(QRectF(4, 4, 11, 11))
        pt.drawLine(QPointF(13.5, 13.5), QPointF(20, 20))


def icon(name: str, color: str | None = None) -> QIcon:
    """A theme-coloured icon; disabled state drawn in the theme's grey."""
    ic = QIcon()
    for mode, col in ((QIcon.Normal, color or theme.T["icon"]), (QIcon.Disabled, theme.T["disabled"])):
        pm = QPixmap(SIZE, SIZE)
        pm.fill(Qt.transparent)
        pt = QPainter(pm)
        pt.setRenderHint(QPainter.Antialiasing)
        pt.scale(SIZE / 24, SIZE / 24)
        _draw(name, pt, QColor(col))
        pt.end()
        ic.addPixmap(pm, mode)
    return ic
