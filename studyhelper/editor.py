"""Main.py editor: line numbers, Python highlighting, hover on self.<widget>."""
import keyword
import re

from PyQt5.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt5.QtGui import (QColor, QFont, QPainter, QSyntaxHighlighter, QTextCharFormat,
                         QTextCursor, QTextFormat)
from PyQt5.QtWidgets import QPlainTextEdit, QTextEdit, QToolTip, QWidget

SELF_ATTR = re.compile(r"\bself\.(\w+)")


class _Note:
    def __init__(self, msg):
        self.msg = msg


def _fmt(color, bold=False, italic=False, underline=False):
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Bold)
    f.setFontItalic(italic)
    f.setFontUnderline(underline)
    return f


class PythonHighlighter(QSyntaxHighlighter):
    KW = _fmt("#0033b3", bold=True)
    SELF = _fmt("#94558d", italic=True)
    STR = _fmt("#067d17")
    COMMENT = _fmt("#8c8c8c", italic=True)
    NUM = _fmt("#1750eb")
    WIDGET = _fmt("#0b6bcb", bold=True, underline=True)

    def __init__(self, doc):
        super().__init__(doc)
        self.names: set[str] = set()
        kw = "|".join(keyword.kwlist)
        self.rules = [
            (re.compile(rf"\b({kw})\b"), self.KW),
            (re.compile(r"\bself\b"), self.SELF),
            (re.compile(r"\b\d+(\.\d+)?\b"), self.NUM),
        ]
        self.strings = re.compile(r"""[rbfu]{0,2}("[^"\n]*"|'[^'\n]*')""", re.I)

    def highlightBlock(self, text):
        for rx, fmt in self.rules:
            for m in rx.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)
        for m in SELF_ATTR.finditer(text):
            if m.group(1) in self.names:
                self.setFormat(m.start(1), len(m.group(1)), self.WIDGET)
        for m in self.strings.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.STR)
        # comment: '#' not inside a string
        in_str = None
        for i, ch in enumerate(text):
            if in_str:
                if ch == in_str:
                    in_str = None
            elif ch in "\"'":
                in_str = ch
            elif ch == "#":
                self.setFormat(i, len(text) - i, self.COMMENT)
                break


class _LineArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_area_width(), 0)

    def paintEvent(self, e):
        self.editor.paint_line_area(e)


