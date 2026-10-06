"""도움말 메뉴: 단축키 목록, 오류 기록 보기, 새 버전 알림."""
import platform
import re
import sys
import urllib.request
from pathlib import Path

from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QFont
from PyQt5.QtWidgets import (QApplication, QDialog, QHBoxLayout, QHeaderView, QPlainTextEdit, QPushButton,
                             QTableWidget, QTableWidgetItem, QVBoxLayout)

from . import __version__
from .theme import ThemedLabel, chrome

LOG = Path(__file__).resolve().parent.parent / "error.log"          # written by run.py's excepthook
REPO_URL = "https://github.com/Dawnilove/PyQtStudyHelper"
VERSION_URL = "https://raw.githubusercontent.com/Dawnilove/PyQtStudyHelper/main/studyhelper/__init__.py"

# keys that aren't menu actions
EXTRA_KEYS = [
    ("편집기", "자동완성 열기 / 고르기", "Ctrl+Space / Tab"),
    ("편집기", "되돌리기 / 다시 하기", "Ctrl+Z / Ctrl+Y"),
    ("편집기", "글자 크게·작게", "Ctrl + 마우스 휠"),
    ("찾기 막대", "다음 / 이전 찾기", "Enter / Shift+Enter"),
    ("찾기 막대", "닫기", "Esc"),
    ("실행 결과", "input()에 값 보내기", "입력 칸에 쓰고 Enter"),
]


def env_info() -> str:
    """What a helper needs to know when a friend reports a problem."""
    return (f"PyQt 학습 도우미 {__version__}\n"
            f"Python {sys.version.split()[0]} ({sys.executable})\n"
            f"PyQt5 {PYQT_VERSION_STR} / Qt {QT_VERSION_STR}\n"
            f"{platform.platform()}")


def menu_shortcuts(menubar) -> list[tuple[str, str, str]]:
    """(menu, action, keys) for every menu action that has a shortcut, in menu order."""
    out = []
    for top in menubar.actions():
        menu = top.menu()
        if menu is None:
            continue
        group = top.text().split("(")[0]
        for a in menu.actions():
            if a.isSeparator() or a.menu() is not None:
                continue
            keys = a.shortcut().toString()
            if keys:
                out.append((group, a.text().replace("&", "").rstrip("…").split(":")[0], keys))
    return out


class ShortcutsDialog(QDialog):
    def __init__(self, menubar, parent=None):
        super().__init__(parent)
        chrome(self)
        self.setWindowTitle("단축키 목록")
        self.resize(520, 560)
        lay = QVBoxLayout(self)
        rows = menu_shortcuts(menubar) + EXTRA_KEYS
        self.table = QTableWidget(len(rows), 3)
        self.table.setHorizontalHeaderLabels(["메뉴", "기능", "단축키"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(text))
        self.table.resizeColumnToContents(0)
        self.table.resizeColumnToContents(2)
        lay.addWidget(self.table)
        b = QPushButton("닫기")
        b.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(b)
        lay.addLayout(row)


class ErrorLogDialog(QDialog):
    """Shows error.log (+ versions) so a friend can copy it and send it."""

    def __init__(self, parent=None, log_path=None):
        super().__init__(parent)
        chrome(self)
        self.log = Path(log_path) if log_path else LOG
        self.setWindowTitle("오류 기록")
        self.resize(720, 520)
        lay = QVBoxLayout(self)
        lay.addWidget(ThemedLabel("프로그램이 예상치 못하게 멈췄을 때의 기록이에요. 문제를 물어볼 때 "
                                  "<b>모두 복사</b>를 눌러 메시지에 붙여넣어 보내 주세요."))
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFont("Consolas", 9))
        lay.addWidget(self.text, 1)
        row = QHBoxLayout()
        self.b_copy = QPushButton("모두 복사 (버전 정보 포함)")
        self.b_copy.setObjectName("primary")
        self.b_copy.clicked.connect(self.copy_all)
        b_folder = QPushButton("파일 위치 열기")
        b_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log.parent))))
        self.b_clear = QPushButton("기록 지우기")
        self.b_clear.clicked.connect(self.clear_log)
        b_close = QPushButton("닫기")
        b_close.clicked.connect(self.accept)
        for b in (self.b_copy, b_folder, self.b_clear):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)
        self.refresh()

    def log_text(self) -> str:
        try:
            return self.log.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return ""

    def refresh(self):
        t = self.log_text()
        self.text.setPlainText(env_info() + "\n\n" + (t or "(아직 오류 기록이 없어요 — 좋은 일이에요!)"))
        self.b_clear.setEnabled(bool(t))

    def copy_all(self):
        QApplication.clipboard().setText(self.text.toPlainText())
        self.b_copy.setText("복사했어요 ✓")

    def clear_log(self):
        try:
            self.log.unlink()
        except OSError:
            pass
        self.refresh()


# ---------------------------------------------------------------- new version notice
def parse_version(text: str):
    m = re.search(r"""__version__\s*=\s*["']([\d.]+)["']""", text or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def is_newer(remote: str, local: str = __version__) -> bool:
    r = parse_version(f'__version__ = "{remote}"')
    l_ = parse_version(f'__version__ = "{local}"')
    return bool(r and l_ and r > l_)


class UpdateChecker(QThread):
    """Reads the version on GitHub in the background. Emits the newer version string, or nothing."""
    newer = pyqtSignal(str)

    def __init__(self, parent=None, url=VERSION_URL):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            with urllib.request.urlopen(self.url, timeout=5) as r:
                v = parse_version(r.read(4096).decode("utf-8", "replace"))
        except Exception:
            return                                    # offline / blocked: say nothing
        if v and v > parse_version(f'__version__ = "{__version__}"'):
            self.newer.emit(".".join(map(str, v)))
