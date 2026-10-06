"""위젯에 하는 일: 우클릭 메뉴, 시그널 연결 코드, .ui 값 고치기·이름 바꾸기·되돌리기, 도전 모드, 코드 과제,
학습 기록, 노트 링크."""
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices, QTextCursor
from PyQt5.QtWidgets import QMenu, QMessageBox

from . import examples, learnlog, recovery, uihistory
from .challenge import ChallengeWindow
from .explainpanel import AI_LINK
from .learnview import LearnLogDialog
from .props import signals_of
from .renamedialog import RenameDialog
from .signaldialog import SignalInsertDialog
from .taskwindow import TaskWindow
from .ui_model import rename_object, set_property


# signals shown first in a widget's right-click menu (the ones lessons use most)
COMMON_SIGNALS = ["clicked()", "clicked(bool)", "toggled(bool)", "textChanged(QString)", "textChanged()",
                  "returnPressed()", "editingFinished()", "valueChanged(int)", "valueChanged(double)",
                  "currentIndexChanged(int)", "currentTextChanged(QString)", "stateChanged(int)",
                  "itemClicked(QListWidgetItem*)", "itemDoubleClicked(QListWidgetItem*)", "currentRowChanged(int)",
                  "cellClicked(int,int)", "cellDoubleClicked(int,int)", "dateChanged(QDate)",
                  "selectionChanged()", "currentChanged(int)", "triggered(bool)", "triggered()",
                  "accepted()", "rejected()", "sliderMoved(int)"]


class WidgetMixin:
    """MainWindow part: 위젯에 하는 일: 우클릭 메뉴, 시그널 연결 코드, .ui 값 고치기·이름 바꾸기·되돌리기, 도전 모드,
    코드 과제, 학습 기록, 노트 링크."""

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
        uihistory.snapshot(self.ui_path, f"{name}.{prop} 값 바꾸기")
        try:
            err = set_property(self.ui_path, name, prop, value)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        if err:
            uihistory.discard(self.ui_path)
            QMessageBox.warning(self, ".ui 저장", err)
            QTimer.singleShot(0, lambda: self.select(name, "reload"))
            return
        self._status(f"{self.ui_path.name} 저장: {name}.{prop} = {value!r}  "
                     "(Designer에서 이 파일을 열어 두었다면 Designer에서 다시 열어 주세요)", 12000)
        QTimer.singleShot(0, lambda: self.load_ui(self.ui_path))

    def _tree_menu(self, pos):
        it = self.tree.itemAt(pos)
        name = it.data(0, Qt.UserRole) if it else None
        if not name:
            return
        self._widget_menu(name, self.tree.viewport().mapToGlobal(pos))

    def _widget_menu(self, name, global_pos):
        """Right-click on a widget (tree or preview): rename, connect a signal, examples, Qt docs."""
        if not self.model or name not in self.model.nodes:
            return
        if self.sel != name:
            self.select(name, "tree")
        node = self.model.nodes[name]
        menu = QMenu(self)
        menu.addAction(self.a_rename)
        obj = self.preview.find(name)
        sigs = [s for _, s in signals_of(obj)] if obj is not None else []
        if sigs and self.py_path:
            sm = menu.addMenu("시그널 연결 코드 넣기")
            common = []
            for want in COMMON_SIGNALS:
                if want in sigs and want.split("(")[0] not in [c.split("(")[0] for c in common]:
                    common.append(want)
            for s in common:
                sm.addAction(s, lambda s=s: self.insert_signal(name, s, sigs))
            rest = [s for s in sigs if s not in common]
            if rest:
                more = sm.addMenu("다른 시그널") if common else sm
                for s in rest:
                    more.addAction(s, lambda s=s: self.insert_signal(name, s, sigs))
        menu.addSeparator()
        menu.addAction("예제 코드 보기", self.panel.show_examples_tab)
        url = examples.doc_url(node.cls)
        if url:
            menu.addAction(f"Qt 문서 열기 ({node.cls})", lambda: QDesktopServices.openUrl(QUrl(url)))
        menu.exec_(global_pos)

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
        uihistory.snapshot(self.ui_path, f"{old} → {new} 이름 바꾸기")
        try:
            err, n = rename_object(self.ui_path, old, new)
        except Exception as e:
            err, n = f"{type(e).__name__}: {e}", 0
        if err:
            uihistory.discard(self.ui_path)
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

    def undo_ui(self):
        if not self.ui_path:
            return
        label = uihistory.undo(self.ui_path)
        if label is None:
            self._status("되돌릴 .ui 수정이 없어요. (Designer에서 바꾼 것은 Designer에서 되돌려 주세요)")
            return
        self._models.pop(self.ui_path, None)
        self.load_ui(self.ui_path)
        more = " — Main.py에서 바뀐 이름은 편집기에서 Ctrl+Z로 되돌리세요" if "이름 바꾸기" in label else ""
        self._status(f".ui 되돌림: {label}{more}", 12000)

    def _update_undo_ui(self):
        label = uihistory.last_label(self.ui_path) if self.ui_path else None
        self.a_undo_ui.setEnabled(label is not None)
        self.a_undo_ui.setText(f".ui 되돌리기: {label}" if label else ".ui 되돌리기")

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

    # ------------------------------------------------------------ code assignments / learning log
    def open_tasks(self):
        if self.task_window is None:
            self.task_window = TaskWindow(self.settings, self)
            self.task_window.openRequested.connect(self.open_path)
            self.task_window.saveRequested.connect(self._save_if_open)
        self.task_window.show()
        self.task_window.raise_()
        self.task_window.activateWindow()

    def _save_if_open(self, path):
        """The task window grades a file: save it first if it is open here with unsaved edits."""
        p = str(Path(path).resolve())
        if self.py_path and str(self.py_path) == p:
            if self.editor.document().isModified():
                self.save_py()
        elif p in self._stash and self._save_stashed(p):
            self._stash.pop(p, None)
            recovery.clear(p)
            self._refresh_tab_titles()

    def _after_save(self, path):
        if self.task_window is not None:
            self.task_window.on_saved(str(path))

    def show_learnlog(self):
        learnlog.reset_cache()                     # another helper window may have written to it
        dlg = LearnLogDialog(self)
        dlg.tasksRequested.connect(lambda: (dlg.accept(), self.open_tasks()))
        dlg.exec_()

    def _on_line_link(self, url):
        if url.toString() == AI_LINK:
            self.ai_explain()
        else:
            self.open_note(url.toString())

    def open_note(self, url):
        if url == "connect":
            self.choose_vault()
        elif url.startswith(("obsidian://", "file:")):
            QDesktopServices.openUrl(QUrl.fromEncoded(url.encode()))
