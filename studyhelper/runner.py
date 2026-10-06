"""실행(F5)·중지, 실행 결과와 input(), 에러 해설, Designer 열기."""
import shutil
import sys
from pathlib import Path

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, QProcess, QProcessEnvironment, Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QMessageBox, QPlainTextEdit

from . import errors, theme


class OutputView(QPlainTextEdit):
    """Run output; clicking a 'File "...", line N' traceback line jumps there."""
    frameClicked = pyqtSignal(str, int)

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 10))
        self.setMaximumBlockCount(5000)          # an endless print loop must not freeze the app
        self.viewport().setMouseTracking(True)

    def _frame_at(self, pos):
        m = errors.FRAME.match(self.cursorForPosition(pos).block().text())
        return (m.group(1), int(m.group(2))) if m else None

    def mouseMoveEvent(self, e):
        super().mouseMoveEvent(e)
        self.viewport().setCursor(Qt.PointingHandCursor if self._frame_at(e.pos()) else Qt.IBeamCursor)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        f = self._frame_at(e.pos())
        if f and not self.textCursor().hasSelection():
            self.frameClicked.emit(*f)


def find_designer() -> str | None:
    exe = shutil.which("designer")
    if exe:
        return exe
    base = Path(sys.executable).parent
    for p in (base / "Scripts" / "designer.exe",
              base / "Lib" / "site-packages" / "QtDesigner" / "designer.exe",
              base / "Lib" / "site-packages" / "qt5_applications" / "Qt" / "bin" / "designer.exe"):
        if p.exists():
            return str(p)
    return None


class RunMixin:
    """MainWindow part: 실행(F5)·중지, 실행 결과와 input(), 에러 해설, Designer 열기."""

    def open_designer(self):
        exe = find_designer()
        if not exe:
            QMessageBox.warning(self, "Designer", "designer.exe 를 찾지 못했어요. (pip install PyQt5Designer)")
            return
        if not QProcess.startDetached(exe, [str(self.ui_path)] if self.ui_path else []):
            QMessageBox.warning(self, "Designer", f"실행하지 못했어요: {exe}")

    def _refresh_generated_py(self):
        """Safety net: rebuild gui.py when gui.ui is newer and Main.py imports it."""
        if not self.ui_path:
            return
        gen = self.ui_path.with_suffix(".py")
        uses_it = f"from {self.ui_path.stem} import" in self.editor.toPlainText() \
            or f"import {self.ui_path.stem}" in self.editor.toPlainText()
        if not uses_it:
            return
        if gen.exists() and gen.stat().st_mtime >= self.ui_path.stat().st_mtime:
            return
        why = "보다 오래돼서" if gen.exists() else "로부터 아직 만들어지지 않아서"
        with open(gen, "w", encoding="utf-8") as f:
            uic.compileUi(str(self.ui_path), f, execute=True)
        self._out(f"[도우미] {gen.name} 가 {self.ui_path.name} {why} 새로 만들었어요.\n", "#0b6bcb")

    def run(self):
        if not self.py_path:
            return
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.stop()
        if self.editor.document().isModified() and not self.save_py():
            return
        self.output.clear()
        self._stderr = ""
        self.editor.error = None
        self.editor.set_issues(self.editor.issues)
        self.bottom.setCurrentWidget(self.run_box)
        try:
            self._refresh_generated_py()
        except Exception as e:
            self._out(f"[도우미] gui.py 생성 실패: {e}\n", "#c0392b")
        proc = QProcess(self)
        proc.setWorkingDirectory(str(self.py_path.parent))
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUNBUFFERED", "1")
        proc.setProcessEnvironment(env)
        # bind to *this* process: a previous run that is still shutting down must not write here
        proc.readyReadStandardOutput.connect(
            lambda: proc is self.proc and self._out(bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")))
        proc.readyReadStandardError.connect(lambda: proc is self.proc and self._on_stderr())
        proc.finished.connect(lambda code, st: proc is self.proc and self._on_finished(code, st))
        proc.errorOccurred.connect(lambda err: proc is self.proc and err == QProcess.FailedToStart
                                   and self._out(f"[도우미] 파이썬을 실행하지 못했어요: {sys.executable}\n", "#c0392b"))
        self.proc = proc
        self._run_py = self.py_path
        self._out(f"> python {self.py_path.name}\n", "#888888")
        proc.start(sys.executable, ["-u", str(self.py_path)])
        self.a_stop.setEnabled(True)
        self._set_input_enabled(True)

    def _set_input_enabled(self, on):
        self.stdin_edit.setEnabled(on)
        self.b_send.setEnabled(on)
        if not on:
            self.stdin_edit.clear()

    def send_input(self):
        """One line typed by the student -> the running program's input()."""
        if not (self.proc and self.proc.state() == QProcess.Running):
            return
        text = self.stdin_edit.text()
        self.proc.write((text + "\n").encode("utf-8"))
        self._out(text + "\n", "#2b8a3e")
        self.stdin_edit.clear()

    def stop(self):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(2000)
            self.a_stop.setEnabled(False)
        self._set_input_enabled(False)

    def _on_stderr(self):
        text = bytes(self.proc.readAllStandardError()).decode("utf-8", "replace")
        self._stderr += text
        self._out(text, "#c0392b")

    def _on_finished(self, code, _status):
        self.a_stop.setEnabled(False)
        self._set_input_enabled(False)
        self._out(f"\n[종료 코드 {code}]\n", "#888888")
        names, _tops = self._all_ui_names()
        top = self.model.top.name if self.model and self.model.top else None
        run_py = getattr(self, "_run_py", None) or self.py_path
        ex = errors.explain(self._stderr, run_py.parent, names, top)
        if ex is None:
            return
        self._out(f"\n[도우미 해설] {ex.error_line}\n", "#6f42c1")
        if ex.hint:
            self._out(f"  → {ex.hint}\n", "#6f42c1")
        if ex.file is not None and ex.line:
            self._out(f'  File "{ex.file}", line {ex.line}   ← 클릭하면 이동\n', "#0b6bcb")
            if self._same_file(ex.file, self.py_path):
                self.editor.set_error(ex.line - 1, ex.hint or ex.error_line)
                self.editor.go_to_line(ex.line - 1)
                self._status(f"에러 위치: {ex.file.name} {ex.line}번째 줄", 10000)

    @staticmethod
    def _same_file(a, b) -> bool:
        try:
            return Path(a).resolve() == Path(b).resolve()
        except OSError:
            return False

    def _on_frame_clicked(self, path, line):
        if self._same_file(path, self.py_path):
            self.editor.go_to_line(line - 1)
            self.editor.setFocus()
        elif Path(path).suffix == ".py" and Path(path).exists() \
                and self._same_file(Path(path).parent, self.py_path.parent):
            if self.open_path(path):
                self.editor.go_to_line(line - 1)
        else:
            self._status(f"{path} 는 내 코드가 아니라 라이브러리 파일이에요.")

    def _on_issue_clicked(self, item):
        line = item.data(Qt.UserRole)
        if line is not None:
            self.editor.go_to_line(line)
            self.editor.setFocus()

    def _out(self, text, color=None):
        cur = self.output.textCursor()
        cur.movePosition(cur.End)
        fmt = cur.charFormat()
        fmt.setForeground(QColor(theme.fg(color) if color else theme.T["text"]))
        cur.setCharFormat(fmt)
        cur.insertText(text)
        self.output.setTextCursor(cur)
        self.output.ensureCursorVisible()
