"""도전 모드: 목표 화면(.ui)을 보고 Designer로 똑같이 만들어 보기. 저장할 때마다 자동 채점."""
from collections import Counter
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QListWidget, QListWidgetItem, QProgressBar, QPushButton,
                             QSplitter, QVBoxLayout, QWidget)

from . import learnlog, theme
from .preview import PreviewPane
from .ui_model import UiModel
from .theme import ThemedLabel, chrome

SKIP = {"QWidget", "QMenuBar", "QStatusBar"}          # always generated / plumbing
TEXT_PROPS = ("text", "title", "windowTitle", "placeholderText")

TEMPLATES = {
    "QMainWindow": """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>MainWindow</class>
 <widget class="QMainWindow" name="MainWindow">
  <property name="geometry"><rect><x>0</x><y>0</y><width>400</width><height>300</height></rect></property>
  <property name="windowTitle"><string>MainWindow</string></property>
  <widget class="QWidget" name="centralwidget"/>
  <widget class="QMenuBar" name="menubar"/>
  <widget class="QStatusBar" name="statusbar"/>
 </widget>
 <resources/>
 <connections/>
</ui>
""",
    "QDialog": """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>Dialog</class>
 <widget class="QDialog" name="Dialog">
  <property name="geometry"><rect><x>0</x><y>0</y><width>400</width><height>300</height></rect></property>
  <property name="windowTitle"><string>Dialog</string></property>
 </widget>
 <resources/>
 <connections/>
</ui>
""",
    "QWidget": """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>Form</class>
 <widget class="QWidget" name="Form">
  <property name="geometry"><rect><x>0</x><y>0</y><width>400</width><height>300</height></rect></property>
  <property name="windowTitle"><string>Form</string></property>
 </widget>
 <resources/>
 <connections/>
</ui>
""",
}


def _texts(model: UiModel) -> Counter:
    c = Counter()
    for n in model.nodes.values():
        if n.kind != "widget" or n is model.top:
            continue
        for k, v in n.props:
            if k in TEXT_PROPS and v.strip():
                c[(n.cls, v.strip())] += 1
    return c


def compare(target: UiModel, mine: UiModel) -> list[tuple[bool, str, str]]:
    """[(passed, check, hint)]"""
    out = []
    t_top, m_top = target.top.cls if target.top else "?", mine.top.cls if mine.top else "?"
    out.append((t_top == m_top, f"창 종류: {t_top}", f"내 것은 {m_top}" if t_top != m_top else ""))

    tw = Counter(n.cls for n in target.nodes.values() if n.kind == "widget" and n is not target.top
                 and n.cls not in SKIP)
    mw = Counter(n.cls for n in mine.nodes.values() if n.kind == "widget" and n is not mine.top
                 and n.cls not in SKIP)
    for cls, cnt in sorted(tw.items()):
        have = mw.get(cls, 0)
        out.append((have == cnt, f"{cls} {cnt}개", f"지금 {have}개" if have != cnt else ""))
    for cls in sorted(set(mw) - set(tw)):
        out.append((False, f"{cls} 는 목표 화면에 없어요", f"지금 {mw[cls]}개 — 지워 보세요"))

    tl = Counter(n.cls for n in target.nodes.values() if n.kind == "layout")
    ml = Counter(n.cls for n in mine.nodes.values() if n.kind == "layout")
    for cls, cnt in sorted(tl.items()):
        out.append((ml.get(cls, 0) >= cnt, f"레이아웃 {cls} {cnt}개 사용",
                    f"지금 {ml.get(cls, 0)}개" if ml.get(cls, 0) < cnt else ""))

    tt, mt = _texts(target), _texts(mine)
    for (cls, text), cnt in sorted(tt.items()):
        ok = mt.get((cls, text), 0) >= cnt
        out.append((ok, f"{cls} 글자 '{text}'", "" if ok else "글자(text 속성)를 확인해 보세요"))

    tn = {n.name for n in target.nodes.values() if n.kind == "widget" and n.cls not in SKIP}
    same = tn & set(mine.nodes)
    out.append((same == tn, f"objectName까지 같게 (보너스) {len(same)}/{len(tn)}",
                "이름까지 같으면 정답 Main.py를 그대로 붙여 쓸 수 있어요" if same != tn else ""))
    return out


