"""시작 화면: 최근 파일, 학습 폴더의 Main 파일 모아 보기."""
import time
from pathlib import Path

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from . import icons
from .studyfolders import existing_folders, load_folders, main_label
from .theme import ThemedLabel


class WelcomeMixin:
    """MainWindow part: 시작 화면: 최근 파일, 학습 폴더의 Main 파일 모아 보기."""

    def _build_welcome(self) -> QWidget:
        page = QWidget()
        page.setObjectName("welcome")
        outer = QVBoxLayout(page)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        box = QVBoxLayout()
        title = ThemedLabel("<span style='font-size:22pt;font-weight:600'>PyQt 학습 도우미</span>")
        sub = ThemedLabel("Designer에서 만든 <b>.ui</b>와 내가 짠 <b>Main.py</b>를 연결해서 보며 공부해요.")
        sub.setStyleSheet("color:#8a8f98;font-size:11pt")
        box.addWidget(title)
        box.addWidget(sub)
        box.addSpacing(18)
        btn = QPushButton("  파일 열기  (Ctrl+O)")
        btn.setIcon(icons.icon("open", "#ffffff"))
        btn.setIconSize(QSize(20, 20))
        btn.setObjectName("bigButton")
        btn.clicked.connect(self.open_dialog)
        box.addWidget(btn)
        hint = ThemedLabel("또는 Main.py / gui.ui / 실습 폴더를 이 창에 끌어다 놓으세요.")
        hint.setStyleSheet("color:#888")
        box.addWidget(hint)
        box.addSpacing(6)
        more = QHBoxLayout()
        self._welcome_buttons = []
        for text, icon_name, slot, tip in (
                ("코드 과제 풀기", "task", self.open_tasks, "짧은 과제를 풀면 저장할 때마다 자동으로 채점해요"),
                ("화면 따라 만들기", "challenge", self.start_challenge, "목표 화면을 Designer로 똑같이 만들어 보기"),
                ("학습 기록", "log", self.show_learnlog, "공부한 날, 많이 본 위젯, 자주 만난 에러")):
            b = QPushButton(text)
            b.setIconSize(QSize(18, 18))
            b.setToolTip(tip)
            b.clicked.connect(slot)
            b.icon_name = icon_name
            more.addWidget(b)
            self._welcome_buttons.append(b)
        more.addStretch(1)
        box.addLayout(more)
        box.addSpacing(14)
        box.addWidget(ThemedLabel("<b>최근 파일</b>  <span style='color:#888'>(더블클릭)</span>"))
        self.recent_list = QListWidget()
        self.recent_list.setMinimumWidth(560)
        self.recent_list.setMaximumHeight(220)
        self.recent_list.itemActivated.connect(lambda it: self.open_path(it.data(Qt.UserRole)))
        box.addWidget(self.recent_list)
        box.addSpacing(14)
        steps = ThemedLabel(
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
        self._refresh_explorer()

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
            header.setForeground(QColor("#8a8f98"))
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
        self.a_explorer.setEnabled(on)
        self.explorer_dock.setVisible(on and self.a_explorer.isChecked())     # the start screen lists files itself
        if idx == 0:
            self._rescan_study()                   # also runs once at start-up, when the start screen is built
