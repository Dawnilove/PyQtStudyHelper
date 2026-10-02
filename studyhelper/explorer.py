"""왼쪽 탐색기(VS Code 방식): 학습 폴더가 있으면 폴더 트리, 없으면 최근 파일.

Clicking a .py / .ui file opens it. Folders load their contents when expanded (so a big
folder doesn't slow the start), and the file open in the editor is highlighted.
"""
import os
import re
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QStyle, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from .studyfolders import SKIP_DIRS

SHOWN_SUFFIXES = {".py", ".ui"}
MAX_ENTRIES = 400                  # per folder; a folder with thousands of files must not freeze the app
PATH_ROLE = Qt.UserRole
KIND_ROLE = Qt.UserRole + 1        # "root" | "dir" | "file" | "more" | "placeholder"


def _natural(text: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def list_dir(folder: str) -> tuple[list[str], list[str], bool]:
    """(sub-folders, .py/.ui files, truncated) of `folder`, natural order, hidden/junk skipped."""
    dirs, files = [], []
    try:
        with os.scandir(folder) as it:
            for e in it:
                name = e.name
                if name.startswith("."):
                    continue
                try:
                    if e.is_dir(follow_symlinks=False):
                        if name.lower() not in SKIP_DIRS and not name.endswith(".egg-info"):
                            dirs.append(name)
                    elif Path(name).suffix.lower() in SHOWN_SUFFIXES:
                        files.append(name)
                except OSError:
                    continue
    except OSError:
        return [], [], False
    dirs.sort(key=_natural)
    files.sort(key=_natural)
    truncated = len(dirs) + len(files) > MAX_ENTRIES
    dirs = dirs[:MAX_ENTRIES]
    files = files[:max(0, MAX_ENTRIES - len(dirs))]
    return dirs, files, truncated


def _same(a, b) -> bool:
    try:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
    except (OSError, ValueError):
        return False


class ExplorerPanel(QWidget):
    openRequested = pyqtSignal(str)       # file path
    manageRequested = pyqtSignal()        # "학습 폴더 관리…"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._folders: list[str] = []
        self._recent: list[str] = []
        self._current: str = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QHBoxLayout()
        head.setContentsMargins(6, 4, 4, 4)
        self.title = QLabel()
        self.title.setObjectName("explorerTitle")
        head.addWidget(self.title, 1)
        self.b_manage = QPushButton("폴더")
        self.b_manage.setToolTip("학습 폴더 추가·삭제")
        self.b_manage.setFlat(True)
        self.b_manage.clicked.connect(self.manageRequested)
        self.b_refresh = QPushButton("새로고침")
        self.b_refresh.setToolTip("폴더 내용을 다시 읽어요")
        self.b_refresh.setFlat(True)
        self.b_refresh.clicked.connect(self.refresh)
        head.addWidget(self.b_manage)
        head.addWidget(self.b_refresh)
        lay.addLayout(head)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setUniformRowHeights(True)
        self.tree.setEditTriggers(QTreeWidget.NoEditTriggers)
        self.tree.itemClicked.connect(self._on_clicked)
        self.tree.itemExpanded.connect(self._on_expanded)
        lay.addWidget(self.tree, 1)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setObjectName("explorerHint")
        self.hint.setMargin(6)
        lay.addWidget(self.hint)

    # ------------------------------------------------------------------ data
    def set_data(self, folders, recent, current=""):
        """folders: registered study folders (existing); recent: recently opened files."""
        self._folders = list(folders)
        self._recent = list(recent)
        self._current = current or ""
        self.refresh()

    def set_current(self, path):
        self._current = str(path) if path else ""
        self._mark_current(reveal=True)

    def refresh(self):
        expanded = self._expanded_paths()
        self.tree.setUpdatesEnabled(False)
        self.tree.clear()
        if self._folders:
            self.title.setText("<b>학습 폴더</b>")
            self.hint.setText("<span style='color:#888'>파일을 클릭하면 열려요. 폴더·.py·.ui만 보여요.</span>")
            for f in self._folders:
                self.tree.addTopLevelItem(self._folder_item(f, Path(f).name or f, root=True))
            for i in range(self.tree.topLevelItemCount()):
                self._restore_expanded(self.tree.topLevelItem(i), expanded)
        else:
            self.title.setText("<b>최근 파일</b>")
            self.hint.setText("<span style='color:#888'>학습 폴더를 등록하면 폴더 목록이 여기 나와요 "
                              "(위의 <b>폴더</b> 버튼).</span>")
            if not self._recent:
                it = QTreeWidgetItem(["(아직 연 파일이 없어요)"])
                it.setFlags(Qt.NoItemFlags)
                self.tree.addTopLevelItem(it)
            for p in self._recent:
                self.tree.addTopLevelItem(self._recent_item(p))
        self.tree.setUpdatesEnabled(True)
        self._mark_current(reveal=bool(self._folders))

    # ------------------------------------------------------------------ items
    def _icon(self, kind):
        st = self.style()
        return st.standardIcon({"root": QStyle.SP_DirHomeIcon, "dir": QStyle.SP_DirIcon,
                                "file": QStyle.SP_FileIcon}.get(kind, QStyle.SP_FileIcon))

    def _folder_item(self, path, label, root=False):
        it = QTreeWidgetItem([label])
        it.setData(0, PATH_ROLE, path)
        it.setData(0, KIND_ROLE, "root" if root else "dir")
        it.setIcon(0, self._icon("root" if root else "dir"))
        it.setToolTip(0, path)
        if root:
            f = it.font(0)
            f.setBold(True)
            it.setFont(0, f)
        ph = QTreeWidgetItem([""])
        ph.setData(0, KIND_ROLE, "placeholder")
        it.addChild(ph)                                   # gives the expand arrow; replaced on expand
        return it

    def _file_item(self, path):
        it = QTreeWidgetItem([Path(path).name])
        it.setData(0, PATH_ROLE, path)
        it.setData(0, KIND_ROLE, "file")
        it.setIcon(0, self._icon("file"))
        it.setToolTip(0, path)
        if Path(path).suffix.lower() == ".ui":
            it.setForeground(0, QColor("#6f42c1"))
        elif Path(path).name.lower() == "main.py":
            f = it.font(0)
            f.setBold(True)
            it.setFont(0, f)
        return it

    def _recent_item(self, path):
        p = Path(path)
        it = QTreeWidgetItem([f"{p.parent.name} / {p.name}"])
        it.setData(0, PATH_ROLE, str(path))
        it.setData(0, KIND_ROLE, "file")
        it.setIcon(0, self._icon("file"))
        it.setToolTip(0, str(path))
        return it

    def _load_children(self, item):
        if item.childCount() == 1 and item.child(0).data(0, KIND_ROLE) == "placeholder":
            item.takeChild(0)
            folder = item.data(0, PATH_ROLE)
            dirs, files, truncated = list_dir(folder)
            for d in dirs:
                item.addChild(self._folder_item(os.path.join(folder, d), d))
            for f in files:
                item.addChild(self._file_item(os.path.join(folder, f)))
            if not dirs and not files:
                e = QTreeWidgetItem(["(.py·.ui 파일이 없어요)"])
                e.setFlags(Qt.NoItemFlags)
                item.addChild(e)
            if truncated:
                m = QTreeWidgetItem([f"… 항목이 많아 {MAX_ENTRIES}개까지만 보여요"])
                m.setFlags(Qt.NoItemFlags)
                item.addChild(m)

    # ------------------------------------------------------------------ events
    def _on_expanded(self, item):
        self._load_children(item)

    def _on_clicked(self, item, _col):
        kind = item.data(0, KIND_ROLE)
        if kind == "file":
            self.openRequested.emit(item.data(0, PATH_ROLE))
        elif kind in ("root", "dir"):
            item.setExpanded(not item.isExpanded())

    # ------------------------------------------------------------------ state
    def _expanded_paths(self) -> set:
        out = set()

        def walk(it):
            if it.isExpanded() and it.data(0, PATH_ROLE):
                out.add(os.path.normcase(it.data(0, PATH_ROLE)))
            for i in range(it.childCount()):
                walk(it.child(i))

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        return out

    def _restore_expanded(self, item, paths):
        if os.path.normcase(item.data(0, PATH_ROLE) or "") in paths:
            self._load_children(item)
            item.setExpanded(True)
            for i in range(item.childCount()):
                self._restore_expanded(item.child(i), paths)

    def _mark_current(self, reveal):
        """Select the open file; with study folders also open the folders down to it."""
        cur = self._current
        if not cur:
            self.tree.clearSelection()
            return
        self.tree.blockSignals(True)
        try:
            target = None
            if self._folders:
                for i in range(self.tree.topLevelItemCount()):
                    root = self.tree.topLevelItem(i)
                    base = root.data(0, PATH_ROLE)
                    try:
                        rel = Path(cur).resolve().relative_to(Path(base).resolve())
                    except (ValueError, OSError):
                        continue
                    if reveal:
                        item = root
                        for part in rel.parts[:-1]:
                            self._load_children(item)
                            item.setExpanded(True)
                            item = next((item.child(j) for j in range(item.childCount())
                                         if item.child(j).text(0).lower() == part.lower()), None)
                            if item is None:
                                break
                        if item is not None:
                            self._load_children(item)
                            item.setExpanded(True)
                            target = next((item.child(j) for j in range(item.childCount())
                                           if item.child(j).data(0, PATH_ROLE)
                                           and _same(item.child(j).data(0, PATH_ROLE), cur)), None)
                    break
            else:
                target = next((self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())
                               if self.tree.topLevelItem(i).data(0, PATH_ROLE)
                               and _same(self.tree.topLevelItem(i).data(0, PATH_ROLE), cur)), None)
            self.tree.clearSelection()
            if target is not None:
                target.setSelected(True)
                self.tree.setCurrentItem(target)
                self.tree.scrollToItem(target)
        finally:
            self.tree.blockSignals(False)

    # -------------------------------------------------------------- for tests
    def top_texts(self) -> list[str]:
        return [self.tree.topLevelItem(i).text(0) for i in range(self.tree.topLevelItemCount())]

    def selected_path(self) -> str:
        it = self.tree.currentItem()
        return it.data(0, PATH_ROLE) if it is not None and it.isSelected() else ""
