"""코드 과제 창: 과제 고르기 → 파일 만들기 → 저장할 때마다 자동 채점 (채점은 별도 프로세스에서)."""
import json
import os
import sys
from html import escape
from pathlib import Path

from PyQt5.QtCore import QProcess, QProcessEnvironment, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout, QListWidget, QListWidgetItem,
                             QPushButton, QSplitter, QVBoxLayout, QWidget)

from . import learnlog, tasks, theme
from .theme import ThemedBrowser, ThemedLabel, chrome

GRADER = Path(__file__).resolve().with_name("grader.py")
LEVELS = {1: "쉬움", 2: "보통", 3: "도전"}
TIMEOUT_MS = 20000
MARK = "@@GRADE@@"


def default_base() -> Path:
    docs = Path(os.environ.get("USERPROFILE") or Path.home()) / "Documents"
    return (docs if docs.is_dir() else Path.home()) / "PyQt과제"


def task_folder(base: Path, task: tasks.Task) -> Path:
    return Path(base) / f"{tasks.TASKS.index(task) + 1:02d}_{task.id}"


def create_task_files(folder: Path, task: tasks.Task) -> Path:
    """task.ui + starter Main.py (an existing Main.py is never overwritten). Returns Main.py."""
    folder.mkdir(parents=True, exist_ok=True)
    ui = folder / "task.ui"
    if not ui.exists():
        ui.write_text(tasks.ui_xml(task), encoding="utf-8")
    main = folder / "Main.py"
    if not main.exists():
        main.write_text(tasks.starter_main(task), encoding="utf-8")
    return main


