"""Main window: wires preview, widget tree, Main.py editor, property panel and runner."""
import os
import shutil
import sys
from html import escape
from pathlib import Path

from PyQt5 import uic
from PyQt5.QtCore import (QFileSystemWatcher, QProcess, QProcessEnvironment, QSettings, Qt,
                          QTimer)
from PyQt5.QtGui import QColor, QFont, QKeySequence
from PyQt5.QtWidgets import (QAction, QComboBox, QFileDialog, QLabel, QMainWindow, QMessageBox,
                             QPlainTextEdit, QSizePolicy, QSplitter, QStyle, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from . import codeview
from .editor import CodeEditor
from .locate import main_py_in, py_for_ui, read_text, ui_candidates
from .preview import PreviewPane
from .props import PropertyPanel
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


def _titled(title: str, widget: QWidget) -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    lab = QLabel(f"<b>{title}</b>")
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
        self.py_path: Path | None = None
        self.ui_path: Path | None = None
        self.encoding, self.crlf = "utf-8", True
        self.model: UiModel | None = None
        self.generated = ""
        self.sel: str | None = None
        self.proc: QProcess | None = None

        self.resize(1500, 900)
        self._build_ui()
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self._on_file_changed)
        self._pending = set()
        self._reload_timer = QTimer(self, singleShot=True, interval=300, timeout=self._reload_pending)
        self._update_title()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        tb = self.addToolBar("main")
        tb.setMovable(False)
        st = self.style()
        a_open = QAction(st.standardIcon(QStyle.SP_DialogOpenButton), "열기", self,
                         shortcut=QKeySequence(QKeySequence.Open), triggered=self.open_dialog)
        a_save = QAction(st.standardIcon(QStyle.SP_DialogSaveButton), "저장", self,
                         shortcut=QKeySequence(QKeySequence.Save), triggered=self.save_py)
        tb.addAction(a_open)
        tb.addAction(a_save)
        tb.addSeparator()
        tb.addWidget(QLabel(" UI 파일: "))
        self.ui_combo = QComboBox()
        self.ui_combo.setMinimumWidth(180)
        self.ui_combo.activated.connect(self._on_ui_combo)
        tb.addWidget(self.ui_combo)
        self.a_designer = QAction("Designer에서 열기", self, triggered=self.open_designer)
        tb.addAction(self.a_designer)
        tb.addSeparator()
        self.a_run = QAction(st.standardIcon(QStyle.SP_MediaPlay), "실행 (F5)", self,
                             shortcut="F5", triggered=self.run)
        self.a_stop = QAction(st.standardIcon(QStyle.SP_MediaStop), "중지", self,
                              triggered=self.stop, enabled=False)
        tb.addAction(self.a_run)
        tb.addAction(self.a_stop)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.preview = PreviewPane()
        self.preview.widgetClicked.connect(lambda n: self.select(n, "preview"))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["objectName", "클래스"])
        self.tree.setColumnWidth(0, 200)
        self.tree.itemClicked.connect(lambda it, _: self.select(it.data(0, Qt.UserRole), "tree"))

        self.editor = CodeEditor()
        self.editor.nameHovered.connect(lambda n: self.select(n, "hover"))
        self.editor.tooltip_for = self._tooltip_for
        self.editor.document().modificationChanged.connect(lambda _: self._update_title())

        self.panel = PropertyPanel()
        self.panel.lineRequested.connect(self.editor.go_to_line)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 10))

        left = QSplitter(Qt.Vertical)
        left.addWidget(_titled("실시간 미리보기 · 클릭하면 선택", self.preview))
        left.addWidget(_titled("위젯 트리", self.tree))
        left.setSizes([550, 300])
        self.editor_box = _titled("Main.py", self.editor)
        top = QSplitter(Qt.Horizontal)
        top.addWidget(left)
        top.addWidget(self.editor_box)
        top.addWidget(_titled("속성", self.panel))
        top.setSizes([480, 620, 400])
        main = QSplitter(Qt.Vertical)
        main.addWidget(top)
        main.addWidget(_titled("실행 결과", self.output))
        main.setSizes([700, 160])
        self.setCentralWidget(main)
        self.splitters = {"left": left, "top": top, "main": main}
        for k, s in self.splitters.items():
            state = self.settings.value(f"split/{k}")
            if state is not None:
                s.restoreState(state)

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
        start = str(self.py_path.parent) if self.py_path else self.settings.value("lastDir", "")
        path, _ = QFileDialog.getOpenFileName(self, "파이썬 파일 또는 .ui 열기", start,
                                              "Python / UI (*.py *.ui);;모든 파일 (*.*)")
        if path:
            self.open_path(path)

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
        text, self.encoding, self.crlf = read_text(p)
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)

        cands = ui_candidates(p)
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
            self.editor.set_names([])
            self.preview.load(None, [])
            return
        try:
            self.model = UiModel(ui_path)
        except Exception as e:  # half-written file while Designer saves
            self._status(f"{ui_path.name} 를 읽지 못했어요: {e}")
            self.editor.set_names([])
            return
        try:
            self.generated = codeview.generate(ui_path)
        except Exception:
            self.generated = ""
        names = list(self.model.nodes)
        self.editor.set_names(names)
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
            group = QTreeWidgetItem(["(액션)", ""])
            group.setFlags(Qt.ItemIsEnabled)
            self.tree.addTopLevelItem(group)
            for a in self.model.actions:
                add(a, group)
        self.tree.expandAll()

    # ------------------------------------------------------------ selection
    def select(self, name, source):
        if not name or self.model is None or name not in self.model.nodes:
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
            elif p == self.py_path and p.exists():
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
        self._status(f"{self.py_path.name} 저장함")
        return True

    def _confirm_discard(self) -> bool:
        if not self.editor.document().isModified():
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
        try:
            self._refresh_generated_py()
        except Exception as e:
            self._out(f"[도우미] gui.py 생성 실패: {e}\n", "#c0392b")
        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(str(self.py_path.parent))
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUNBUFFERED", "1")
        self.proc.setProcessEnvironment(env)
        self.proc.readyReadStandardOutput.connect(
            lambda: self._out(bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")))
        self.proc.readyReadStandardError.connect(
            lambda: self._out(bytes(self.proc.readAllStandardError()).decode("utf-8", "replace"), "#c0392b"))
        self.proc.finished.connect(self._on_finished)
        self._out(f"> python {self.py_path.name}\n", "#888888")
        self.proc.start(sys.executable, ["-u", str(self.py_path)])
        self.a_run.setEnabled(True)
        self.a_stop.setEnabled(True)

    def stop(self):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(2000)

    def _on_finished(self, code, _status):
        self.a_stop.setEnabled(False)
        self._out(f"\n[종료 코드 {code}]\n", "#888888")

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
        for k, s in self.splitters.items():
            self.settings.setValue(f"split/{k}", s.saveState())
        e.accept()


def _now():
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")
