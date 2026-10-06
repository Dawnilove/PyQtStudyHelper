"""Main window: wires preview, widget tree, Main.py editor, property panel and runner."""
from html import escape
from pathlib import Path

from PyQt5.QtCore import QFileSystemWatcher, QProcess, QSettings, QSize, Qt, QTimer, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QKeySequence
from PyQt5.QtWidgets import (QAction, QApplication, QComboBox, QDialog, QDockWidget, QHBoxLayout, QLineEdit,
                             QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
                             QSizePolicy, QSplitter, QStackedWidget, QStyle, QTabBar, QTabWidget,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import checker, codeview, helpmenu, learnlog, recovery, theme
from .aiactions import AiMixin
from .editor import CodeEditor
from .explainpanel import AiPanel, LineExplainView
from .explorer import ExplorerPanel
from .filetabs import TabsMixin
from .findbar import FindBar
from .legend import LEGEND, LEGEND_FULL
from .locate import class_ui_ranges, import_mismatch, main_py_in, py_for_ui, read_text, ui_candidates
from .preview import PreviewPane
from .props import PropertyPanel
from .runner import OutputView, RunMixin
from .studyfolders import (load_folders, MainFilesScanner, pick_file, save_folders, start_dir,
                           StudyFoldersDialog)
from .theme import ThemedLabel
from .ui_model import UiModel
from .viewsettings import ViewMixin
from .welcome import WelcomeMixin
from .widgetactions import WidgetMixin


# QWidget containers that are normal to leave unused in Main.py
_CONTAINERS = {"QWidget", "QMenuBar", "QStatusBar", "QToolBar", "QFrame", "QMenu"}


def _titled(title: str, widget: QWidget) -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    lab = ThemedLabel(f"<b>{title}</b>")
    lab.setObjectName("paneTitle")
    lab.setMargin(4)
    lab.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # long paths must not widen the pane
    lay.addWidget(lab)
    lay.addWidget(widget, 1)
    box.title_label = lab
    return box


class MainWindow(ViewMixin, TabsMixin, RunMixin, WelcomeMixin, WidgetMixin, AiMixin, QMainWindow):
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

        scr = QApplication.primaryScreen().availableGeometry()
        self.setMinimumSize(900, 600)
        self.resize(min(1500, int(scr.width() * 0.94)), min(900, int(scr.height() * 0.92)))
        self.move(scr.x() + (scr.width() - self.width()) // 2, scr.y() + (scr.height() - self.height()) // 2)
        self._dark = self.settings.value("view/dark", False) in (True, "true")
        theme.apply(QApplication.instance(), self._dark)
        self._build_ui()
        self.a_dark.setChecked(self._dark)
        self._light_preview()
        self._apply_icons()
        self._chrome()
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self._on_file_changed)
        self._pending = set()
        self._missing = {}               # watched file -> how many times it was found missing
        self._reload_timer = QTimer(self, singleShot=True, interval=300, timeout=self._reload_pending)
        self._check_timer = QTimer(self, singleShot=True, interval=400, timeout=self.run_check)
        self.editor.textChanged.connect(self._check_timer.start)
        self._update_title()
        self._backup_timer = QTimer(self, timeout=self._backup_now)
        self._apply_backup_interval()


    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        st = self.style()
        A = lambda text, slot, key=None, icon=None, tip=None: self._action(text, slot, key, icon, tip)
        self.a_open = A("열기…", self.open_dialog, QKeySequence.Open, QStyle.SP_DialogOpenButton,
                        "Main.py 또는 .ui 파일 열기 (파일을 창에 끌어다 놓아도 돼요)")
        self.a_explorer = A("탐색기 보기", self.toggle_explorer, "Ctrl+B", None,
                            "왼쪽의 파일 목록(학습 폴더 또는 최근 파일)을 보이거나 숨겨요 (Ctrl+B)")
        self.a_explorer.setCheckable(True)
        self.a_study = A("학습 폴더 관리…", self.manage_study_folders, None, None,
                         "자주 여는 학습 폴더를 등록하면 파일 열기 창 왼쪽에 바로가기로 나와요")
        self.a_save = A("저장", self.save_py, QKeySequence.Save, QStyle.SP_DialogSaveButton)
        self.a_run = A("실행", self.run, "F5", QStyle.SP_MediaPlay, "Main.py 실행 (F5)")
        self.a_stop = A("중지", self.stop, "Shift+F5", QStyle.SP_MediaStop, "실행 중인 프로그램 끄기 (Shift+F5)")
        self.a_stop.setEnabled(False)
        self.a_designer = A("Designer", self.open_designer, "Ctrl+D", QStyle.SP_FileDialogDetailedView,
                            "지금 .ui 파일을 Qt Designer로 열기 (Ctrl+D)")
        self.a_explain = A("AI 설명", self.ai_explain, "Ctrl+E", QStyle.SP_MessageBoxInformation,
                           "선택한 줄(없으면 현재 줄)을 AI가 설명 (Ctrl+E)")
        self.a_review = A("AI 코드 리뷰", self.ai_review, "Ctrl+Shift+R", None, "Main.py 전체 리뷰")
        self.a_ai_settings = A("AI 모델·키 설정…", self.ai_settings)
        self.a_free_ai = A("무료 AI 켜기 (Gemini)…", self.free_ai, None, None,
                           "구글 계정만 있으면 무료 — 키를 한 번 연결하면 답이 도우미 안에 바로 나와요")
        self.a_zoom_in = A("글자 크게", lambda: self.zoom(1), QKeySequence.ZoomIn)
        self.a_zoom_out = A("글자 작게", lambda: self.zoom(-1), QKeySequence.ZoomOut)
        self.a_zoom_reset = A("글자 크기 원래대로", lambda: self.zoom(0), "Ctrl+0")
        self.a_reset_layout = A("화면 배치 초기화", self.reset_layout)
        self.a_vault = A("내 노트 폴더 연결…", self.choose_vault, None, None,
                         "내 Obsidian 볼트(또는 .md 노트 폴더)를 연결하면 위젯·코드에 맞는 노트를 찾아 줘요")
        self.a_vault_off = A("내 노트 폴더 연결 해제", self.disconnect_vault)
        self.a_dark = A("어두운 테마", self.toggle_dark, None, None, "화면을 어둡게 바꿔요 (눈이 편해요)")
        self.a_dark.setCheckable(True)
        self.a_legend = A("색 범례 보기", self.toggle_legend)
        self.a_legend.setCheckable(True)
        self.a_help = A("사용법", self.show_help, "F1", QStyle.SP_MessageBoxQuestion, "사용법과 단축키 (F1)")
        self.a_shortcuts = A("단축키 목록", self.show_shortcuts, "Ctrl+/")
        self.a_errlog = A("오류 기록 보기…", self.show_error_log, None, None,
                          "프로그램이 멈췄을 때의 기록. 친구에게 물어볼 때 복사해서 보내요")
        self.a_settings = A("설정…", self.open_settings, "Ctrl+,", None, "테마·글자 크기·백업·시작 설정을 한곳에서")
        self.a_update = A("새 버전 받기", lambda: QDesktopServices.openUrl(QUrl(helpmenu.REPO_URL)))
        self.a_update.setVisible(False)
        self.a_home = A("시작 화면", lambda: self.stack.setCurrentIndex(0))
        self.a_challenge = A("도전 모드…", self.start_challenge, "Ctrl+T", QStyle.SP_DialogApplyButton,
                             "목표 화면(.ui)을 보고 Designer로 똑같이 만들어 보기 — 저장할 때마다 자동 채점")
        self.challenge = None
        self.a_tasks = A("코드 과제…", self.open_tasks, "Ctrl+Shift+T", None,
                         "‘버튼을 누르면 라벨이 바뀌게’ 같은 짧은 과제 — Main.py를 저장할 때마다 자동 채점 (Ctrl+Shift+T)")
        self.task_window = None
        self.a_learnlog = A("학습 기록…", self.show_learnlog, "Ctrl+Shift+L", None,
                            "공부한 날, 많이 본 위젯, 자주 만난 에러, 푼 과제 (이 PC에만 저장)")
        self.a_find =A("찾기…", lambda: self.findbar.open_bar(False), QKeySequence.Find, None, "코드에서 찾기 (Ctrl+F)")
        self.a_replace = A("바꾸기…", lambda: self.findbar.open_bar(True), "Ctrl+H", None, "찾아서 바꾸기 (Ctrl+H)")
        self.a_undo_ui = A(".ui 되돌리기", self.undo_ui, "Ctrl+Alt+Z", None,
                           "도우미에서 바꾼 .ui(속성 값, 이름 바꾸기, 위젯 추가·삭제)를 바로 전으로 되돌려요")
        self.a_undo_ui.setEnabled(False)
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
        m.addAction(self.a_settings)
        m.addAction(A("끝내기", self.close, "Ctrl+Q"))
        m = mb.addMenu("편집(&E)")
        m.addAction(self.a_find)
        m.addAction(self.a_replace)
        m.addSeparator()
        m.addAction(self.a_undo_ui)
        m = mb.addMenu("실행(&R)")
        for a in (self.a_run, self.a_stop, self.a_designer):
            m.addAction(a)
        m = mb.addMenu("위젯(&W)")
        m.addAction(self.a_rename)
        m = mb.addMenu("연습(&P)")
        m.addAction(self.a_challenge)
        m.addAction(self.a_tasks)
        m.addSeparator()
        m.addAction(self.a_learnlog)
        m = mb.addMenu("AI(&A)")
        for a in (self.a_explain, self.a_review):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_free_ai)
        m.addAction(self.a_ai_settings)
        m = mb.addMenu("보기(&V)")
        for a in (self.a_zoom_in, self.a_zoom_out, self.a_zoom_reset):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_explorer)
        m.addAction(self.a_legend)
        m.addAction(self.a_dark)
        m.addAction(self.a_reset_layout)
        m.addAction(self.a_vault)
        m.addAction(self.a_vault_off)
        m = mb.addMenu("도움말(&H)")
        m.addAction(self.a_help)
        m.addAction(self.a_shortcuts)
        m.addSeparator()
        m.addAction(self.a_errlog)
        m.addAction(self.a_update)

        tb = self.addToolBar("main")
        self.toolbar = tb
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tb.addAction(self.a_open)
        tb.addAction(self.a_save)
        tb.addSeparator()
        ui_lab = ThemedLabel("<span style='color:#888'>UI 파일</span>")
        ui_lab.setContentsMargins(6, 0, 4, 0)
        tb.addWidget(ui_lab)
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
        tb.addAction(self.a_tasks)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        tb.addAction(self.a_help)

        self.preview = PreviewPane()
        self.preview.widgetClicked.connect(lambda n: self.select(n, "preview"))
        self.preview.widgetMenuRequested.connect(self._widget_menu)
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
        self.line_view.anchorClicked.connect(self._on_line_link)
        self.ai_panel = AiPanel()
        self.ai_panel.settingsRequested.connect(self.ai_settings)
        self.ai_panel.freeAiRequested.connect(self.free_ai)
        self.ai_panel.explainRequested.connect(self.ai_explain)
        self.ai_panel.reviewRequested.connect(self.ai_review)
        self.explain_tabs = QTabWidget()
        self.explain_tabs.addTab(self.line_view, "줄 해설")
        self.explain_tabs.addTab(self.ai_panel, "AI 해설")

        self.output = OutputView()
        self.output.frameClicked.connect(self._on_frame_clicked)
        self.issue_list = QListWidget()
        self.issue_list.itemClicked.connect(self._on_issue_clicked)
        # input() support: what the student types here goes to the running program's stdin
        self.stdin_edit = QLineEdit()
        self.stdin_edit.setPlaceholderText("실행 중인 프로그램의 input()에 보낼 값을 쓰고 Enter")
        self.stdin_edit.setEnabled(False)
        self.stdin_edit.returnPressed.connect(self.send_input)
        self.b_send = QPushButton("보내기")
        self.b_send.setEnabled(False)
        self.b_send.clicked.connect(self.send_input)
        self.b_clear_out = QPushButton("지우기")
        self.b_clear_out.setToolTip("실행 결과 창을 비워요")
        self.b_clear_out.clicked.connect(self.output.clear)
        run_box = QWidget()
        rl = QVBoxLayout(run_box)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(2)
        rl.addWidget(self.output, 1)
        row = QHBoxLayout()
        row.setContentsMargins(2, 0, 2, 2)
        row.addWidget(ThemedLabel("입력:"))
        row.addWidget(self.stdin_edit, 1)
        row.addWidget(self.b_send)
        row.addWidget(self.b_clear_out)
        rl.addLayout(row)
        self.run_box = run_box
        self.bottom = QTabWidget()
        self.bottom.addTab(run_box, "실행 결과")
        self.bottom.addTab(self.issue_list, "검사")

        left = QSplitter(Qt.Vertical)
        self.preview_box = _titled("미리보기", self.preview)
        left.addWidget(self.preview_box)
        self.tree_box = _titled("위젯 트리", self.tree)
        left.addWidget(self.tree_box)
        left.setSizes([480, 300])
        self.editor_box = _titled("Main.py", self.editor)
        self.legend = ThemedLabel(LEGEND)
        self.legend.setWordWrap(True)
        self.legend.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)
        self.legend.setObjectName("legend")
        self.legend.setToolTip("<html>"+LEGEND_FULL+"<br>(보기 메뉴에서 끄고 켤 수 있어요)</html>")
        self.file_tabs = QTabBar()
        self.file_tabs.setObjectName("fileTabs")
        self.file_tabs.setTabsClosable(False)          # see _select_tab: own ✕ buttons
        self.file_tabs.setDocumentMode(True)
        self.file_tabs.setExpanding(False)
        self.file_tabs.setUsesScrollButtons(True)
        self.file_tabs.currentChanged.connect(self._on_tab_changed)
        self.file_tabs.setVisible(False)
        self._stash = {}                 # path -> {"text", "line"} for edited files that aren't the one shown
        self.editor_box.layout().insertWidget(1, self.file_tabs)
        self.findbar = FindBar(self.editor)
        self.editor_box.layout().addWidget(self.findbar)
        self.editor_box.layout().addWidget(self.legend)
        right = QSplitter(Qt.Vertical)
        self.right_split = right
        right.addWidget(_titled("선택한 위젯", self.panel))
        right.addWidget(_titled("해설", self.explain_tabs))
        right.setSizes([340, 480])
        top = QSplitter(Qt.Horizontal)
        top.addWidget(left)
        top.addWidget(self.editor_box)
        top.addWidget(right)
        top.setSizes([270, 640, 340])
        top.setStretchFactor(0, 2)
        top.setStretchFactor(1, 5)
        top.setStretchFactor(2, 3)
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
        work = QWidget()
        wl = QVBoxLayout(work)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)
        self.tips = self._build_tips()
        wl.addWidget(self.tips)
        wl.addWidget(main, 1)
        self.stack.addWidget(work)
        self.setCentralWidget(self.stack)
        self.explorer = ExplorerPanel()
        self.explorer.openRequested.connect(self.open_path)
        self.explorer.manageRequested.connect(self.manage_study_folders)
        self.explorer_dock = QDockWidget("탐색기", self)
        self.explorer_dock.setObjectName("explorerDock")
        self.explorer_dock.setWidget(self.explorer)
        self.explorer_dock.setTitleBarWidget(QWidget())          # no title bar: it's a plain side panel
        self.explorer_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.explorer_dock.setMinimumWidth(170)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.explorer_dock)
        want = self.settings.value("view/explorer", True) not in (False, "false")
        self.a_explorer.setChecked(want)
        self.resizeDocks([self.explorer_dock], [int(self.settings.value("explorer/width", 220))], Qt.Horizontal)
        self.stack.currentChanged.connect(self._on_page_changed)
        self._on_page_changed(0)

        v = self.settings.value("vault", "")
        self.panel.vault = self.line_view.vault = Path(v) if v and Path(v).is_dir() else None
        self.a_vault_off.setEnabled(self.panel.vault is not None)

        show_legend = self.settings.value("view/legend", True) not in (False, "false")
        self.a_legend.setChecked(show_legend)
        self.legend.setVisible(show_legend)

        self.ai_status = ThemedLabel()
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


    # ---------------------------------------------------------- challenge
    def _update_title(self):
        name = self.py_path.name if self.py_path else "파일 없음"
        dirty = "*" if self.editor.document().isModified() else ""
        self.setWindowTitle(f"{dirty}{name} — PyQt 학습 도우미")
        if hasattr(self, "file_tabs"):
            self._refresh_tab_titles()
        if self.py_path:
            self.editor_box.title_label.setText(f"<b>{dirty}{escape(self.py_path.name)}</b> "
                                                f"<span style='color:#888'>· {escape(self.py_path.parent.name)}</span>")
            self.editor_box.title_label.setToolTip(str(self.py_path))

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
        try:
            text, encoding, crlf = read_text(p)
        except OSError as e:
            QMessageBox.warning(self, "열기", f"{p.name} 를 열지 못했어요.\n{e.strerror or e}")
            return False
        self._stash_current()

        self.py_path = p
        self._mismatch = import_mismatch(p)
        self.encoding, self.crlf = encoding, crlf
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)
        kept = self._stash.pop(str(p), None)
        lost = None if kept else recovery.load(p, text)
        if kept:
            self.editor.setPlainText(kept["text"])
            self.editor.document().setModified(True)
            self.editor.go_to_line(kept["line"])
        if lost is not None and QMessageBox.question(
                self, "복구", f"{p.name} 을(를) 저장하지 못하고 닫힌 흔적이 있어요.\n그때 작성하던 내용을 되살릴까요?",
                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.editor.setPlainText(lost.replace("\r\n", "\n"))
            self.editor.document().setModified(True)
        elif lost is not None:
            recovery.clear(p)

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
        self._select_tab(p)
        self.ai_panel.save_dir = str(p.parent)
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
        learnlog.note_open(p)
        return True

    # ------------------------------------------------------------ file tabs
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
        self._update_undo_ui()
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
            f"<b>미리보기</b> <span style='color:#555'>· {escape(ui_path.name)}</span>"
            + (f" <span style='color:#555'>({escape(cls)} 클래스)</span>" if cls and many else "")
            + (" <span style='color:#888'>· 클래스를 클릭하면 바뀌어요</span>" if many else ""))
        self.preview_box.title_label.setToolTip("실시간 미리보기 — 위젯을 클릭하면 선택돼요")
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
            learnlog.note_widget(node.cls)
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
            elif p == self.py_path and not p.exists():   # editors that save by replace: wait a little
                tries = self._missing.get(p, 0) + 1
                self._missing[p] = tries
                if tries < 10:
                    self._pending.add(p)
                    self._reload_timer.start()
                elif tries == 10:                        # really gone (deleted / renamed outside)
                    self.editor.document().setModified(True)
                    self._status(f"{p.name} 파일이 폴더에서 사라졌어요 (지워졌거나 이름이 바뀜). 코드는 그대로 있어요 — "
                                 "Ctrl+S로 저장하면 다시 만들어져요.", 30000)
                continue
            elif p == self.py_path:
                self._missing.pop(p, None)
                try:
                    text, *_ = read_text(p)
                except OSError:
                    continue
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
            it.setForeground(QColor(theme.fg("#c92a2a" if x.level == "error" else "#b35c00")))
            it.setData(Qt.UserRole, x.line)
            self.issue_list.addItem(it)
        if not issues:
            ok = QListWidgetItem("문제 없음 — .ui 이름과 Main.py가 잘 맞아요.")
            ok.setForeground(QColor(theme.fg("#2b8a3e")))
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
            item.setForeground(0, QColor(theme.T["text"] if used else theme.T["unused"]))
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


    # -------------------------------------------------------------- closing
    def closeEvent(self, e):
        if not self._confirm_all():
            e.ignore()
            return
        self.stop()
        self.ai_panel.stop()
        if self.task_window is not None:
            self.task_window.close()             # stops a grading run that is still going
        self.settings.setValue("session/tabs", [self.file_tabs.tabData(i) for i in range(self.file_tabs.count())])
        self.settings.setValue("session/current", str(self.py_path) if self.py_path else "")
        if self.explorer_dock.isVisible():
            self.settings.setValue("explorer/width", self.explorer_dock.width())
        for k, s in self.splitters.items():
            self.settings.setValue(f"split2/{k}", s.saveState())
        u = getattr(self, "_updater", None)
        if u is not None and u.isRunning():      # a QThread must not be destroyed while it runs
            u.wait(6000)
        e.accept()


def _now():
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")