class CodeEditor(QPlainTextEdit):
    nameHovered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.highlighter = PythonHighlighter(self.document())
        self.tooltip_for = None          # callable(name) -> str
        self.zoomRequested = None        # callable(step) for Ctrl+wheel
        self._hover = None
        self._marked = None
        self._mark_sels = []
        self.issues = []                 # checker.Issue list
        self.error = None                # (block_no, message) from the last run
        self._line_area = _LineArea(self)
        self.blockCountChanged.connect(lambda _: self._update_margin())
        self.updateRequest.connect(self._on_update_request)
        self.textChanged.connect(self._on_text_changed)
        self.cursorPositionChanged.connect(self._apply)
        self._update_margin()
        self.viewport().setMouseTracking(True)

    # --- names known from the .ui -------------------------------------
    def set_names(self, names):
        self.highlighter.names = set(names)
        self.highlighter.rehighlight()

    # --- hover ----------------------------------------------------------
    def name_at(self, pos):
        cur = self.cursorForPosition(pos)
        # cursorForPosition snaps to the nearest char; make sure we're really over text
        if self.cursorRect(cur).bottom() < pos.y() - self.fontMetrics().height():
            return None
        col = cur.positionInBlock()
        text = cur.block().text()
        for m in SELF_ATTR.finditer(text):
            if m.start() <= col <= m.end() and m.group(1) in self.highlighter.names:
                return m.group(1)
        return None

    def _on_text_changed(self):
        self.error = None                # the code changed; the old crash line is stale
        self.mark(self._marked)

    def issue_at(self, pos):
        cur = self.cursorForPosition(pos)
        b, col = cur.blockNumber(), cur.positionInBlock()
        for x in self.issues:
            if x.line == b and x.start <= col <= max(x.end, x.start + 1):
                return x
        if self.error and self.error[0] == b:
            return _Note(f"실행 중 에러난 줄: {self.error[1]}")
        return None

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier and self.zoomRequested:
            self.zoomRequested(1 if e.angleDelta().y() > 0 else -1)
            return
        super().wheelEvent(e)

    def mouseMoveEvent(self, e):
        super().mouseMoveEvent(e)
        issue = self.issue_at(e.pos())
        if issue is not None:
            QToolTip.showText(e.globalPos(), issue.msg, self.viewport())
            self._hover = None
            return
        name = self.name_at(e.pos())
        if name and name != self._hover:
            self.nameHovered.emit(name)
            if self.tooltip_for:
                QToolTip.showText(e.globalPos(), self.tooltip_for(name), self.viewport())
        elif not name:
            QToolTip.hideText()
        self._hover = name

    # --- marking all uses of self.<name> ------------------------------
    def occurrences(self, name) -> list[int]:
        """Block numbers (0-based) that use self.<name>."""
        if not name:
            return []
        rx = re.compile(rf"\bself\.{re.escape(name)}\b")
        out, block = [], self.document().firstBlock()
        while block.isValid():
            if rx.search(block.text()):
                out.append(block.blockNumber())
            block = block.next()
        return out

    def set_issues(self, issues):
        self.issues = issues
        self._apply()

    def set_error(self, block_no, msg):
        self.error = (block_no, msg)
        self._apply()

    def _apply(self):
        cur = QTextEdit.ExtraSelection()          # current line, so the 해설 panel's line is obvious
        cur.format.setBackground(QColor("#eaf2ff"))
        cur.format.setProperty(QTextFormat.FullWidthSelection, True)
        cur.cursor = QTextCursor(self.textCursor().block())
        sels = [cur] + list(self._mark_sels)
        if self.error:
            block = self.document().findBlockByNumber(self.error[0])
            if block.isValid():
                s = QTextEdit.ExtraSelection()
                s.format.setBackground(QColor("#ffd9d9"))
                s.format.setProperty(QTextFormat.FullWidthSelection, True)
                s.cursor = QTextCursor(block)
                sels.insert(0, s)
        for x in self.issues:
            block = self.document().findBlockByNumber(x.line)
            if not block.isValid() or x.end <= x.start:
                continue
            s = QTextEdit.ExtraSelection()
            s.format.setUnderlineStyle(QTextCharFormat.WaveUnderline)
            s.format.setUnderlineColor(QColor("#e03131" if x.level == "error" else "#e8890c"))
            c = QTextCursor(block)
            c.setPosition(block.position() + min(x.start, block.length() - 1))
            c.setPosition(block.position() + min(x.end, block.length() - 1), QTextCursor.KeepAnchor)
            s.cursor = c
            sels.append(s)
        self.setExtraSelections(sels)
        self._line_area.update()

    def mark(self, name):
        self._marked = name
        sels = []
        if name:
            rx = re.compile(rf"\bself\.{re.escape(name)}\b")
            block = self.document().firstBlock()
            while block.isValid():
                for m in rx.finditer(block.text()):
                    line = QTextEdit.ExtraSelection()
                    line.format.setBackground(QColor("#fff4c2"))
                    line.format.setProperty(QTextFormat.FullWidthSelection, True)
                    line.cursor = QTextCursor(block)
                    sels.append(line)
                    word = QTextEdit.ExtraSelection()
                    word.format.setBackground(QColor("#ffd666"))
                    c = QTextCursor(block)
                    c.setPosition(block.position() + m.start())
                    c.setPosition(block.position() + m.end(), QTextCursor.KeepAnchor)
                    word.cursor = c
                    sels.append(word)
                block = block.next()
        self._mark_sels = sels
        self._apply()

    def go_to_line(self, block_no):
        block = self.document().findBlockByNumber(block_no)
        if block.isValid():
            self.setTextCursor(QTextCursor(block))
            self.centerCursor()

    def reveal(self, name):
        """Scroll so the first use of self.<name> is visible (without stealing focus)."""
        occ = self.occurrences(name)
        if not occ:
            return
        first_visible = self.firstVisibleBlock().blockNumber()
        visible_lines = self.viewport().height() // max(1, self.fontMetrics().height())
        if not any(first_visible <= b < first_visible + visible_lines for b in occ):
            self.go_to_line(occ[0])

    # --- line numbers ---------------------------------------------------
    def line_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * max(3, digits)

    def _update_margin(self):
        self.setViewportMargins(self.line_area_width(), 0, 0, 0)

    def _on_update_request(self, rect, dy):
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cr = self.contentsRect()
        self._line_area.setGeometry(QRect(cr.left(), cr.top(), self.line_area_width(), cr.height()))

    def paint_line_area(self, e):
        p = QPainter(self._line_area)
        p.fillRect(e.rect(), QColor("#f3f3f3"))
        marked = set(self.occurrences(self._marked))
        levels = {}
        for x in self.issues:
            if levels.get(x.line) != "error":
                levels[x.line] = x.level
        if self.error:
            levels[self.error[0]] = "error"
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        h = self.fontMetrics().height()
        while block.isValid() and top <= e.rect().bottom():
            if block.isVisible():
                n = block.blockNumber()
                if n in levels:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor("#e03131" if levels[n] == "error" else "#e8890c"))
                    p.drawEllipse(3, top + h // 2 - 3, 6, 6)
                p.setPen(QColor("#b8860b") if n in marked else QColor("#999999"))
                p.drawText(0, top, self._line_area.width() - 6, h, Qt.AlignRight, str(n + 1))
            top += round(self.blockBoundingRect(block).height())
            block = block.next()
