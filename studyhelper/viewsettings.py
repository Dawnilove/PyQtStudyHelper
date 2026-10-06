"""보기·설정·도움말: 테마, 아이콘, 글자 크기, 설정 창, 단축키·오류 기록, 새 버전 알림, 백업 타이머."""
import time
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QMessageBox, QPushButton, QSizePolicy,
                             QWidget)

from . import helpmenu, icons, notes, recovery, theme
from .legend import LEGEND
from .settingsdialog import SettingsDialog
from .studyfolders import existing_folders, load_folders
from .theme import ThemedLabel


class ViewMixin:
    """MainWindow part: 보기·설정·도움말: 테마, 아이콘, 글자 크기, 설정 창, 단축키·오류 기록, 새 버전 알림, 백업 타이머."""

    def _apply_backup_interval(self):
        sec = int(self.settings.value("backup/interval", 20))
        if sec > 0:
            self._backup_timer.start(sec * 1000)
        else:
            self._backup_timer.stop()

    def open_settings(self):
        values = {
            "dark": self._dark, "zoom": self._font_delta, "legend": self.a_legend.isChecked(),
            "explorer": self.a_explorer.isChecked(), "tips": not self._tips_hidden(),
            "restore": self.settings.value("session/restore", True) not in (False, "false"),
            "update": self.settings.value("update/check", True) not in (False, "false"),
            "backup": int(self.settings.value("backup/interval", 20)),
        }
        actions = {"AI 모델·키 설정…": self.ai_settings, "무료 AI 켜기…": self.free_ai,
                   "내 노트 폴더 연결…": self.choose_vault, "학습 폴더 관리…": self.manage_study_folders}
        dlg = SettingsDialog(values, actions, self)
        if dlg.exec_():
            self.apply_settings(dlg.values())

    def apply_settings(self, v: dict):
        if v["dark"] != self._dark:
            self.a_dark.setChecked(v["dark"])
            self.toggle_dark()
        if v["zoom"] != self._font_delta:
            self._font_delta = v["zoom"]
            self.zoom(None)
        if v["legend"] != self.a_legend.isChecked():
            self.a_legend.setChecked(v["legend"])
            self.toggle_legend()
        if v["explorer"] != self.a_explorer.isChecked():
            self.a_explorer.setChecked(v["explorer"])
            self.toggle_explorer()
        self.settings.setValue("tips/hidden", not v["tips"])
        self.tips.setVisible(v["tips"])
        self.settings.setValue("session/restore", v["restore"])
        self.settings.setValue("update/check", v["update"])
        self.settings.setValue("backup/interval", v["backup"])
        self._apply_backup_interval()
        self._status("설정을 적용했어요.")

    def _tips_hidden(self) -> bool:
        return self.settings.value("tips/hidden", False) in (True, "true")

    def show_shortcuts(self):
        helpmenu.ShortcutsDialog(self.menuBar(), self).exec_()

    def show_error_log(self):
        helpmenu.ErrorLogDialog(self).exec_()

    def check_updates_later(self):
        """At start-up (from run.py): look for a newer version on GitHub, at most once a day, in the background."""
        if self.settings.value("update/check", True) in (False, "false"):
            return
        last = float(self.settings.value("update/last", 0) or 0)
        if time.time() - last < 24 * 3600:
            newer = self.settings.value("update/newer", "")
            if newer and helpmenu.is_newer(newer):
                self._show_update(newer)
            return
        self._updater = helpmenu.UpdateChecker(self)
        self._updater.newer.connect(self._show_update)
        self._updater.finished.connect(lambda: self.settings.setValue("update/last", time.time()))
        QTimer.singleShot(4000, self._updater.start)

    def _show_update(self, version):
        self.settings.setValue("update/newer", version)
        self.a_update.setText(f"새 버전 {version} 받기 (GitHub)")
        self.a_update.setVisible(True)
        self._status(f"새 버전 {version} 이 나왔어요 — 도움말 메뉴 → 새 버전 받기", 20000)

    def _build_tips(self) -> QWidget:
        """처음 쓰는 사람을 위한 한 줄 안내 (닫으면 다시 안 나와요)."""
        bar = QWidget()
        bar.setObjectName("tips")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 4, 6, 4)
        lab = ThemedLabel("<b>처음이세요?</b> &nbsp; ① 코드의 <span style='color:#0b6bcb'><u>파란 이름</u></span>에 마우스를 올려 보세요 "
                     "&nbsp; ② 궁금한 줄을 클릭하면 해설이 나와요 &nbsp; ③ <b>F5</b>로 실행 &nbsp; ④ 막히면 <b>F1</b>(사용법)")
        lab.setWordWrap(True)
        lab.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)
        b = QPushButton("다시 보지 않기")
        b.setFlat(True)
        b.clicked.connect(lambda: (bar.setVisible(False), self.settings.setValue("tips/hidden", True)))
        lay.addWidget(lab, 1)
        lay.addWidget(b)
        bar.setVisible(not self._tips_hidden())
        return bar

    def _backup_now(self):
        if self.py_path and self.editor.document().isModified():
            recovery.save(self.py_path, self.editor.toPlainText())
        for path, st in self._stash.items():
            recovery.save(path, st["text"])

    def toggle_explorer(self):
        on = self.a_explorer.isChecked()
        self.settings.setValue("view/explorer", on)
        self.explorer_dock.setVisible(on and self.stack.currentIndex() == 1)

    def _refresh_explorer(self):
        """Study folders (if any) else the recent files; the open file is highlighted."""
        if not hasattr(self, "explorer"):
            return
        self.explorer.set_data(existing_folders(load_folders(self.settings)), self._recent(),
                               str(self.py_path) if self.py_path else "")

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
            "<tr><td><b>Ctrl+B</b></td><td>왼쪽 탐색기 보이기/숨기기 (학습 폴더 또는 최근 파일)</td></tr>"
            "<tr><td><b>F5 / Shift+F5</b></td><td>실행 / 중지</td></tr>"
            "<tr><td><b>Ctrl+D</b></td><td>.ui를 Qt Designer로 열기 (저장하면 자동 반영)</td></tr>"
            "<tr><td><b>Ctrl+E</b></td><td>선택한 줄을 AI에게 설명 듣기</td></tr>"
            "<tr><td><b>F2</b></td><td>선택한 위젯의 objectName 바꾸기 (.ui와 Main.py 함께)</td></tr>"
            "<tr><td><b>Ctrl+T</b></td><td>화면 따라 만들기 도전</td></tr>"
            "<tr><td><b>Ctrl+Shift+T</b></td><td>코드 과제 (저장할 때마다 자동 채점)</td></tr>"
            "<tr><td><b>Ctrl+Shift+L</b></td><td>학습 기록 (공부한 날, 많이 본 위젯, 자주 만난 에러)</td></tr>"
            "<tr><td><b>위젯 우클릭</b></td><td>위젯 추가·삭제·순서 바꾸기, 시그널 연결 코드 넣기</td></tr>"
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

    def _apply_icons(self):
        """One matching set of line icons, in the theme's colours (run green, stop red, AI accent)."""
        t = theme.T
        for act, name, color in ((self.a_open, "open", None), (self.a_save, "save", None),
                                 (self.a_designer, "designer", None), (self.a_run, "run", t["run"]),
                                 (self.a_stop, "stop", t["stop"]), (self.a_explain, "ai", t["accent"]),
                                 (self.a_challenge, "challenge", None), (self.a_tasks, "task", None),
                                 (self.a_learnlog, "log", None), (self.a_help, "help", None),
                                 (self.a_find, "find", None), (self.a_study, "folders", None)):
            act.setIcon(icons.icon(name, color))
        for b in self._welcome_buttons:
            b.setIcon(icons.icon(b.icon_name))
        self.explorer.set_icons(icons.icon("folders"), icons.icon("refresh"))

    def _chrome(self):
        """The app look for our own panels (never for an ancestor of the .ui preview, see theme.py)."""
        theme.chrome(self.menuBar(), self.toolbar, self.statusBar(), self.explorer, self.tips, self.editor_box,
                     self.tree_box, self.right_split, self.bottom, self.stack.widget(0))

    def _light_preview(self):
        """The .ui preview keeps the light look it was designed with, also in the dark theme."""
        self.preview.set_fixed_palette(theme.light_palette())

    def toggle_dark(self):
        self._dark = self.a_dark.isChecked()
        self.settings.setValue("view/dark", self._dark)
        theme.apply(QApplication.instance(), self._dark)
        self._light_preview()
        self._apply_icons()
        self.editor.apply_theme()
        self.run_check()                       # re-colours the dimmed (unused) widget names
        theme.retheme_all(self)                # labels, dialogs-in-window, browsers
        self.explorer.refresh()
        self.legend.setText(LEGEND)
        self.line_view._last = None
        self._on_cursor_moved()                # re-draws the 해설 panel with the new colours
        if self.sel:
            self.select(self.sel, "reload")

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
