"""찾기·바꾸기 막대 (Ctrl+F / Ctrl+H). Sits under the editor like VS Code's find widget."""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QTextCursor, QTextDocument
from PyQt5.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget)


class FindBar(QWidget):
    closed = pyqtSignal()

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setObjectName("findBar")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(3)

        r1 = QHBoxLayout()
        self.find = QLineEdit()
        self.find.setPlaceholderText("찾기")
        self.find.setClearButtonEnabled(True)
        self.case = QCheckBox("Aa")
        self.case.setToolTip("대소문자 구분")
        self.count = QLabel("")
        self.count.setMinimumWidth(70)
        self.b_prev = QPushButton("↑")
        self.b_prev.setToolTip("이전 (Shift+Enter)")
        self.b_next = QPushButton("↓")
        self.b_next.setToolTip("다음 (Enter)")
        self.b_close = QPushButton("✕")
        self.b_close.setToolTip("닫기 (Esc)")
        for b in (self.b_prev, self.b_next, self.b_close):
            b.setFlat(True)
            b.setFixedWidth(28)
        for w in (self.find, self.case, self.count, self.b_prev, self.b_next, self.b_close):
            r1.addWidget(w, 1 if w is self.find else 0)
        lay.addLayout(r1)

        self.row2 = QWidget()
        r2 = QHBoxLayout(self.row2)
        r2.setContentsMargins(0, 0, 0, 0)
        self.repl = QLineEdit()
        self.repl.setPlaceholderText("바꿀 내용")
        self.b_rep = QPushButton("바꾸기")
        self.b_all = QPushButton("모두 바꾸기")
        r2.addWidget(self.repl, 1)
        r2.addWidget(self.b_rep)
        r2.addWidget(self.b_all)
        lay.addWidget(self.row2)
        self.row2.setVisible(False)

        self.find.textChanged.connect(lambda _: self._find(True, from_start=True))
        self.find.returnPressed.connect(lambda: self._find(True))
        self.case.toggled.connect(lambda _: self._update_count())
        self.b_next.clicked.connect(lambda: self._find(True))
        self.b_prev.clicked.connect(lambda: self._find(False))
        self.b_close.clicked.connect(self.close_bar)
        self.b_rep.clicked.connect(self.replace_one)
        self.b_all.clicked.connect(self.replace_all)
        self.find.installEventFilter(self)
        self.repl.installEventFilter(self)
        self.setVisible(False)

    # ---------------------------------------------------------------- show/hide
    def open_bar(self, replace=False):
        sel = self.editor.textCursor().selectedText()
        if sel and " " not in sel:
            self.find.setText(sel)
        self.row2.setVisible(replace)
        self.setVisible(True)
        self.find.setFocus()
        self.find.selectAll()
        self._update_count()

    def close_bar(self):
        self.setVisible(False)
        self.editor.setFocus()
        self.closed.emit()

    def eventFilter(self, o, e):
        if e.type() == e.KeyPress:
            if e.key() == Qt.Key_Escape:
                self.close_bar()
                return True
            if e.key() in (Qt.Key_Return, Qt.Key_Enter) and e.modifiers() & Qt.ShiftModifier and o is self.find:
                self._find(False)
                return True
        return super().eventFilter(o, e)

    # ---------------------------------------------------------------- searching
    def _flags(self, forward=True):
        f = QTextDocument.FindFlags()
        if self.case.isChecked():
            f |= QTextDocument.FindCaseSensitively
        if not forward:
            f |= QTextDocument.FindBackward
        return f

    def _find(self, forward=True, from_start=False):
        text = self.find.text()
        if not text:
            self.count.setText("")
            return False
        ed = self.editor
        cur = ed.textCursor()
        if from_start:                                  # typing: keep the match at/after where we are
            cur.setPosition(cur.selectionStart())
            ed.setTextCursor(cur)
        found = ed.document().find(text, ed.textCursor(), self._flags(forward))
        if found.isNull():                              # wrap around
            start = QTextCursor(ed.document())
            if not forward:
                start.movePosition(QTextCursor.End)
            found = ed.document().find(text, start, self._flags(forward))
        if found.isNull():
            self.count.setText("없음")
            self.find.setStyleSheet("background:#ffe3e3;")
            return False
        self.find.setStyleSheet("")
        ed.setTextCursor(found)
        ed.centerCursor()
        self._update_count()
        return True

    def _update_count(self):
        text = self.find.text()
        if not text:
            self.count.setText("")
            return
        hay = self.editor.toPlainText()
        n = hay.count(text) if self.case.isChecked() else hay.lower().count(text.lower())
        self.count.setText(f"{n}개" if n else "없음")

    # ---------------------------------------------------------------- replacing
    def _selection_matches(self):
        sel = self.editor.textCursor().selectedText()
        t = self.find.text()
        return bool(t) and (sel == t if self.case.isChecked() else sel.lower() == t.lower())

    def replace_one(self):
        if not self._selection_matches():
            self._find(True)
            return
        cur = self.editor.textCursor()
        cur.insertText(self.repl.text())
        self._find(True)

    def replace_all(self):
        text = self.find.text()
        if not text:
            return 0
        ed = self.editor
        cur = QTextCursor(ed.document())
        cur.beginEditBlock()                            # one Ctrl+Z undoes all
        n = 0
        pos = QTextCursor(ed.document())
        while True:
            pos = ed.document().find(text, pos, self._flags())
            if pos.isNull():
                break
            pos.insertText(self.repl.text())
            n += 1
        cur.endEditBlock()
        self._update_count()
        self.count.setText(f"{n}개 바꿈")
        return n
