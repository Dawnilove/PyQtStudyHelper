"""여러 파일 탭, 저장, 지난 탭 다시 열기, 저장 안 한 변경 묻기."""
from pathlib import Path

from PyQt5.QtWidgets import QMessageBox, QTabBar, QToolButton

from . import recovery
from .locate import import_mismatch, read_text


class TabsMixin:
    """MainWindow part: 여러 파일 탭, 저장, 지난 탭 다시 열기, 저장 안 한 변경 묻기."""

    def restore_session(self) -> bool:
        """Re-open the tabs that were open when the app was closed (files that still exist)."""
        if self.settings.value("session/restore", True) in (False, "false"):
            return False
        tabs = self.settings.value("session/tabs", []) or []
        if isinstance(tabs, str):              # QSettings gives a plain str for a one-item list
            tabs = [tabs]
        tabs = [t for t in tabs if t and Path(t).is_file()]
        if not tabs:
            return False
        for t in tabs:
            self.open_path(t)
        cur = self.settings.value("session/current", "")
        if cur and cur in tabs and (not self.py_path or str(self.py_path) != cur):
            self.open_path(cur)
        self._status(f"지난번에 열어 둔 파일 {len(tabs)}개를 다시 열었어요.")
        return self.py_path is not None

    def _tab_index(self, path) -> int:
        for i in range(self.file_tabs.count()):
            if self.file_tabs.tabData(i) == str(path):
                return i
        return -1

    def _select_tab(self, path):
        i = self._tab_index(path)
        self.file_tabs.blockSignals(True)
        if i < 0:
            i = self.file_tabs.addTab(Path(path).name)
            self.file_tabs.setTabData(i, str(path))
            self.file_tabs.setTabToolTip(i, str(path))
            # our own ✕ (text, so it follows the theme's text colour; the built-in icon is black)
            x = QToolButton()
            x.setText("✕")
            x.setAutoRaise(True)
            x.setFixedSize(18, 18)
            x.setStyleSheet("QToolButton { padding: 0; border: none; border-radius: 3px; } "
                            "QToolButton:hover { background: rgba(128, 128, 128, 90); }")
            x.setToolTip("탭 닫기")
            x.clicked.connect(lambda _=False, b=x: self._close_tab_of(b))
            self.file_tabs.setTabButton(i, QTabBar.RightSide, x)
        self.file_tabs.setCurrentIndex(i)
        self.file_tabs.blockSignals(False)
        self.file_tabs.setVisible(True)

    def _close_tab_of(self, button):
        for i in range(self.file_tabs.count()):
            if self.file_tabs.tabButton(i, QTabBar.RightSide) is button:
                self.close_tab(i)
                return

    def _stash_current(self):
        """Leaving the shown file: keep its unsaved edits (so switching tabs never asks or loses work)."""
        if self.py_path and self.editor.document().isModified():
            self._stash[str(self.py_path)] = {"text": self.editor.toPlainText(),
                                              "line": self.editor.textCursor().blockNumber()}
            self.editor.document().setModified(False)
            self._refresh_tab_titles()

    def _refresh_tab_titles(self):
        for i in range(self.file_tabs.count()):
            path = self.file_tabs.tabData(i)
            cur = bool(self.py_path) and path == str(self.py_path)
            dirty = self.editor.document().isModified() if cur else path in self._stash
            self.file_tabs.setTabText(i, ("● " if dirty else "") + Path(path).name)

    def _on_tab_changed(self, i):
        path = self.file_tabs.tabData(i) if i >= 0 else None
        if path and (not self.py_path or str(self.py_path) != path):
            if not self.open_path(path) and self.py_path:
                self._select_tab(self.py_path)

    def close_tab(self, i):
        path = self.file_tabs.tabData(i)
        is_cur = bool(self.py_path) and path == str(self.py_path)
        if is_cur:
            if not self._confirm_discard():
                return
        elif path in self._stash:
            r = QMessageBox.question(self, "저장하지 않은 변경", f"{Path(path).name} 의 변경을 저장할까요?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Cancel:
                return
            if r == QMessageBox.Save and not self._save_stashed(path):
                return
            self._stash.pop(path, None)
            recovery.clear(path)
        self.file_tabs.blockSignals(True)
        self.file_tabs.removeTab(i)
        self.file_tabs.blockSignals(False)
        if self.file_tabs.count() == 0:
            self.file_tabs.setVisible(False)
            self.stack.setCurrentIndex(0)
            self.py_path = None
            self.editor.document().setModified(False)
            self._update_title()
        elif is_cur:
            self.py_path = None
            self.editor.document().setModified(False)
            self.open_path(self.file_tabs.tabData(min(i, self.file_tabs.count() - 1)))
        self._refresh_tab_titles()

    def _save_stashed(self, path) -> bool:
        try:
            _, enc, crlf = read_text(Path(path))
            with open(path, "w", encoding=enc, newline="\r\n" if crlf else "\n") as f:
                f.write(self._stash[path]["text"])
        except OSError as e:
            QMessageBox.critical(self, "저장 실패", str(e))
            return False
        return True

    def _confirm_all(self) -> bool:
        """Closing the app: ask about the shown file, then about every other tab with unsaved edits."""
        if not self._confirm_discard():
            return False
        for path in list(self._stash):
            r = QMessageBox.question(self, "저장하지 않은 변경", f"{Path(path).name} 의 변경을 저장할까요?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Cancel or (r == QMessageBox.Save and not self._save_stashed(path)):
                return False
            self._stash.pop(path, None)
            recovery.clear(path)
        return True

    def save_py(self) -> bool:
        if not self.py_path:
            return False
        try:
            with open(self.py_path, "w", encoding=self.encoding,
                      newline="\r\n" if self.crlf else "\n") as f:
                f.write(self.editor.toPlainText())
        except OSError as e:
            QMessageBox.critical(self, "저장 실패", str(e))
            return False
        self.editor.document().setModified(False)
        recovery.clear(self.py_path)
        self._missing.pop(self.py_path, None)
        self._mismatch = import_mismatch(self.py_path)
        self.run_check()
        self._status(f"{self.py_path.name} 저장함")
        return True

    def _confirm_discard(self) -> bool:
        if not self.py_path or not self.editor.document().isModified():
            return True
        r = QMessageBox.question(self, "저장하지 않은 변경", f"{self.py_path.name} 의 변경을 저장할까요?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save_py()
        if r == QMessageBox.Discard:
            recovery.clear(self.py_path)
            return True
        return False
