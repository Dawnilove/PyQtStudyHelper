"""'무료 AI 켜기' 마법사: Gemini 무료 키를 받아 도우미에 연결한다.

Flow: open Google AI Studio -> the student creates a key there and presses its copy button
-> we notice a Gemini-looking key on the clipboard, test it, and save it. Nothing is typed
into any website; the key only ever goes to the student's own Credential Manager.
"""
import re

from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QVBoxLayout)

from . import ai
from .theme import ThemedLabel

GEMINI_KEY = re.compile(r"AIza[0-9A-Za-z_\-]{35}")
FREE_MODEL = "gemini-3.8-flash"
KEY_PAGE = ai.PROVIDERS["gemini"]["key_page"]


def find_key(text: str) -> str | None:
    """A Gemini API key inside copied text (None if there isn't exactly a plausible one)."""
    if not text or len(text) > 200:
        return None
    m = GEMINI_KEY.search(text.strip())
    return m.group(0) if m else None


class FreeAiDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("무료 AI 켜기 (Gemini)")
        self.setMinimumWidth(560)
        self.done_ok = False
        self._busy = False
        self._tried = set()

        lay = QVBoxLayout(self)
        lay.addWidget(self._label(
            "<h3>무료 AI 켜기 — 1분이면 돼요</h3>"
            "구글 계정만 있으면 <b>카드 등록 없이</b> 쓸 수 있어요. 한 번만 설정하면 이제부터 "
            "<b>Ctrl+E</b>를 누르는 것만으로 답이 도우미 안에 바로 나와요."))
        lay.addSpacing(6)
        lay.addWidget(self._label(
            "<b>1.</b> 아래 버튼을 눌러 구글 페이지를 열어요 (구글 로그인이 필요할 수 있어요)."))
        b_open = QPushButton("키 발급 페이지 열기")
        b_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(KEY_PAGE)))
        lay.addWidget(b_open)
        lay.addWidget(self._label(
            "<b>2.</b> 페이지에서 <b>Create API key</b>를 누르고, 만들어진 키 옆의 <b>복사 버튼</b>을 눌러요."))
        lay.addWidget(self._label(
            "<b>3.</b> 끝! 복사한 키를 도우미가 알아채고 <b>자동으로 연결</b>해요. "
            "<span style='color:#888'>(자동으로 안 되면 아래 칸에 붙여넣기)</span>"))

        row = QHBoxLayout()
        self.key = QLineEdit()
        self.key.setPlaceholderText("AIza...")
        self.key.setEchoMode(QLineEdit.Password)
        self.key.textChanged.connect(self._on_typed)
        row.addWidget(self.key, 1)
        b_paste = QPushButton("붙여넣기")
        b_paste.clicked.connect(lambda: self.key.setText(QApplication.clipboard().text().strip()))
        row.addWidget(b_paste)
        lay.addLayout(row)

        self.status = ThemedLabel("<span style='color:#888'>키를 복사하면 여기에 결과가 나와요…</span>")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        lay.addWidget(self._label(
            "<span style='color:#777'>무료 티어는 분당·하루 사용량 제한이 있고, 입력한 내용이 Google 제품 개선에 "
            "쓰일 수 있어요. 키는 이 PC의 Windows 자격 증명 관리자에만 저장돼요.</span>"))
        close = QPushButton("닫기")
        close.clicked.connect(self.reject)
        lay.addWidget(close, 0, Qt.AlignRight)

        self.setMinimumHeight(self.sizeHint().height() + 40)       # wrapped labels need the room

        if not ai.package_ok("gemini"):
            self._fail("Gemini 패키지가 없어요. install.bat 을 다시 실행해 주세요 (pip install google-genai).")
        QApplication.clipboard().dataChanged.connect(self._on_clipboard)

    @staticmethod
    def _label(html):
        lab = ThemedLabel(html)
        lab.setWordWrap(True)
        lab.setTextFormat(Qt.RichText)
        return lab

    # ------------------------------------------------------------ detection
    def _on_clipboard(self):
        key = find_key(QApplication.clipboard().text())
        if key:
            self.key.setText(key)                   # -> _on_typed

    def _on_typed(self, text):
        key = find_key(text)
        if key:
            self._connect(key)

    def _connect(self, key):
        if self._busy or key in self._tried or self.done_ok:
            return
        self._tried.add(key)
        self._busy = True
        self.status.setText("키를 찾았어요. 연결을 확인하는 중…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QTimer.singleShot(0, lambda: self._finish(key))      # let the label repaint first

    def _finish(self, key):
        try:
            err = ai.test_key(FREE_MODEL, key)
        finally:
            QApplication.restoreOverrideCursor()
            self._busy = False
        if err:
            self._fail(err)
            return
        ai.set_key("gemini", key)
        ai.set_model(FREE_MODEL)
        self.done_ok = True
        self.status.setText("<span style='color:#2b8a3e;font-size:11pt'><b>★ 연결됐어요!</b> "
                            "이제 Ctrl+E를 눌러 보세요. 답이 도우미 안에 바로 나와요.</span>")
        QTimer.singleShot(1800, self.accept)

    def _fail(self, msg):
        self.status.setText(f"<span style='color:#c0392b'>{msg}</span>")

    def done(self, r):
        try:
            QApplication.clipboard().dataChanged.disconnect(self._on_clipboard)
        except TypeError:
            pass
        super().done(r)
