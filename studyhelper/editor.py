"""Main.py editor: line numbers, Python highlighting, hover on self.<widget>, autocomplete (Tab accepts)."""
import keyword
import re
import threading

from PyQt5.QtCore import QObject, QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (QColor, QFont, QPainter, QSyntaxHighlighter, QTextCharFormat,
                         QTextCursor, QTextFormat)
from PyQt5.QtWidgets import (QListWidget, QListWidgetItem, QPlainTextEdit, QStyledItemDelegate, QTextEdit,
                             QToolTip, QWidget)

from . import theme
from .completer import Completer

SELF_ATTR = re.compile(r"\bself\.(\w+)")
WORD_BEFORE_CURSOR = re.compile(r"\w*$")
COMPLETE_DELAY_MS = 150          # pause after the last keystroke before asking for candidates
_KIND_ROLE = Qt.UserRole + 1
_MODIFIER_KEYS = {Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_AltGr, Qt.Key_Meta, Qt.Key_CapsLock}


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
    def __init__(self, doc):
        super().__init__(doc)
        self.names: set[str] = set()
        self.strings = re.compile(r"""[rbfu]{0,2}("[^"\n]*"|'[^'\n]*')""", re.I)
        self.rebuild()

    def rebuild(self):
        """(Re)read the colours from the current theme."""
        t = theme.T
        self.KW = _fmt(t["kw"], bold=True)
        self.SELF = _fmt(t["self"], italic=True)
        self.STR = _fmt(t["str"])
        self.COMMENT = _fmt(t["comment"], italic=True)
        self.NUM = _fmt(t["num"])
        self.WIDGET = _fmt(t["widget"], bold=True, underline=True)
        kw = "|".join(keyword.kwlist)
        self.rules = [
            (re.compile(rf"\b({kw})\b"), self.KW),
            (re.compile(r"\bself\b"), self.SELF),
            (re.compile(r"\b\d+(\.\d+)?\b"), self.NUM),
        ]

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


class _CompletionWorker(QObject):
    """Asks the Completer on its own thread (jedi can take seconds); only the newest request is answered."""
    ready = pyqtSignal(int, list, int)           # request id, [completer.Item], length of the typed prefix

    def __init__(self, completer):
        super().__init__()
        self._completer = completer
        self._cv = threading.Condition()
        self._job = None
        threading.Thread(target=self._run, daemon=True).start()

    def request(self, rid, source, line, col, force):
        with self._cv:
            self._job = (rid, source, line, col, force)
            self._cv.notify()

    def _run(self):
        self._completer.warmup()                 # read the PyQt5 stubs now, not on the first keystroke
        while True:
            with self._cv:
                while self._job is None:
                    self._cv.wait()
                (rid, source, line, col, force), self._job = self._job, None
            try:
                items, prefix_len = self._completer.complete(source, line, col, force)
            except Exception:
                items, prefix_len = [], 0
            try:
                self.ready.emit(rid, items, prefix_len)
            except RuntimeError:                 # the editor is gone
                return


class _KindDelegate(QStyledItemDelegate):
    """Draws the kind (위젯, 메서드, 시그널 …) grey on the right of each candidate."""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        painter.save()
        painter.setPen(QColor(theme.T["muted"]))
        painter.drawText(option.rect.adjusted(8, 0, -8, 0), Qt.AlignRight | Qt.AlignVCenter,
                         index.data(_KIND_ROLE) or "")
        painter.restore()


class _CompletionPopup(QListWidget):
    """Candidate list under the cursor. Never takes focus: the editor keeps getting the keys."""
    MAX_ROWS = 10

    def __init__(self, editor):
        super().__init__(editor)
        self.shown = []                          # completer.Item list in the order shown
        self.setWindowFlags(Qt.ToolTip)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setItemDelegate(_KindDelegate(self))
        self.setStyleSheet("QListWidget { background: #ffffff; border: 1px solid #b8c4d6; }"
                           "QListWidget::item:selected { background: #2f6fd6; color: #ffffff; }")

    def set_items(self, items):
        self.shown = list(items)
        self.clear()
        for it in self.shown:
            row = QListWidgetItem(it.name)
            row.setData(_KIND_ROLE, it.kind)
            self.addItem(row)
        self.setCurrentRow(0)
        fm = self.fontMetrics()
        width = max(fm.horizontalAdvance(i.name) + fm.horizontalAdvance(i.kind) for i in self.shown)
        self.setFixedSize(min(width + 56, 560),
                          min(len(self.shown), self.MAX_ROWS) * self.sizeHintForRow(0) + 4)

    def narrow(self, prefix):
        """Keep only the candidates that still match a longer prefix."""
        low = prefix.lower()
        keep = [i for i in self.shown if i.name.lower().startswith(low) and i.name != prefix]
        if keep:
            self.set_items(keep)
        return bool(keep)

    def move_selection(self, step):
        self.setCurrentRow((self.currentRow() + step) % self.count())

    def current_name(self):
        return self.currentItem().text()


