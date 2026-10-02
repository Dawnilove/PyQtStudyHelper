"""Main window: wires preview, widget tree, Main.py editor, property panel and runner."""
import os
import shutil
import sys
import time
from html import escape
from pathlib import Path

from PyQt5 import uic
from PyQt5.QtCore import (QFileSystemWatcher, QProcess, QProcessEnvironment, QSettings, Qt,
                          QTimer)
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QFont, QKeySequence, QTextCursor
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (QAction, QComboBox, QDialog, QFileDialog, QLabel, QListWidget, QListWidgetItem,
                             QMainWindow, QMessageBox, QPlainTextEdit, QSizePolicy, QSplitter, QStyle,
                             QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
                             QStackedWidget, QPushButton, QHBoxLayout, QTextBrowser, QMenu)

from . import ai, checker, codeview, errors, notes
from .challenge import ChallengeWindow
from .renamedialog import RenameDialog
from .signaldialog import SignalInsertDialog
from .ui_model import rename_object, set_property
from .explainpanel import AiPanel, AiSettingsDialog, LineExplainView
from .editor import CodeEditor
from .locate import class_ui_ranges, import_mismatch, main_py_in, py_for_ui, read_text, ui_candidates
from .preview import PreviewPane
from .props import PropertyPanel
from .studyfolders import (MainFilesScanner, StudyFoldersDialog, existing_folders, load_folders, main_label,
                           pick_file, save_folders, start_dir)
from .ui_model import UiModel


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


def _chip(bg, fg, text, border=None):
    b = f"border:1px solid {border};" if border else ""
    return (f"<span style='background:{bg};color:{fg};{b}'>&nbsp;{text}&nbsp;</span>")


LEGEND = " &nbsp; ".join(f"<span style='white-space:nowrap'>{x}</span>" for x in [
    "<b>색 표시</b>",
    "<span style='color:#0b6bcb'><b><u>파란 밑줄</u></b></span> .ui 위젯 (마우스 올리기)",
    "<span style='color:#e03131'>〰 빨간 물결</span> .ui에 없는 이름",
    "<span style='color:#e8890c'>〰 주황 물결</span> 함수 없음·주의",
    _chip("#ffd666", "#5c3c00", "노랑") + " 선택한 위젯을 쓰는 곳",
    _chip("#ffd9d9", "#8a1f1f", "빨강 줄") + " 실행 에러 난 줄",
    _chip("#d3f9d8", "#1e6b2e", "초록 줄") + " 방금 넣은 코드",
    _chip("#eaf2ff", "#1f3a5f", "파랑 줄") + " 지금 줄 (해설 대상)",
    "<span style='color:#e03131'>●</span> 문제 있는 줄 번호",
])


# QWidget containers that are normal to leave unused in Main.py
_CONTAINERS = {"QWidget", "QMenuBar", "QStatusBar", "QToolBar", "QFrame", "QMenu"}


