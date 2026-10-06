"""Study folders: shortcuts on the left of the open dialog, and where that dialog starts."""
import os
import re
import threading
from pathlib import Path

from PyQt5.QtCore import QDir, QObject, QStandardPaths, Qt, QUrl, pyqtSignal
from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QListWidget,
                             QListWidgetItem, QPushButton, QVBoxLayout)

from .theme import ThemedLabel, chrome

KEY = "studyFolders"                 # QSettings key holding the list of folder paths
MAIN_NAME = "main.py"                # compared in lower case, like locate.main_py_in does
MAX_DEPTH = 6                        # folders below a study folder that are searched for Main files
MAX_MAIN_FILES = 500                 # per study folder, so registering a whole drive cannot run away
SKIP_DIRS = {"__pycache__", "node_modules", "venv", "env", "site-packages"}   # plus every ".name" folder


def _same(a, b) -> bool:
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


def load_folders(settings) -> list[str]:
    raw = settings.value(KEY, [])
    if isinstance(raw, str):                 # QSettings hands back a plain str when only one was saved
        raw = [raw]
    return [str(p) for p in (raw or []) if str(p).strip()]


def save_folders(settings, folders):
    if folders:
        settings.setValue(KEY, list(folders))
    else:
        settings.remove(KEY)


def existing_folders(folders) -> list[str]:
    return [f for f in folders if os.path.isdir(f)]


def add_folder(folders, new) -> list[str]:
    new = str(new or "").strip()
    if not new or any(_same(f, new) for f in folders):
        return list(folders)
    return [*folders, os.path.normpath(new)]


def remove_folder(folders, path) -> list[str]:
    return [f for f in folders if not _same(f, path)]


def _home() -> str:
    docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
    return docs if docs and os.path.isdir(docs) else str(Path.home())


def start_dir(current, last, folders) -> str:
    """Folder the open dialog starts in: open file's folder, last opened folder, first study folder, home."""
    for cand in (current, last):
        if cand and os.path.isdir(str(cand)):
            return str(cand)
    alive = existing_folders(folders)
    return alive[0] if alive else _home()


def standard_places() -> list[str]:
    places = []
    for loc in (QStandardPaths.HomeLocation, QStandardPaths.DesktopLocation,
                QStandardPaths.DocumentsLocation, QStandardPaths.DownloadLocation):
        p = QStandardPaths.writableLocation(loc)
        if p and os.path.isdir(p):
            places.append(p)
    return places + [d.absoluteFilePath() for d in QDir.drives()]


def sidebar_paths(folders) -> list[str]:
    out = []
    for p in [*existing_folders(folders), *standard_places()]:
        if not any(_same(p, q) for q in out):
            out.append(p)
    return out


def make_file_dialog(parent, title, start, name_filter, folders) -> QFileDialog:
    """Qt's own file dialog (the Windows one cannot show extra shortcuts) with the study folders on the left."""
    dlg = QFileDialog(parent, title, start, name_filter)
    dlg.setOption(QFileDialog.DontUseNativeDialog, True)
    dlg.setFileMode(QFileDialog.ExistingFile)
    dlg.setAcceptMode(QFileDialog.AcceptOpen)
    dlg.setSidebarUrls([QUrl.fromLocalFile(p) for p in sidebar_paths(folders)])
    return dlg


def pick_file(parent, title, start, name_filter, folders) -> str:
    dlg = make_file_dialog(parent, title, start, name_filter, folders)
    if dlg.exec_() == QDialog.Accepted and dlg.selectedFiles():
        return dlg.selectedFiles()[0]
    return ""


def _natural(text: str) -> list:
    """Sort key that puts lesson2 before lesson10."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def find_main_files(folder, max_depth=MAX_DEPTH, limit=MAX_MAIN_FILES) -> list[Path]:
    """Files called main.py (any case) below `folder`, in natural order of their path."""
    root = Path(folder)
    found: list[Path] = []
    for here, dirs, files in os.walk(root):
        depth = len(Path(here).relative_to(root).parts)
        dirs[:] = sorted((d for d in dirs if not d.startswith(".") and d.lower() not in SKIP_DIRS),
                         key=_natural) if depth < max_depth else []
        for name in sorted(files, key=_natural):
            if name.lower() == MAIN_NAME:
                found.append(Path(here) / name)
        if len(found) >= limit:
            break
    found.sort(key=lambda p: _natural(str(p.relative_to(root))))
    return found[:limit]


def main_label(folder, path) -> str:
    """'ex1_2_02 / Main.py' style label: the file's folder relative to its study folder."""
    folder, path = Path(folder), Path(path)
    rel = path.parent.relative_to(folder)
    return f"{rel if rel.parts else folder.name} / {path.name}"


class MainFilesScanner(QObject):
    """Looks for the Main files of the study folders on a worker thread so the window never waits.

    `ready` carries {folder: [path, ...]} once the newest scan is done; older scans are dropped.
    """
    _done = pyqtSignal(int, object)
    ready = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result: dict[str, list[str]] = {}
        self.busy = False
        self._gen = 0
        self._done.connect(self._on_done)

    def scan(self, folders):
        self._gen += 1
        self.busy = True
        threading.Thread(target=self._run, args=(self._gen, existing_folders(folders)), daemon=True).start()

    def _run(self, gen, folders):
        out = {f: [str(p) for p in find_main_files(f)] for f in folders}
        try:
            self._done.emit(gen, out)                # queued: handled on the GUI thread
        except RuntimeError:                         # the window is already gone
            pass

    def _on_done(self, gen, out):
        if gen != self._gen:
            return
        self.busy = False
        self.result = out
        self.ready.emit(out)


class StudyFoldersDialog(QDialog):
    def __init__(self, folders, parent=None):
        super().__init__(parent)
        chrome(self)                           # the app look for this dialog
        self.setWindowTitle("학습 폴더 관리")
        self.resize(560, 320)
        self._folders = list(folders)
        lay = QVBoxLayout(self)
        lay.addWidget(ThemedLabel("자주 여는 학습 폴더를 등록하면 파일 열기 창 왼쪽에 바로가기로 나와요."))
        self.view = QListWidget()
        lay.addWidget(self.view)
        row = QHBoxLayout()
        add = QPushButton("추가…")
        add.clicked.connect(self._choose)
        remove = QPushButton("삭제")
        remove.clicked.connect(self.remove_selected)
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch(1)
        lay.addLayout(row)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Ok).setText("저장")
        box.button(QDialogButtonBox.Cancel).setText("취소")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        self._refill()

    def folders(self) -> list[str]:
        return list(self._folders)

    def add_path(self, path):
        self._folders = add_folder(self._folders, path)
        self._refill()

    def remove_selected(self):
        row = self.view.currentRow()
        if 0 <= row < len(self._folders):
            del self._folders[row]
            self._refill()

    def _choose(self):
        start = self._folders[-1] if self._folders and os.path.isdir(self._folders[-1]) else _home()
        d = QFileDialog.getExistingDirectory(self, "학습할 폴더 고르기", start)
        if d:
            self.add_path(d)

    def _refill(self):
        self.view.clear()
        for f in self._folders:
            it = QListWidgetItem(f if os.path.isdir(f) else f"{f}    (폴더를 찾을 수 없어요)")
            it.setData(Qt.UserRole, f)
            self.view.addItem(it)