def parse_result(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        if line.startswith(MARK):
            try:
                return json.loads(line[len(MARK):])
            except ValueError:
                break
    return {"fatal": "채점 결과를 읽지 못했어요.", "results": []}


class TaskWindow(QDialog):
    openRequested = pyqtSignal(str)          # Main.py to open in the helper
    saveRequested = pyqtSignal(str)          # save this file first if it's open with changes

    def __init__(self, settings, parent=None):
        super().__init__(parent, Qt.Window)
        chrome(self)
        self.settings = settings
        self.setWindowTitle("코드 과제")
        self.resize(900, 600)
        self._hints = {}                     # task id -> how many hints are shown
        self._proc = None
        self._grading = None                 # task id being graded
        self._timer = QTimer(self, singleShot=True, interval=TIMEOUT_MS, timeout=self._timeout)
        self._timed_out = False
        self._saving = False                 # grade() is asking the helper to save: ignore on_saved meanwhile

        lay = QVBoxLayout(self)
        lay.addWidget(ThemedLabel("과제를 고르고 <b>과제 시작</b>을 누르면 <code>task.ui</code>와 <code>Main.py</code>가 "
                                  "만들어져 열려요. Main.py를 <b>저장할 때마다 자동으로 채점</b>해요."))
        sp = QSplitter()
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._show_task)
        sp.addWidget(self.list)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.desc = ThemedBrowser()
        self.desc.setOpenExternalLinks(False)
        rl.addWidget(self.desc, 3)
        row = QHBoxLayout()
        self.b_start = QPushButton("과제 시작")
        self.b_start.setObjectName("primary")
        self.b_start.clicked.connect(self.start)
        self.b_grade = QPushButton("채점하기")
        self.b_grade.clicked.connect(self.grade)
        self.b_hint = QPushButton("힌트 보기")
        self.b_hint.clicked.connect(self.more_hint)
        self.auto = QCheckBox("저장할 때마다 자동 채점")
        self.auto.setChecked(True)
        for w in (self.b_start, self.b_grade, self.b_hint):
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(self.auto)
        rl.addLayout(row)
        self.status = ThemedLabel("")
        self.status.setWordWrap(True)
        rl.addWidget(self.status)
        self.results = QListWidget()
        self.results.setWordWrap(True)
        rl.addWidget(self.results, 2)
        sp.addWidget(right)
        sp.setSizes([250, 650])
        lay.addWidget(sp, 1)
        bottom = QHBoxLayout()
        self.folder_label = ThemedLabel("")
        bottom.addWidget(self.folder_label, 1)
        b_folder = QPushButton("과제 폴더 바꾸기…")
        b_folder.clicked.connect(self.choose_base)
        bottom.addWidget(b_folder)
        lay.addLayout(bottom)

        self._fill_list()
        self._update_folder_label()
        self.list.setCurrentRow(self._first_unsolved())

    # ---------------------------------------------------------------- data
    def base(self) -> Path:
        v = self.settings.value("tasks/folder", "")
        return Path(v) if v else default_base()

    def task(self) -> tasks.Task | None:
        i = self.list.currentRow()
        return tasks.TASKS[i] if 0 <= i < len(tasks.TASKS) else None

    def main_of(self, task) -> Path:
        return task_folder(self.base(), task) / "Main.py"

    def _first_unsolved(self) -> int:
        solved = learnlog.solved_tasks()
        return next((i for i, t in enumerate(tasks.TASKS) if t.id not in solved), 0)

    def _fill_list(self):
        solved = learnlog.solved_tasks()
        cur = self.list.currentRow()
        self.list.blockSignals(True)
        self.list.clear()
        for i, t in enumerate(tasks.TASKS, 1):
            mark = "✓ " if t.id in solved else "    "
            it = QListWidgetItem(f"{mark}{i}. {t.title}  · {LEVELS.get(t.level, '')}")
            if t.id in solved:
                it.setForeground(QColor(theme.fg("#2b8a3e")))
            self.list.addItem(it)
        self.list.blockSignals(False)
        if cur >= 0:
            self.list.setCurrentRow(cur)

    def _update_folder_label(self):
        self.folder_label.setText(f"<span style='color:#888'>과제 폴더: {escape(str(self.base()))}</span>")

    # ---------------------------------------------------------------- showing
    def _show_task(self, _row=None):
        t = self.task()
        if t is None:
            return
        if self._grading is not None and self._grading != t.id:     # switched task while grading: drop that run
            self._kill_running()
            self._grading = None
        main = self.main_of(t)
        solved = learnlog.solved_tasks().get(t.id)
        n = self._hints.get(t.id, 0)
        h = [f"<h3>{escape(t.title)} <span style='color:#888;font-size:10pt'>· {LEVELS.get(t.level, '')}</span></h3>",
             f"<p>{t.goal}</p>",
             "<p style='color:#888;margin-bottom:2px'>task.ui 에 있는 위젯</p><p style='margin-top:0'>"
             + " · ".join(f"<code>{escape(w)}</code>" for w in tasks.widget_names(t)) + "</p>"]
        if solved:
            h.append(f"<p style='color:#2b8a3e'>✓ {escape(solved)} 에 통과했어요.</p>")
        if n:
            h.append("<p><b>힌트</b></p><ol>" + "".join(f"<li>{x}</li>" for x in t.hints[:n]) + "</ol>")
        h.append(f"<p style='color:#888'>파일: {escape(str(main))}" + ("" if main.exists() else " (아직 없음)") + "</p>")
        self.desc.setHtml("".join(h))
        self.b_start.setText("이어서 하기 (파일 열기)" if main.exists() else "과제 시작")
        self.b_grade.setEnabled(main.exists())
        self.b_hint.setEnabled(n < len(t.hints))
        self.b_hint.setText(f"힌트 보기 ({n}/{len(t.hints)})")
        if self._grading != t.id:
            self.results.clear()
            self.status.setText("")

    def more_hint(self):
        t = self.task()
        if t is not None:
            self._hints[t.id] = min(len(t.hints), self._hints.get(t.id, 0) + 1)
            self._show_task()

    def choose_base(self):
        d = QFileDialog.getExistingDirectory(self, "과제 파일을 만들 폴더", str(self.base()))
        if d:
            self.settings.setValue("tasks/folder", d)
            self._update_folder_label()
            self._show_task()

    # ---------------------------------------------------------------- start / grade
    def start(self):
        t = self.task()
        if t is None:
            return
        try:
            main = create_task_files(task_folder(self.base(), t), t)
        except OSError as e:
            self.status.setText(f"<span style='color:#c0392b'>파일을 만들지 못했어요: {escape(str(e))}</span>")
            return
        self.openRequested.emit(str(main))
        self._show_task()
        self.status.setText("Main.py가 열렸어요. <code># TODO</code> 자리에 코드를 쓰고 <b>Ctrl+S</b>로 저장해 보세요.")

    def on_saved(self, path):
        """The helper saved a file: grade it if it is this task's Main.py."""
        t = self.task()
        if t is None or self._saving or not self.auto.isChecked() or not self.isVisible():
            return
        try:
            same = Path(path).resolve() == self.main_of(t).resolve()
        except OSError:
            same = False
        if same:
            self.grade()

    def grade(self):
        t = self.task()
        if t is None:
            return
        main = self.main_of(t)
        if not main.exists():
            self.status.setText("먼저 <b>과제 시작</b>을 눌러 주세요.")
            return
        self._saving = True
        try:
            self.saveRequested.emit(str(main))
        finally:
            self._saving = False
        self._kill_running()
        proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("QT_QPA_PLATFORM", "offscreen")
        proc.setProcessEnvironment(env)
        proc.setWorkingDirectory(str(main.parent))
        proc.finished.connect(lambda code, st, p=proc, tid=t.id: p is self._proc and self._finished(tid, p))
        self._proc = proc
        self._grading = t.id
        self._timed_out = False
        self.results.clear()
        self.status.setText("채점하는 중…")
        self.b_grade.setEnabled(False)
        proc.start(sys.executable, [str(GRADER), t.id, str(main)])
        self._timer.start()

    def _timeout(self):
        if self._proc is not None and self._proc.state() != QProcess.NotRunning:
            self._timed_out = True
            self._proc.kill()
            self.status.setText("<span style='color:#c0392b'>채점이 너무 오래 걸려서 멈췄어요. "
                                "끝나지 않는 반복(while)이 있는지 확인해 보세요.</span>")

    def _finished(self, task_id, proc):
        self._timer.stop()
        self.b_grade.setEnabled(True)
        out = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        if self._timed_out:
            self._grading = None
            return
        self.show_result(task_id, parse_result(out))

    def show_result(self, task_id, r: dict):
        self._grading = None
        fatal = r.get("fatal")
        passed, total = r.get("passed", 0), r.get("total", 0)
        full = not fatal and total and passed == total
        first = full and task_id not in learnlog.solved_tasks()
        if full:                                   # ✓ in the list and the description, before the results go in
            learnlog.note_task(task_id)
            self._fill_list()
            self._show_task()
        self.results.clear()
        if fatal:
            self.status.setText(f"<span style='color:#c0392b'><b>실행하지 못했어요.</b> {escape(str(fatal))}</span>")
            return
        for x in r.get("results", []):
            ok = bool(x.get("ok"))
            it = QListWidgetItem(("✓  " if ok else "✕  ") + str(x.get("label", ""))
                                 + ("" if ok or not x.get("detail") else f"\n     → {x['detail']}"))
            it.setForeground(QColor(theme.fg("#2b8a3e" if ok else "#c0392b")))
            self.results.addItem(it)
        if full:
            nxt = self._first_unsolved()
            more = " 다음 과제에 도전해 보세요!" if tasks.TASKS[nxt].id not in learnlog.solved_tasks() \
                else " 모든 과제를 다 풀었어요! 🎉"
            self.status.setText(f"<span style='color:#2b8a3e;font-size:12pt'><b>★ 통과!</b></span> "
                                f"{passed}/{total} 모두 맞았어요." + (more if first else ""))
        else:
            self.status.setText(f"{passed}/{total} 통과 — <span style='color:#c0392b'>✕</span> 표시된 것을 고쳐서 "
                                "다시 저장해 보세요. 막히면 <b>힌트 보기</b>.")

    def _kill_running(self):
        """Stop a grading run that is still going (it no longer reports: it isn't self._proc any more)."""
        old, self._proc = self._proc, None
        self._timer.stop()
        if old is not None and old.state() != QProcess.NotRunning:
            old.kill()
            old.waitForFinished(1000)

    def closeEvent(self, e):
        if self._proc is not None:
            self._kill_running()
            self._grading = None
            self.b_grade.setEnabled(True)
        super().closeEvent(e)
