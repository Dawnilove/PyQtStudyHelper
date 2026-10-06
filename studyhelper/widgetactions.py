"""위젯에 하는 일: 우클릭 메뉴, 시그널 연결 코드, .ui 값 고치기·이름 바꾸기·되돌리기, 도전 모드, 코드 과제,
학습 기록, 노트 링크."""
import re
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices, QTextCursor
from PyQt5.QtWidgets import QMenu, QMessageBox

from . import examples, learnlog, recovery, uiedit, uihistory
from .addwidgetdialog import AddWidgetDialog
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
        kept = uihistory.snapshot(self.ui_path, f"{name}.{prop} 값 바꾸기")
        try:
            err = set_property(self.ui_path, name, prop, value)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        if err:
            if kept:
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
        # editing the .ui: run after the menu (and the preview event that opened it) has finished
        later = lambda fn: (lambda: QTimer.singleShot(0, fn))        # noqa: E731
        menu.addSeparator()
        menu.addAction("위젯 추가…", later(lambda: self.add_widget_dialog(name)))
        mi = uiedit.move_info(self.model, name)
        if mi is not None:
            back, fwd, horiz = mi
            a = menu.addAction("왼쪽으로 옮기기" if horiz else "위로 옮기기", later(lambda: self.move_selected(-1, name)))
            a.setEnabled(back)
            a = menu.addAction("오른쪽으로 옮기기" if horiz else "아래로 옮기기", later(lambda: self.move_selected(1, name)))
            a.setEnabled(fwd)
        if uiedit.why_not_delete(self.model, name) is None:
            menu.addAction("위젯 삭제…", later(lambda: self.delete_selected(name)))
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
        kept = uihistory.snapshot(self.ui_path, f"{old} → {new} 이름 바꾸기")
        try:
            err, n = rename_object(self.ui_path, old, new)
        except Exception as e:
            err, n = f"{type(e).__name__}: {e}", 0
        if err:
            if kept:
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

    # ------------------------------------------------------------ editing the .ui from the preview
    def _ui_edit_ready(self) -> bool:
        if not (self.model and self.ui_path and self.model.top is not None):
            self._status("먼저 .ui가 연결된 파일을 열어 주세요.")
            return False
        return True

    def _apply_ui_edit(self, label, fn, select=None) -> bool:
        """Change the .ui (undoable with .ui 되돌리기), then reload the preview, tree and checks."""
        kept = uihistory.snapshot(self.ui_path, label)
        try:
            err = fn()
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        if err:
            if kept:                               # only our own step: never an older, real one
                uihistory.discard(self.ui_path)
            QMessageBox.information(self, label, err)
            return False
        self._models.pop(self.ui_path, None)
        self.sel = select
        self.load_ui(self.ui_path)
        return True

    def add_widget_dialog(self, near=None):
        if not self._ui_edit_ready():
            return
        near = near or self.sel
        if not near or near not in self.model.nodes or self.model.nodes[near].kind not in ("widget", "layout"):
            near = self.model.top.name                 # nothing (usable) selected: put it in the window
        try:
            places, err = uiedit.insert_places(self.ui_path, near)
            taken = uiedit.taken_names(self.ui_path)
        except Exception as e:
            places, err, taken = [], f"{self.ui_path.name} 를 읽지 못했어요: {e}", set()
        if err:
            QMessageBox.information(self, "위젯 추가", err)
            return
        dlg = AddWidgetDialog(taken, places, self)
        if not dlg.exec_():
            return
        cls, name, text, where = dlg.values()
        if self._apply_ui_edit(f"{name} 추가", lambda: uiedit.add_widget(self.ui_path, near, where, cls, name, text),
                               select=name):
            self._status(f"{name} ({cls}) 를 {self.ui_path.name}에 추가했어요 → Main.py에서 self.{name} 로 써요. "
                         "우클릭 → 시그널 연결 코드 넣기. (Designer에서 이 파일을 열어 두었다면 다시 열어 주세요)", 15000)

    def delete_selected(self, name=None):
        if not self._ui_edit_ready():
            return
        name = name or self.sel
        if not name or name not in self.model.nodes:
            self._status("먼저 미리보기·위젯 트리에서 지울 위젯을 선택해 주세요.")
            return
        why = uiedit.why_not_delete(self.model, name)
        if why:
            QMessageBox.information(self, "위젯 삭제", why)
            return
        node = self.model.nodes[name]
        inner = []

        def walk(n):
            for c in n.children:
                if c.kind == "widget":
                    inner.append(c.name)
                walk(c)
        walk(node)
        uses = len(re.findall(rf"\bself\.{re.escape(name)}\b", self.editor.toPlainText()))
        msg = f"{name} ({node.cls}) 를 {self.ui_path.name}에서 지울까요?"
        if inner:
            msg += f"\n안에 있는 위젯 {len(inner)}개도 함께 지워져요."
        if uses:
            msg += f"\n\nMain.py에서 self.{name} 를 {uses}곳에서 쓰고 있어요. 지우면 그 줄은 실행할 때 에러가 나요."
        msg += "\n\n(편집 → .ui 되돌리기 Ctrl+Alt+Z 로 되돌릴 수 있어요)"
        if QMessageBox.question(self, "위젯 삭제", msg, QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) != QMessageBox.Yes:
            return
        up = node.parent
        while up is not None and up.kind != "widget":
            up = up.parent
        if self._apply_ui_edit(f"{name} 삭제", lambda: uiedit.delete_widget(self.ui_path, name)[0],
                               select=up.name if up is not None else None):
            self._status(f"{name} 를 지웠어요." + (f" Main.py의 self.{name} {uses}곳은 빨간 밑줄로 보여요." if uses else "")
                         + " (Ctrl+Alt+Z로 되돌리기)", 12000)

    def move_selected(self, step, name=None):
        if not self._ui_edit_ready():
            return
        name = name or self.sel
        if not name or name not in self.model.nodes:
            self._status("먼저 미리보기·위젯 트리에서 옮길 위젯을 선택해 주세요.")
            return
        if self._apply_ui_edit(f"{name} 옮기기", lambda: uiedit.move_widget(self.ui_path, name, step), select=name):
            self._status(f"{name} 를 옮겼어요. (Ctrl+Alt+Z로 되돌리기)")

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