def _titled(title: str, widget: QWidget) -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    lab = QLabel(f"<b>{title}</b>")
    lab.setObjectName("paneTitle")
    lab.setMargin(4)
    lab.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # long paths must not widen the pane
    lay.addWidget(lab)
    lay.addWidget(widget, 1)
    box.title_label = lab
    return box


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("PyQtStudyHelper", "PyQtStudyHelper")
        self.scanner = MainFilesScanner(self)      # finds the study folders' Main files without freezing the window
        self.scanner.ready.connect(lambda _: self._fill_recent())
        self._scan_at = 0.0
        self.py_path: Path | None = None
        self.ui_path: Path | None = None
        self.encoding, self.crlf = "utf-8", True
        self.model: UiModel | None = None
        self.generated = ""
        self.sel: str | None = None
        self.proc: QProcess | None = None
        self._stderr = ""
        self._mismatch = None
        self._names_cache = {}           # ui path -> (mtime, names, top class)
        self._models = {}                # ui path -> (mtime, UiModel): every .ui this file uses
        self._class_ranges = []          # [(first, last, ui path, class name)] from class_ui_ranges
        self.setAcceptDrops(True)

        self.resize(1500, 900)
        self._build_ui()
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self._on_file_changed)
        self._pending = set()
        self._reload_timer = QTimer(self, singleShot=True, interval=300, timeout=self._reload_pending)
        self._check_timer = QTimer(self, singleShot=True, interval=400, timeout=self.run_check)
        self.editor.textChanged.connect(self._check_timer.start)
        self._update_title()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        st = self.style()
        A = lambda text, slot, key=None, icon=None, tip=None: self._action(text, slot, key, icon, tip)
        self.a_open = A("열기…", self.open_dialog, QKeySequence.Open, QStyle.SP_DialogOpenButton,
                        "Main.py 또는 .ui 파일 열기 (파일을 창에 끌어다 놓아도 돼요)")
        self.a_study = A("학습 폴더 관리…", self.manage_study_folders, None, None,
                         "자주 여는 학습 폴더를 등록하면 파일 열기 창 왼쪽에 바로가기로 나와요")
        self.a_save = A("저장", self.save_py, QKeySequence.Save, QStyle.SP_DialogSaveButton)
        self.a_run = A("실행", self.run, "F5", QStyle.SP_MediaPlay, "Main.py 실행 (F5)")
        self.a_stop = A("중지", self.stop, "Shift+F5", QStyle.SP_MediaStop, "실행 중인 프로그램 끄기 (Shift+F5)")
        self.a_stop.setEnabled(False)
        self.a_designer = A("Designer에서 열기", self.open_designer, "Ctrl+D", None,
                            "지금 .ui 파일을 Qt Designer로 열기 (Ctrl+D)")
        self.a_explain = A("AI에게 설명 듣기", self.ai_explain, "Ctrl+E", None,
                           "선택한 줄(없으면 현재 줄)을 AI가 설명 (Ctrl+E)")
        self.a_review = A("AI 코드 리뷰", self.ai_review, "Ctrl+Shift+R", None, "Main.py 전체 리뷰")
        self.a_ai_settings = A("AI 모델·키 설정…", self.ai_settings)
        self.a_zoom_in = A("글자 크게", lambda: self.zoom(1), QKeySequence.ZoomIn)
        self.a_zoom_out = A("글자 작게", lambda: self.zoom(-1), QKeySequence.ZoomOut)
        self.a_zoom_reset = A("글자 크기 원래대로", lambda: self.zoom(0), "Ctrl+0")
        self.a_reset_layout = A("화면 배치 초기화", self.reset_layout)
        self.a_vault = A("내 노트 폴더 연결…", self.choose_vault, None, None,
                         "내 Obsidian 볼트(또는 .md 노트 폴더)를 연결하면 위젯·코드에 맞는 노트를 찾아 줘요")
        self.a_vault_off = A("내 노트 폴더 연결 해제", self.disconnect_vault)
        self.a_legend = A("색 범례 보기", self.toggle_legend)
        self.a_legend.setCheckable(True)
        self.a_help = A("사용법", self.show_help, "F1")
        self.a_home = A("시작 화면", lambda: self.stack.setCurrentIndex(0))
        self.a_challenge = A("화면 따라 만들기 도전…", self.start_challenge, "Ctrl+T", None,
                             "목표 화면(.ui)을 보고 Designer로 똑같이 만들어 보기 — 저장할 때마다 자동 채점")
        self.challenge = None
        self.a_rename = A("objectName 바꾸기…", self.rename_selected, "F2", None,
                          "선택한 위젯의 이름을 .ui와 Main.py에서 한꺼번에 바꾸기 (F2)")

        mb = self.menuBar()
        m = mb.addMenu("파일(&F)")
        m.addAction(self.a_open)
        self.recent_menu = m.addMenu("최근 파일")
        m.addAction(self.a_study)
        m.addAction(self.a_save)
        m.addSeparator()
        m.addAction(self.a_home)
        m.addAction(A("끝내기", self.close, "Ctrl+Q"))
        m = mb.addMenu("실행(&R)")
        for a in (self.a_run, self.a_stop, self.a_designer):
            m.addAction(a)
        m = mb.addMenu("위젯(&W)")
        m.addAction(self.a_rename)
        m = mb.addMenu("도전(&C)")
        m.addAction(self.a_challenge)
        m = mb.addMenu("AI(&A)")
        for a in (self.a_explain, self.a_review):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_ai_settings)
        m = mb.addMenu("보기(&V)")
        for a in (self.a_zoom_in, self.a_zoom_out, self.a_zoom_reset):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_legend)
        m.addAction(self.a_reset_layout)
        m.addAction(self.a_vault)
        m.addAction(self.a_vault_off)
        m = mb.addMenu("도움말(&H)")
        m.addAction(self.a_help)

        tb = self.addToolBar("main")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tb.addAction(self.a_open)
        tb.addAction(self.a_save)
        tb.addSeparator()
        tb.addWidget(QLabel(" UI 파일 "))
        self.ui_combo = QComboBox()
        self.ui_combo.setMinimumWidth(160)
        self.ui_combo.setToolTip("이 파이썬 파일이 쓰는 .ui (자동으로 찾아요). 여러 개면 여기서 바꿔요")
        self.ui_combo.activated.connect(self._on_ui_combo)
        tb.addWidget(self.ui_combo)
        tb.addAction(self.a_designer)
        tb.addSeparator()
        tb.addAction(self.a_run)
        tb.addAction(self.a_stop)
        tb.addSeparator()
        tb.addAction(self.a_explain)
        tb.addAction(self.a_challenge)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        tb.addAction(self.a_help)

        self.preview = PreviewPane()
        self.preview.widgetClicked.connect(lambda n: self.select(n, "preview"))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["objectName", "클래스"])
        self.tree.setColumnWidth(0, 180)
        self.tree.itemClicked.connect(lambda it, _: self.select(it.data(0, Qt.UserRole), "tree"))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)

        self.editor = CodeEditor()
        self.editor.nameHovered.connect(lambda n, line: self.select(n, "hover", line))
        self.editor.tooltip_for = self._tooltip_for
        self.editor.document().modificationChanged.connect(lambda _: self._update_title())
        self.editor.cursorPositionChanged.connect(self._on_cursor_moved)
        self.editor.setContextMenuPolicy(Qt.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self._editor_menu)
        self.editor.zoomRequested = self.zoom
        self._font_delta = int(self.settings.value("editor/zoom", 0))
        self.zoom(None)

        self.panel = PropertyPanel()
        self.panel.lineRequested.connect(self.editor.go_to_line)
        self.panel.signalInsertRequested.connect(self.insert_signal)
        self.panel.propertyEdited.connect(self.edit_property)
        self.panel.noteRequested.connect(self.open_note)
        self.panel.renameRequested.connect(self.rename_selected)

        self.line_view = LineExplainView()
        self.line_view.anchorClicked.connect(lambda url: self.open_note(url.toString()))
        self.ai_panel = AiPanel()
        self.ai_panel.settingsRequested.connect(self.ai_settings)
        self.ai_panel.explainRequested.connect(self.ai_explain)
        self.ai_panel.reviewRequested.connect(self.ai_review)
        self.explain_tabs = QTabWidget()
        self.explain_tabs.addTab(self.line_view, "줄 해설")
        self.explain_tabs.addTab(self.ai_panel, "AI 해설")

        self.output = OutputView()
        self.output.frameClicked.connect(self._on_frame_clicked)
        self.issue_list = QListWidget()
        self.issue_list.itemClicked.connect(self._on_issue_clicked)
        self.bottom = QTabWidget()
        self.bottom.addTab(self.output, "실행 결과")
        self.bottom.addTab(self.issue_list, "검사")

        left = QSplitter(Qt.Vertical)
        self.preview_box = _titled("실시간 미리보기 · 위젯을 클릭하면 선택", self.preview)
        left.addWidget(self.preview_box)
        left.addWidget(_titled("위젯 트리 · 흐린 이름 = Main.py에서 아직 안 씀", self.tree))
        left.setSizes([520, 300])
        self.editor_box = _titled("Main.py", self.editor)
        self.legend = QLabel(LEGEND)
        self.legend.setObjectName("legend")
        self.legend.setWordWrap(True)
        self.legend.setToolTip("코드 화면의 색 표시 뜻 (보기 메뉴에서 끄고 켤 수 있어요)")
        self.editor_box.layout().addWidget(self.legend)
        right = QSplitter(Qt.Vertical)
        right.addWidget(_titled("선택한 위젯", self.panel))
        right.addWidget(_titled("해설 · 줄을 클릭하면 설명이 나와요", self.explain_tabs))
        right.setSizes([380, 440])
        top = QSplitter(Qt.Horizontal)
        top.addWidget(left)
        top.addWidget(self.editor_box)
        top.addWidget(right)
        top.setSizes([430, 640, 430])
        main = QSplitter(Qt.Vertical)
        main.addWidget(top)
        main.addWidget(self.bottom)
        main.setSizes([740, 130])
        self.splitters = {"left": left, "right": right, "top": top, "main": main}
        self._default_split = {k: sp.saveState() for k, sp in self.splitters.items()}
        for k, sp in self.splitters.items():
            state = self.settings.value(f"split2/{k}")
            if state is not None:
                sp.restoreState(state)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_welcome())
        self.stack.addWidget(main)
        self.setCentralWidget(self.stack)
        self.stack.currentChanged.connect(self._on_page_changed)
        self._on_page_changed(0)

        v = self.settings.value("vault", "")
        self.panel.vault = self.line_view.vault = Path(v) if v and Path(v).is_dir() else None
        self.a_vault_off.setEnabled(self.panel.vault is not None)

        show_legend = self.settings.value("view/legend", True) not in (False, "false")
        self.a_legend.setChecked(show_legend)
        self.legend.setVisible(show_legend)

        self.ai_status = QLabel()
        self.statusBar().addPermanentWidget(self.ai_status)
        self._update_ai_status()
        self._fill_recent()
        self._follow_timer = QTimer(self, singleShot=True, interval=250, timeout=self._follow_cursor_ui)

    def _action(self, text, slot, key=None, icon=None, tip=None) -> QAction:
        a = QAction(text, self)
        if icon is not None:
            a.setIcon(self.style().standardIcon(icon))
        if key is not None:
            a.setShortcut(QKeySequence(key))
        if tip:
            a.setToolTip(tip)
        elif key is not None:
            a.setToolTip(f"{text} ({QKeySequence(key).toString()})")
        a.triggered.connect(slot)
        self.addAction(a)
        return a

    # ------------------------------------------------------------ welcome
    def _build_welcome(self) -> QWidget:
        page = QWidget()
        page.setObjectName("welcome")
        outer = QVBoxLayout(page)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        box = QVBoxLayout()
        title = QLabel("<span style='font-size:22pt;font-weight:600'>PyQt 학습 도우미</span>")
        sub = QLabel("Designer에서 만든 <b>.ui</b>와 내가 짠 <b>Main.py</b>를 연결해서 보며 공부해요.")
        sub.setStyleSheet("color:#555;font-size:11pt")
        box.addWidget(title)
        box.addWidget(sub)
        box.addSpacing(18)
        btn = QPushButton("  파일 열기  (Ctrl+O)")
        btn.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        btn.setObjectName("bigButton")
        btn.clicked.connect(self.open_dialog)
        box.addWidget(btn)
        hint = QLabel("또는 Main.py / gui.ui / 실습 폴더를 이 창에 끌어다 놓으세요.")
        hint.setStyleSheet("color:#888")
        box.addWidget(hint)
        box.addSpacing(14)
        box.addWidget(QLabel("<b>최근 파일</b>  <span style='color:#888'>(더블클릭)</span>"))
        self.recent_list = QListWidget()
        self.recent_list.setMinimumWidth(560)
        self.recent_list.setMaximumHeight(220)
        self.recent_list.itemActivated.connect(lambda it: self.open_path(it.data(Qt.UserRole)))
        box.addWidget(self.recent_list)
        box.addSpacing(14)
        steps = QLabel(
            "<b>이렇게 써요</b><ol style='margin-left:-20px'>"
            "<li>Main.py를 열면 맞는 .ui를 자동으로 찾아 미리보기에 띄워요.</li>"
            "<li>코드의 <span style='color:#0b6bcb'><u>파란 이름</u></span>에 마우스를 올리면 화면의 위젯이 빨갛게 표시돼요.</li>"
            "<li>줄을 클릭하면 오른쪽 아래에 <b>무엇을·왜</b> 해설이 나와요. 더 궁금하면 <b>Ctrl+E</b>로 AI에게 물어봐요.</li>"
            "<li><b>F5</b>로 실행하고, 에러가 나면 쉬운 말 해설과 함께 그 줄로 이동해요.</li></ol>")
        steps.setStyleSheet("color:#333")
        box.addWidget(steps)
        row.addLayout(box)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(2)
        return page

    def _recent(self) -> list[str]:
        r = self.settings.value("recent", []) or []
        return [x for x in (r if isinstance(r, list) else [r]) if Path(x).exists()]

    def _add_recent(self, path: Path):
        r = [str(path)] + [x for x in self._recent() if x != str(path)]
        self.settings.setValue("recent", r[:10])
        self._fill_recent()

    def _fill_recent(self):
        self.recent_menu.clear()
        self.recent_list.clear()
        recent = self._recent()
        for x in recent:
            p = Path(x)
            label = f"{p.parent.name} / {p.name}"
            a = self.recent_menu.addAction(label)
            a.setToolTip(x)
            a.triggered.connect(lambda _=False, x=x: self.open_path(x))
            it = QListWidgetItem(f"{label}      {p.parent.parent}")
            it.setData(Qt.UserRole, x)
            it.setToolTip(x)
            self.recent_list.addItem(it)
        if not recent:
            it = QListWidgetItem("(아직 없음)")
            it.setFlags(Qt.NoItemFlags)
            self.recent_list.addItem(it)
        has_study = self._fill_study_sections(separator=bool(recent))
        self.recent_menu.setEnabled(bool(recent) or has_study)

    def _fill_study_sections(self, separator: bool) -> bool:
        """Under the real recent files: one section per study folder listing its Main files.

        These are searched by `self.scanner`, shown only, and never written into the saved "recent" list.
        """
        folders = existing_folders(load_folders(self.settings))
        for i, folder in enumerate(folders):
            name = Path(folder).name or folder
            found = self.scanner.result.get(folder)
            if found is None:
                note, files = "(찾는 중…)", []
            elif not found:
                note, files = "(Main 파일이 없어요)", []
            else:
                note, files = f"({len(found)}개)", found
            header = QListWidgetItem(f"학습 폴더 — {name}   {note}")
            header.setFlags(Qt.NoItemFlags)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            header.setForeground(QColor("#555555"))
            header.setToolTip(folder)
            self.recent_list.addItem(header)

            if i == 0 and separator:
                self.recent_menu.addSeparator()
            sub = self.recent_menu.addMenu(f"학습 폴더 — {name}")
            sub.setToolTipsVisible(True)
            if not files:
                sub.addAction(note).setEnabled(False)
            for x in files:
                label = main_label(folder, x)
                it = QListWidgetItem(label)
                it.setData(Qt.UserRole, x)
                it.setToolTip(x)
                self.recent_list.addItem(it)
                a = sub.addAction(label)
                a.setToolTip(x)
                a.triggered.connect(lambda _=False, x=x: self.open_path(x))
        return bool(folders)

    def _rescan_study(self, force=False):
        """Search the study folders for Main files again (at most every 30 s unless forced)."""
        now = time.monotonic()
        if not force and now - self._scan_at < 30:
            return
        self._scan_at = now
        self.scanner.scan(load_folders(self.settings))
        self._fill_recent()                        # shows "찾는 중…" right away

    def _on_page_changed(self, idx):
        on = idx == 1
        for a in (self.a_save, self.a_run, self.a_designer, self.a_explain, self.a_review, self.a_rename,
                  self.a_zoom_in, self.a_zoom_out, self.a_zoom_reset):
            a.setEnabled(on)
        self.ui_combo.setEnabled(on)
        if idx == 0:
            self._rescan_study()                   # also runs once at start-up, when the start screen is built

    # --------------------------------------------------------------- view
    def zoom(self, step):
        if step == 0:
            self._font_delta = 0
        elif step:
            self._font_delta = max(-4, min(12, self._font_delta + step))
        f = self.editor.font()
        f.setPointSize(10 + self._font_delta)
        self.editor.setFont(f)
        self.editor.setTabStopDistance(4 * self.editor.fontMetrics().horizontalAdvance(" "))
        self.editor._update_margin()
        self.settings.setValue("editor/zoom", self._font_delta)

    def reset_layout(self):
        for k, sp in self.splitters.items():
            sp.restoreState(self._default_split[k])

    def show_help(self):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("사용법")
        dlg.setTextFormat(Qt.RichText)
        dlg.setText(
            "<h3>PyQt 학습 도우미 사용법</h3>"
            "<table cellspacing=4>"
            "<tr><td><b>Ctrl+O</b></td><td>Main.py / .ui 열기 (창에 끌어다 놓아도 됨)</td></tr>"
            "<tr><td><b>Ctrl+S</b></td><td>Main.py 저장</td></tr>"
            "<tr><td><b>F5 / Shift+F5</b></td><td>실행 / 중지</td></tr>"
            "<tr><td><b>Ctrl+D</b></td><td>.ui를 Qt Designer로 열기 (저장하면 자동 반영)</td></tr>"
            "<tr><td><b>Ctrl+E</b></td><td>선택한 줄을 AI에게 설명 듣기</td></tr>"
            "<tr><td><b>F2</b></td><td>선택한 위젯의 objectName 바꾸기 (.ui와 Main.py 함께)</td></tr>"
            "<tr><td><b>Ctrl+T</b></td><td>화면 따라 만들기 도전</td></tr>"
            "<tr><td><b>시그널 탭</b></td><td>시그널 더블클릭 → connect 줄과 함수 틀 넣기</td></tr>"
            "<tr><td><b>Ctrl+휠, Ctrl+= / Ctrl+-</b></td><td>코드 글자 크기</td></tr>"
            "</table><br>"
            "<b>색 표시</b><ul>"
            "<li><span style='color:#0b6bcb'><u>파란 밑줄 이름</u></span> = .ui에 있는 위젯 (마우스를 올려 보세요)</li>"
            "<li><span style='color:#e03131'>빨간 물결</span> = .ui에 없는 이름 (오타) · "
            "<span style='color:#e8890c'>주황 물결</span> = 연결한 함수가 없음</li>"
            "<li><span style='background:#ffd9d9'>빨간 줄</span> = 실행 중 에러가 난 줄</li>"
            "<li>위젯 트리의 흐린 이름 = Main.py에서 아직 안 쓰는 위젯</li></ul>")
        dlg.exec_()

    # ----------------------------------------------------------- explain / AI
    def _on_cursor_moved(self):
        lines = self.editor.toPlainText().split("\n")
        self.line_view.show_line(lines, self.editor.textCursor().blockNumber())
        self._follow_timer.start()

    def _follow_cursor_ui(self):
        """Cursor inside `class dlgForm(QDialog, Ui_Dialog)` -> show dialog.ui."""
        if self.stack.currentIndex() != 1:
            return
        p = self.ui_for_line(self.editor.textCursor().blockNumber())
        if p is not None and p != self.ui_path:
            self.switch_ui(p)

    def _editor_menu(self, pos):
        menu = self.editor.createStandardContextMenu()
        menu.insertSeparator(menu.actions()[0])
        show_line = QAction("이 줄 해설 보기", menu)
        show_line.triggered.connect(lambda: self.explain_tabs.setCurrentWidget(self.line_view))
        menu.insertAction(menu.actions()[0], show_line)
        menu.insertAction(menu.actions()[0], self.a_review)
        menu.insertAction(menu.actions()[0], self.a_explain)
        menu.exec_(self.editor.viewport().mapToGlobal(pos))

    def _ai_context(self) -> str:
        lines = self.editor.toPlainText().split("\n")
        numbered = "\n".join(f"{i + 1:>4}| {l}" for i, l in enumerate(lines))
        parts = []
        for path, model in self.all_models().items():
            owners = ", ".join(c for _, _, p, c in self._class_ranges if p == path)
            widgets = "\n".join(f"- {n.name}: {n.cls} ({n.position_text()})"
                                 for n in model.nodes.values() if n.kind != "layout")
            parts.append(f"<ui_widgets file='{path.name}'" + (f" used_by_class='{owners}'" if owners else "")
                         + f">\n{widgets}\n</ui_widgets>")
        return (f"<code file='{self.py_path.name if self.py_path else 'Main.py'}'>\n{numbered}\n</code>\n"
                + ("\n".join(parts) or "<ui_widgets>(없음)</ui_widgets>"))

    def ai_explain(self):
        if not self.py_path:
            return
        cur = self.editor.textCursor()
        doc = self.editor.document()
        if cur.hasSelection():
            a = doc.findBlock(cur.selectionStart()).blockNumber()
            b = doc.findBlock(cur.selectionEnd()).blockNumber()
        else:
            a = b = cur.blockNumber()
        lines = self.editor.toPlainText().split("\n")[a:b + 1]
        code = "\n".join(f"{a + i + 1:>4}| {l}" for i, l in enumerate(lines))
        title = f"{a + 1}줄 설명" if a == b else f"{a + 1}~{b + 1}줄 설명"
        self.explain_tabs.setCurrentWidget(self.ai_panel)
        self.ai_panel.start(self._ai_context(), ai.EXPLAIN_TASK.format(code=code), title)

    def ai_review(self):
        if not self.py_path:
            return
        if self.editor.document().isModified():
            self.save_py()
        self.explain_tabs.setCurrentWidget(self.ai_panel)
        self.ai_panel.start(self._ai_context(), ai.REVIEW_TASK, f"{self.py_path.name} 전체 리뷰")

    def ai_settings(self):
        if AiSettingsDialog(self).exec_():
            self._update_ai_status()
            if not self.ai_panel.history:
                self.ai_panel.show_welcome()
            else:
                self.ai_panel.b_model.setText(f"AI: {ai.short_name(ai.get_model())} · 설정")

    # ------------------------------------------------- signal helper / .ui edit
    def insert_signal(self, widget, sig, all_sigs):
        if not self.py_path:
            return
        dlg = SignalInsertDialog(self.editor.toPlainText(), widget, sig, all_sigs, self,
                                 target_class=self.class_for_ui(self.ui_path))
        if not dlg.exec_() or dlg.plan is None:
            return
        if dlg.plan.existing is not None:
            self.editor.go_to_line(dlg.plan.existing)
            self._status(f"이미 {dlg.plan.existing + 1}줄에 연결돼 있어요.")
            return
        line = self.editor.insert_plan(dlg.plan)
        self.editor.setFocus()
        self._status(f"{line + 1}줄에 연결 코드, 클래스 끝에 함수 틀을 넣었어요 (Ctrl+Z로 되돌리기, Ctrl+S로 저장).", 10000)

    def edit_property(self, name, prop, value):
        if not self.ui_path:
            return
        try:
            err = set_property(self.ui_path, name, prop, value)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        if err:
            QMessageBox.warning(self, ".ui 저장", err)
            QTimer.singleShot(0, lambda: self.select(name, "reload"))
            return
        self._status(f"{self.ui_path.name} 저장: {name}.{prop} = {value!r}  "
                     "(Designer에서 이 파일을 열어 두었다면 Designer에서 다시 열어 주세요)", 12000)
        QTimer.singleShot(0, lambda: self.load_ui(self.ui_path))

    def toggle_legend(self):
        on = self.a_legend.isChecked()
        self.legend.setVisible(on)
        self.settings.setValue("view/legend", on)

    def choose_vault(self):
        d = QFileDialog.getExistingDirectory(self, "내 노트 폴더 고르기 (Obsidian 볼트 또는 .md 노트가 있는 폴더)",
                                             self.settings.value("vault", ""))
        if not d:
            return
        v = notes.find_vault(d) or Path(d)
        n = len(notes.note_files(v))
        if n == 0:
            QMessageBox.warning(self, "내 노트", f"{v} 안에 .md 노트가 없어요. 다른 폴더를 골라 주세요.")
            return
        self._set_vault(v)
        kind = "Obsidian 볼트" if (v / ".obsidian").is_dir() else "노트 폴더"
        self._status(f"{kind} 연결: {v} (노트 {n}개)", 10000)

    def disconnect_vault(self):
        self._set_vault(None)
        self._status("내 노트 폴더 연결을 해제했어요.")

    def _set_vault(self, v):
        self.settings.setValue("vault", str(v) if v else "")
        self.panel.vault = self.line_view.vault = v
        self.line_view._last = None
        self.a_vault_off.setEnabled(v is not None)
        if self.sel:
            self.select(self.sel, "reload")
        self._on_cursor_moved()

    # ---------------------------------------------------------- challenge
    def start_challenge(self):
        path = self._pick_file("도전할 목표 화면 고르기 (.ui) — 예제나 정답(_sol) .ui", self.ui_path,
                               "Qt Designer (*.ui)")
        if not path:
            return
        try:
            self.challenge = ChallengeWindow(Path(path), self)
        except Exception as e:
            QMessageBox.warning(self, "도전", f"이 .ui를 읽지 못했어요: {e}")
            return
        self.challenge.newUiRequested.connect(self._challenge_ui)
        self.challenge.show()
        if self.ui_path:
            self.challenge.update_mine(self.ui_path)

    def _challenge_ui(self, path):
        p = Path(path).resolve()
        if self.ui_combo.findData(str(p)) < 0:
            self.ui_combo.addItem(p.name, str(p))
        self.ui_combo.setCurrentIndex(self.ui_combo.findData(str(p)))
        self.stack.setCurrentIndex(1)
        self.load_ui(p)
        self._watch()
        self.open_designer()
        self._status(f"{p.name} 를 Designer로 열었어요. 저장할 때마다 도전 창이 채점해요.", 10000)

    def _tree_menu(self, pos):
        it = self.tree.itemAt(pos)
        name = it.data(0, Qt.UserRole) if it else None
        if not name:
            return
        self.select(name, "tree")
        menu = QMenu(self.tree)
        menu.addAction(self.a_rename)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def rename_selected(self):
        if not (self.model and self.ui_path and self.sel in self.model.nodes):
            self._status("먼저 미리보기·위젯 트리에서 위젯을 선택해 주세요.")
            return
        node = self.model.nodes[self.sel]
        allowed = None
        shared = any(node.name in m.nodes for p, m in self.all_models().items() if p != self.ui_path)
        mine = [(a, b) for a, b, p, _ in self._class_ranges if p == self.ui_path]
        if shared and mine:          # same name in another .ui: only touch this .ui's classes
            allowed = {i for a, b in mine for i in range(a, b + 1)}
        dlg = RenameDialog(node.name, node.cls, self.model.nodes.keys(), self.editor.toPlainText(),
                           node is self.model.top, self, allowed=allowed)
        if not dlg.exec_():
            return
        old, new = node.name, dlg.new
        try:
            err, n = rename_object(self.ui_path, old, new)
        except Exception as e:
            err, n = f"{type(e).__name__}: {e}", 0
        if err:
            QMessageBox.warning(self, "이름 바꾸기", err)
            return
        if dlg.changes:                                    # one undo step in the editor
            sb = self.editor.verticalScrollBar().value()
            cur = QTextCursor(self.editor.document())
            cur.beginEditBlock()
            cur.select(QTextCursor.Document)
            cur.insertText(dlg.new_src)
            cur.endEditBlock()
            self.editor.verticalScrollBar().setValue(sb)
        if dlg.save_py.isChecked() and self.editor.document().isModified():
            self.save_py()
        self.sel = new
        self._models.pop(self.ui_path, None)
        self.load_ui(self.ui_path)
        self._status(f"{old} → {new}: .ui {n}곳, Main.py {len(dlg.changes)}줄 바꿨어요. "
                     "(Designer에서 이 파일을 열어 두었다면 Designer에서 다시 열어 주세요)", 12000)

    def open_note(self, url):
        if url == "connect":
            self.choose_vault()
        elif url.startswith(("obsidian://", "file:")):
            QDesktopServices.openUrl(QUrl.fromEncoded(url.encode()))

    def _update_ai_status(self):
        m = ai.get_model()
        self.ai_status.setText(f"AI: {ai.short_name(m)}" if ai.ready(m)
                               else "AI: 설정 필요 (AI 메뉴 → 모델·키 설정)")

    def _update_title(self):
        name = self.py_path.name if self.py_path else "파일 없음"
        dirty = "*" if self.editor.document().isModified() else ""
        self.setWindowTitle(f"{dirty}{name} — PyQt 학습 도우미")
        if self.py_path:
            self.editor_box.title_label.setText(f"<b>{dirty}{escape(self.py_path.name)}</b> "
                                                f"<span style='color:#888'>{escape(str(self.py_path.parent))}</span>")

    def _status(self, msg, ms=6000):
        self.statusBar().showMessage(msg, ms)

    # --------------------------------------------------------------- opening
    def open_dialog(self):
        path = self._pick_file("파이썬 파일 또는 .ui 열기", self.py_path,
                               "Python / UI (*.py *.ui);;모든 파일 (*.*)")
        if path:
            self.open_path(path)

    def _pick_file(self, title, open_file, name_filter) -> str:
        """Open dialog: starts in the open file's folder (else the last opened one), study folders on its left."""
        folders = load_folders(self.settings)
        start = start_dir(str(open_file.parent) if open_file else "", self.settings.value("lastDir", ""), folders)
        return pick_file(self, title, start, name_filter, folders)

    def manage_study_folders(self):
        dlg = StudyFoldersDialog(load_folders(self.settings), self)
        if dlg.exec_() == QDialog.Accepted:
            save_folders(self.settings, dlg.folders())
            self._rescan_study(force=True)
            self._status(f"학습 폴더 {len(dlg.folders())}개를 저장했어요. 파일 열기 창 왼쪽에 나와요.")

    def open_path(self, path) -> bool:
        p = Path(path).resolve()
        if p.is_dir():
            py = main_py_in(p)
            if py is None:
                QMessageBox.warning(self, "열기", f"{p} 에서 Main.py를 찾지 못했어요.")
                return False
            p = py.resolve()
        ui = None
        if p.suffix.lower() == ".ui":
            ui = p
            py = py_for_ui(p)
            if py is None:
                QMessageBox.information(self, "열기", f"{p.name} 를 쓰는 파이썬 파일을 같은 폴더에서 "
                                                      "찾지 못했어요. 파이썬 파일을 직접 골라 주세요.")
                return False
            p = py.resolve()
        if not self._confirm_discard():
            return False

        self.py_path = p
        self._mismatch = import_mismatch(p)
        text, self.encoding, self.crlf = read_text(p)
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)

        cands = ui_candidates(p)
        self._models = {}
        self._update_class_ranges()
        self.ui_combo.clear()
        for c in cands:
            self.ui_combo.addItem(c.name, str(c))
        if ui is not None and str(ui) in [str(c) for c in cands]:
            self.ui_combo.setCurrentIndex([str(c) for c in cands].index(str(ui)))
        self.settings.setValue("lastFile", str(p))
        self.settings.setValue("lastDir", str(p.parent))
        self._update_title()
        if cands:
            self.load_ui(Path(self.ui_combo.currentData()))
            how = "코드에서 찾음" if self.ui_path in ui_candidates(p, include_folder=False) \
                else "코드에 없어서 같은 폴더의 .ui를 엶"
            self._status(f"{p.name} → {self.ui_path.name} ({how})")
        else:
            self.load_ui(None)
            self._status(f"{p.name} 가 쓰는 .ui 파일을 찾지 못했어요.")
        self._watch()
        self._add_recent(p)
        self.stack.setCurrentIndex(1)
        self._on_cursor_moved()
        return True

    def _on_ui_combo(self, idx):
        self.load_ui(Path(self.ui_combo.itemData(idx)))
        self._watch()

    def _watch(self):
        if self.watcher.files():
            self.watcher.removePaths(self.watcher.files())
        for p in (self.py_path, self.ui_path):
            if p and p.exists():
                self.watcher.addPath(str(p))

    # ------------------------------------------------------------ .ui model
    def load_ui(self, ui_path: Path | None):
        self.ui_path = ui_path
        self.model, self.generated = None, ""
        self.tree.clear()
        self.panel.clear()
        if ui_path is None:
            self.editor.set_widgets({})
            self.preview.load(None, [])
            return
        try:
            self.model = UiModel(ui_path)
        except Exception as e:  # half-written file while Designer saves
            self._status(f"{ui_path.name} 를 읽지 못했어요: {e}")
            self.editor.set_widgets({})
            return
        try:
            self.generated = codeview.generate(ui_path)
        except Exception:
            self.generated = ""
        names = list(self.model.nodes)
        self._models[ui_path] = (ui_path.stat().st_mtime, self.model)
        all_widgets = {}                      # every .ui this file uses: colours the names, feeds autocomplete
        for m in self.all_models().values():
            all_widgets.update({n: node.cls for n, node in m.nodes.items()})
        self.editor.set_widgets(all_widgets)
        cls = self.class_for_ui(ui_path)
        many = len(self.all_models()) > 1
        self.preview_box.title_label.setText(
            f"<b>실시간 미리보기 · {escape(ui_path.name)}</b>"
            + (f" <span style='color:#555'>({escape(cls)} 클래스)</span>" if cls and many else "")
            + (" <span style='color:#888'>· 다른 .ui는 그 클래스 안을 클릭하면 바뀌어요</span>" if many else ""))
        idx = self.ui_combo.findData(str(ui_path))
        if idx >= 0 and idx != self.ui_combo.currentIndex():
            self.ui_combo.setCurrentIndex(idx)
        err = self.preview.load(ui_path, names)
        if err:
            self._status(f"미리보기 오류: {err}")
        self._fill_tree()
        if self.sel in self.model.nodes:
            self.select(self.sel, "reload")
        else:
            self.sel = None
            self.preview.select(None)
            self.editor.mark(None)
        self.run_check()
        if self.challenge is not None and self.challenge.isVisible():
            self.challenge.update_mine(self.ui_path)

    def _fill_tree(self):
        self.tree.clear()
        if self.model is None or self.model.top is None:
            return
        self._items = {}

        def add(node, parent_item):
            it = QTreeWidgetItem([node.name, node.cls])
            it.setData(0, Qt.UserRole, node.name)
            if node.kind == "layout":
                f = it.font(0)
                f.setItalic(True)
                it.setFont(0, f)
                it.setForeground(0, QColor("#7a7a7a"))
                it.setForeground(1, QColor("#7a7a7a"))
            (parent_item.addChild if parent_item else self.tree.addTopLevelItem)(it)
            self._items[node.name] = it
            for ch in node.children:
                add(ch, it)

        add(self.model.top, None)
        if self.model.actions:
            group = QTreeWidgetItem(["(액션 · 버튼 그룹)", ""])
            group.setFlags(Qt.ItemIsEnabled)
            self.tree.addTopLevelItem(group)
            for a in self.model.actions:
                add(a, group)
        self.tree.expandAll()

    # ------------------------------------------------------------ selection
    # ----------------------------------------------------- several .ui per file
    def all_models(self) -> dict:
        """{ui path: UiModel} for every .ui the file uses (cached by mtime)."""
        out = {}
        if not self.py_path:
            return out
        paths = ui_candidates(self.py_path, include_folder=False)
        if self.ui_path and self.ui_path not in paths:
            paths.append(self.ui_path)
        for p in paths:
            try:
                mt = p.stat().st_mtime
                c = self._models.get(p)
                if c is None or c[0] != mt:
                    c = (mt, UiModel(p))
                    self._models[p] = c
                out[p] = c[1]
            except Exception:
                continue
        return out

    def _update_class_ranges(self):
        if not self.py_path:
            self._class_ranges = []
            return
        self._class_ranges = class_ui_ranges(self.editor.toPlainText(), self.py_path.parent,
                                             list(self.all_models()))

    def ui_for_line(self, line):
        for a, b, p, _ in self._class_ranges:
            if a <= line <= b:
                return p
        return None

    def class_for_ui(self, ui_path):
        return next((c for _, _, p, c in self._class_ranges if p == ui_path), None)

    def switch_ui(self, path):
        idx = self.ui_combo.findData(str(path))
        if idx < 0:
            self.ui_combo.addItem(path.name, str(path))
        self.load_ui(path)
        self._watch()

    def select(self, name, source, line=None):
        if not name:
            return
        target = None
        models = self.all_models() if (self.model is None or name not in self.model.nodes
                                       or line is not None) else {}
        if line is not None:
            p = self.ui_for_line(line)
            if p is not None and p in models and name in models[p].nodes:
                target = p
        if target is None and (self.model is None or name not in self.model.nodes):
            target = next((p for p, m in models.items() if name in m.nodes), None)
        if target is not None and target != self.ui_path:
            self.sel = name
            self.switch_ui(target)                 # load_ui re-selects self.sel
            return
        if self.model is None or name not in self.model.nodes:
            return
        if name == self.sel and source == "hover":
            return
        self.sel = name
        node = self.model.nodes[name]
        self.preview.select(name)
        self.editor.mark(name)
        self.panel.show_node(self.model, node, self.preview.find(name), self.generated, self.editor)
        it = getattr(self, "_items", {}).get(name)
        if it is not None and source != "tree":
            self.tree.blockSignals(True)
            self.tree.setCurrentItem(it)
            self.tree.scrollToItem(it)
            self.tree.blockSignals(False)
        if source in ("preview", "tree"):
            self.editor.reveal(name)
        self._status(f"{name} ({node.cls}) — {node.position_text()}", 0)

    def _tooltip_for(self, name):
        node = self.model.nodes.get(name) if self.model else None
        if node is None:
            return ""
        return f"<b>{escape(name)}</b> : {escape(node.cls)}<br>{escape(node.position_text())}"

    # --------------------------------------------------------- file watching
    def _on_file_changed(self, path):
        self._pending.add(Path(path))
        self._reload_timer.start()

    def _reload_pending(self):
        pending, self._pending = self._pending, set()
        for p in pending:
            if p == self.ui_path:
                if not p.exists():          # Designer saves by replace; wait a moment
                    self._pending.add(p)
                    self._reload_timer.start()
                    continue
                self.load_ui(p)
                self._status(f"{p.name} 변경 감지 → 다시 불러왔어요 ({_now()})")
            elif p == self.py_path and not p.exists():   # editors that save by replace
                self._pending.add(p)
                self._reload_timer.start()
                continue
            elif p == self.py_path:
                text, *_ = read_text(p)
                if text == self.editor.toPlainText():
                    pass
                elif self.editor.document().isModified():
                    self._status(f"{p.name} 가 밖에서 바뀌었지만, 저장하지 않은 편집이 있어 "
                                 "다시 불러오지 않았어요.", 10000)
                else:
                    sb = self.editor.verticalScrollBar().value()
                    self.editor.setPlainText(text)
                    self.editor.document().setModified(False)
                    self.editor.verticalScrollBar().setValue(sb)
                    self.editor.mark(self.sel)
                    self._status(f"{p.name} 변경 감지 → 다시 불러왔어요 ({_now()})")
        self._watch()

    # ---------------------------------------------------------------- save
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
        return r == QMessageBox.Discard

    # ------------------------------------------------------------- designer
    def open_designer(self):
        exe = find_designer()
        if not exe:
            QMessageBox.warning(self, "Designer", "designer.exe 를 찾지 못했어요. (pip install PyQt5Designer)")
            return
        if not QProcess.startDetached(exe, [str(self.ui_path)] if self.ui_path else []):
            QMessageBox.warning(self, "Designer", f"실행하지 못했어요: {exe}")

    # ----------------------------------------------------------------- run
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
        self.bottom.setCurrentWidget(self.output)
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
        proc.closeWriteChannel()        # no keyboard here: input() ends with EOFError instead of hanging
        self.a_stop.setEnabled(True)

    def stop(self):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(2000)
            self.a_stop.setEnabled(False)

    def _on_stderr(self):
        text = bytes(self.proc.readAllStandardError()).decode("utf-8", "replace")
        self._stderr += text
        self._out(text, "#c0392b")

    def _on_finished(self, code, _status):
        self.a_stop.setEnabled(False)
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

    # ---------------------------------------------------------------- check
    def _all_ui_names(self):
        """Names from every .ui the file explicitly uses, plus the one shown."""
        names, tops = set(), set()
        if not self.py_path:
            return names, tops
        uis = ui_candidates(self.py_path, include_folder=False)
        if self.ui_path and self.ui_path not in uis:
            uis.append(self.ui_path)
        for u in uis:
            try:
                mt = u.stat().st_mtime
                cached = self._names_cache.get(u)
                if cached is None or cached[0] != mt:
                    m = UiModel(u)
                    cached = (mt, set(m.nodes), m.top.cls if m.top else "QWidget")
                    self._names_cache[u] = cached
            except Exception:
                continue
            names |= cached[1]
            tops.add(cached[2])
        return names, tops

    def run_check(self):
        if not self.py_path:
            return
        self._update_class_ranges()
        text = self.editor.toPlainText()
        names, tops = self._all_ui_names()
        extra = []
        if self._mismatch:
            ln, msg = self._mismatch
            line_text = self.editor.document().findBlockByNumber(ln).text()
            extra.append(checker.Issue(ln, 0, len(line_text), "warn", msg))
        issues = checker.check(text, names, tops, extra)
        self.editor.set_issues(issues)

        self.issue_list.clear()
        for x in issues:
            it = QListWidgetItem(f"{x.line + 1:>4}줄   {x.msg}")
            it.setForeground(QColor("#c92a2a" if x.level == "error" else "#b35c00"))
            it.setData(Qt.UserRole, x.line)
            self.issue_list.addItem(it)
        if not issues:
            ok = QListWidgetItem("문제 없음 — .ui 이름과 Main.py가 잘 맞아요.")
            ok.setForeground(QColor("#2b8a3e"))
            self.issue_list.addItem(ok)
        self.bottom.setTabText(1, f"검사 ({len(issues)})" if issues else "검사 ✓")

        # widgets never used in Main.py: dim them in the tree
        if self.model is None:
            return
        for name, item in getattr(self, "_items", {}).items():
            node = self.model.nodes.get(name)
            if node is None or node.kind != "widget" or node is self.model.top \
                    or node.cls in _CONTAINERS:
                continue
            used = f"self.{name}" in text
            f = item.font(0)
            f.setItalic(not used)
            item.setFont(0, f)
            item.setForeground(0, QColor("#202020" if used else "#a0a0a0"))
            item.setToolTip(0, "" if used else "Main.py에서 아직 쓰지 않는 위젯")

    # ---------------------------------------------------------- drag & drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_dir() or p.suffix.lower() in (".py", ".ui", ".pyw"):
                self.open_path(p)
                break

    def _out(self, text, color=None):
        cur = self.output.textCursor()
        cur.movePosition(cur.End)
        fmt = cur.charFormat()
        fmt.setForeground(QColor(color or "#202020"))
        cur.setCharFormat(fmt)
        cur.insertText(text)
        self.output.setTextCursor(cur)
        self.output.ensureCursorVisible()

    # -------------------------------------------------------------- closing
    def closeEvent(self, e):
        if not self._confirm_discard():
            e.ignore()
            return
        self.stop()
        self.ai_panel.stop()
        for k, s in self.splitters.items():
            self.settings.setValue(f"split2/{k}", s.saveState())
        e.accept()


def _now():
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")