class ChallengeWindow(QDialog):
    """Non-modal: target preview on the left, live checklist on the right."""
    newUiRequested = pyqtSignal(str)        # path of a fresh .ui to build in

    def __init__(self, target_path: Path, parent=None):
        super().__init__(parent, Qt.Window)
        self.target_path = Path(target_path)
        self.target = UiModel(self.target_path)
        self.setWindowTitle(f"도전: {self.target_path.parent.name}/{self.target_path.name} 따라 만들기")
        self.resize(1000, 560)
        lay = QVBoxLayout(self)
        info = ThemedLabel("왼쪽 <b>목표 화면</b>을 Qt Designer로 똑같이 만들어 보세요. "
                      "Designer에서 <b>저장할 때마다</b> 오른쪽 체크리스트가 자동으로 채점돼요.")
        info.setWordWrap(True)
        lay.addWidget(info)
        sp = QSplitter()
        self.preview = PreviewPane()
        self.preview.load(self.target_path, [])
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(ThemedLabel("<b>목표 화면</b>"))
        ll.addWidget(self.preview, 1)
        sp.addWidget(left)
        right = QWidget()
        chrome(right)                            # not the whole window: the target preview keeps the Designer look
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.mine_label = ThemedLabel()
        self.mine_label.setWordWrap(True)
        rl.addWidget(self.mine_label)
        self.bar = QProgressBar()
        rl.addWidget(self.bar)
        self.checks = QListWidget()
        rl.addWidget(self.checks, 1)
        row = QHBoxLayout()
        b_new = QPushButton("빈 .ui 만들어서 시작 (Designer로 열기)")
        b_new.setObjectName("primary")
        b_new.clicked.connect(self._new_ui)
        row.addWidget(b_new)
        row.addStretch(1)
        rl.addLayout(row)
        sp.addWidget(right)
        sp.setSizes([520, 480])
        lay.addWidget(sp, 1)
        self.update_mine(None)

    def _new_ui(self):
        from PyQt5.QtWidgets import QFileDialog
        start = str(self.target_path.parent / "my_challenge.ui")
        path, _ = QFileDialog.getSaveFileName(self, "내가 만들 .ui 파일", start, "Qt Designer (*.ui)")
        if not path:
            return
        top = self.target.top.cls if self.target.top else "QMainWindow"
        Path(path).write_text(TEMPLATES.get(top, TEMPLATES["QMainWindow"]), encoding="utf-8")
        self.newUiRequested.emit(path)

    def update_mine(self, mine_path):
        self.checks.clear()
        if not mine_path or Path(mine_path).resolve() == self.target_path.resolve():
            self.mine_label.setText("<span style='color:#888'>아직 내 .ui가 없어요 → 아래 "
                                    "<b>빈 .ui 만들어서 시작</b>을 누르세요.</span>")
            self.bar.setValue(0)
            return
        try:
            mine = UiModel(mine_path)
        except Exception:
            self.mine_label.setText("내 .ui를 읽는 중이에요… (저장 중일 수 있어요)")
            return
        res = compare(self.target, mine)
        main = [r for r in res if "보너스" not in r[1]]
        passed = sum(1 for ok, _, _ in main if ok)
        pct = round(100 * passed / max(1, len(main)))
        self.bar.setValue(pct)
        done = passed == len(main)
        if done:
            learnlog.note_challenge(f"{self.target_path.parent.name}/{self.target_path.name}")
        self.mine_label.setText(f"내 파일: <b>{Path(mine_path).name}</b> — "
                                + ("<span style='color:#2b8a3e;font-size:12pt'><b>★ 완성! 목표 화면과 구조가 같아요.</b></span>"
                                   if done else f"{passed}/{len(main)} 통과"))
        for ok, check, hint in res:
            it = QListWidgetItem(("●  " if ok else "○  ") + check + (f"   — {hint}" if hint else ""))
            it.setForeground(QColor(theme.fg("#2b8a3e") if ok else theme.T["text"]))   # readable in both themes
            self.checks.addItem(it)