class CodeEditor(QPlainTextEdit):
    nameHovered = pyqtSignal(str, int)       # name, block number (to know which class/.ui it's in)

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
        self._flash = set()              # lines just inserted by the signal helper (green)
        self._line_area = _LineArea(self)
        self.blockCountChanged.connect(lambda _: self._update_margin())
        self.updateRequest.connect(self._on_update_request)
        self.textChanged.connect(self._on_text_changed)
        self.cursorPositionChanged.connect(self._apply)
        self._update_margin()
        self.viewport().setMouseTracking(True)
        # autocomplete
        self.completer = Completer()
        self._popup = _CompletionPopup(self)
        self._popup.itemClicked.connect(self._accept_completion)
        self._worker = _CompletionWorker(self.completer)
        self._worker.ready.connect(self._on_completions)
        self._req_id = 0                 # bumped on every new ask / close, so late answers are ignored
        self._asked_at = None            # (block, column) the newest ask was made at
        self._prefix_len = 0             # how many typed letters Tab will replace
        self._ask_timer = QTimer(self)
        self._ask_timer.setSingleShot(True)
        self._ask_timer.setInterval(COMPLETE_DELAY_MS)
        self._ask_timer.timeout.connect(self._ask_completions)

    # --- names known from the .ui -------------------------------------
    def set_names(self, names):
        self.highlighter.names = set(names)
        self.highlighter.rehighlight()

    def set_widgets(self, widgets):
        """widgets: {object name: Qt class name} from the .ui — colours the names and feeds autocomplete."""
        self.set_names(widgets)
        self.completer.set_widgets(widgets)

    # --- autocomplete ----------------------------------------------------
    def completion_visible(self):
        return self._popup.isVisible()

    def completion_names(self):
        return [i.name for i in self._popup.shown]

    def hide_completion(self):
        self._req_id += 1                # whatever is still being computed is no longer wanted
        self._ask_timer.stop()
        self._popup.hide()

    def _ask_completions(self, force=False):
        cur = self.textCursor()
        if cur.hasSelection():
            self.hide_completion()
            return
        self._req_id += 1
        self._asked_at = (cur.blockNumber(), cur.positionInBlock())
        self._worker.request(self._req_id, self.toPlainText(), *self._asked_at, force)

    def _on_completions(self, rid, items, prefix_len):
        cur = self.textCursor()
        if rid != self._req_id or self._asked_at != (cur.blockNumber(), cur.positionInBlock()):
            return                       # the user typed on since this was asked
        if not items:
            self._popup.hide()
            return
        self._prefix_len = prefix_len
        self._popup.setFont(self.font())
        self._popup.set_items(items)
        self._place_popup()
        self._popup.show()

    def _place_popup(self):
        rect = self.cursorRect()
        cur = self.textCursor()
        col = cur.positionInBlock()
        typed = cur.block().text()[max(0, col - self._prefix_len):col]
        x = rect.left() - self.fontMetrics().horizontalAdvance(typed)     # line up with the start of the word
        pos = self.viewport().mapToGlobal(QPoint(x, rect.bottom() + 2))
        if pos.y() + self._popup.height() > self.screen().availableGeometry().bottom():
            pos.setY(self.viewport().mapToGlobal(QPoint(0, rect.top())).y() - self._popup.height() - 2)
        self._popup.move(pos)

    def _accept_completion(self, *_):
        if not self._popup.isVisible() or self._popup.currentItem() is None:
            return
        name = self._popup.current_name()
        cur = self.textCursor()
        cur.beginEditBlock()             # one Ctrl+Z undoes the whole completion
        cur.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, self._prefix_len)
        cur.insertText(name)
        cur.endEditBlock()
        self.setTextCursor(cur)
        self.hide_completion()

    def keyPressEvent(self, e):
        key, mods = e.key(), e.modifiers()
        if key == Qt.Key_Space and mods == Qt.ControlModifier:
            self._ask_timer.stop()
            self._ask_completions(force=True)
            return
        if self._popup.isVisible():
            if key == Qt.Key_Tab and mods == Qt.NoModifier:
                self._accept_completion()
                return
            if key in (Qt.Key_Down, Qt.Key_Up):
                self._popup.move_selection(1 if key == Qt.Key_Down else -1)
                return
            if key == Qt.Key_Escape:
                self.hide_completion()
                return
        super().keyPressEvent(e)
        self._after_key(e)

    def _after_key(self, e):
        """Decide what the key just typed means for the popup."""
        key, text = e.key(), e.text()
        if key in _MODIFIER_KEYS:
            return
        if text and (text.isalnum() or text == "_"):
            if self._popup.isVisible():          # keep Tab safe while the new answer is on its way
                cur = self.textCursor()
                prefix = WORD_BEFORE_CURSOR.search(cur.block().text()[:cur.positionInBlock()]).group()
                if self._popup.narrow(prefix):
                    self._prefix_len = len(prefix)
                else:
                    self._popup.hide()
            self._ask_timer.start()
        elif text == "." or key in (Qt.Key_Backspace, Qt.Key_Delete):
            self._popup.hide()
            self._ask_timer.start()
        else:
            self.hide_completion()

    def mousePressEvent(self, e):
        self.hide_completion()
        super().mousePressEvent(e)

    def focusOutEvent(self, e):
        self.hide_completion()
        super().focusOutEvent(e)

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

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():      # let the main window open dropped files
            e.ignore()
            return
        super().dragEnterEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            e.ignore()
            return
        super().dropEvent(e)

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
            self.nameHovered.emit(name, self.cursorForPosition(e.pos()).blockNumber())
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

    def insert_plan(self, plan) -> int:
        """Apply a codegen.Plan as ONE undo step; returns the new connect line number."""
        doc = self.document()
        cur = QTextCursor(doc)
        cur.beginEditBlock()
        stub_lines = []
        if plan.stub:                                   # later position first
            cur.setPosition(doc.findBlockByNumber(plan.stub_after).position())
            cur.movePosition(QTextCursor.EndOfBlock)
            text = plan.stub.rstrip("\n")
            cur.insertText("\n" + text)
            # stub = blank line + def…; +1 more for the connect line inserted above it
            first = plan.stub_after + 3
            stub_lines = list(range(first, first + text.count("\n")))
        cur.setPosition(doc.findBlockByNumber(plan.connect_after).position())
        cur.movePosition(QTextCursor.EndOfBlock)
        cur.insertText("\n" + plan.connect_line)
        cur.endEditBlock()
        line = plan.connect_after + 1
        self._flash = {line, *stub_lines}
        QTimer.singleShot(3000, self._clear_flash)
        self.go_to_line(line)
        return line

    def _clear_flash(self):
        self._flash = set()
        self._apply()

    def set_issues(self, issues):
        self.issues = issues
        self._apply()

    def set_error(self, block_no, msg):
        self.error = (block_no, msg)
        self._apply()

    def _apply(self):
        cur = QTextEdit.ExtraSelection()          # current line, so the 해설 panel's line is obvious
        cur.format.setBackground(QColor(theme.T["cur_line"]))
        cur.format.setProperty(QTextFormat.FullWidthSelection, True)
        cur.cursor = QTextCursor(self.textCursor().block())
        sels = [cur] + list(self._mark_sels)
        for n in self._flash:
            block = self.document().findBlockByNumber(n)
            if block.isValid():
                f = QTextEdit.ExtraSelection()
                f.format.setBackground(QColor(theme.T["flash"]))
                f.format.setProperty(QTextFormat.FullWidthSelection, True)
                f.cursor = QTextCursor(block)
                sels.append(f)
        if self.error:
            block = self.document().findBlockByNumber(self.error[0])
            if block.isValid():
                s = QTextEdit.ExtraSelection()
                s.format.setBackground(QColor(theme.T["err_line"]))
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
                    line.format.setBackground(QColor(theme.T["mark_line"]))
                    line.format.setProperty(QTextFormat.FullWidthSelection, True)
                    line.cursor = QTextCursor(block)
                    sels.append(line)
                    word = QTextEdit.ExtraSelection()
                    word.format.setBackground(QColor(theme.T["mark_word"]))
                    c = QTextCursor(block)
                    c.setPosition(block.position() + m.start())
                    c.setPosition(block.position() + m.end(), QTextCursor.KeepAnchor)
                    word.cursor = c
                    sels.append(word)
                block = block.next()
        self._mark_sels = sels
        self._apply()

    def apply_theme(self):
        """Colours changed (light <-> dark): redo the highlighting, line marks and gutter."""
        self.highlighter.rebuild()
        self.highlighter.rehighlight()
        self.mark(self._marked)
        self._line_area.update()
        self.viewport().update()

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
        p.fillRect(e.rect(), QColor(theme.T["gutter_bg"]))
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
                p.setPen(QColor(theme.T["gutter_mark"]) if n in marked else QColor(theme.T["gutter_fg"]))
                p.drawText(0, top, self._line_area.width() - 6, h, Qt.AlignRight, str(n + 1))
            top += round(self.blockBoundingRect(block).height())
            block = block.next()
