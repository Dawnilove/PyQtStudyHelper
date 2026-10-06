"""설정 창: 흩어져 있던 설정을 한곳에서 (Ctrl+,)."""
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
                             QHBoxLayout, QPushButton, QSpinBox, QVBoxLayout)

from .theme import ThemedLabel, chrome

BACKUP_CHOICES = [("10초마다", 10), ("20초마다 (기본)", 20), ("1분마다", 60), ("끄기", 0)]


class SettingsDialog(QDialog):
    """values: dict with dark, zoom, legend, explorer, tips, restore, update, backup (seconds, 0 = off).
    actions: {label: callable} for the buttons that open other windows (AI 설정, 노트 폴더 …)."""

    def __init__(self, values: dict, actions: dict, parent=None):
        super().__init__(parent)
        chrome(self)
        self.setWindowTitle("설정")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)

        look = QGroupBox("화면")
        f = QFormLayout(look)
        self.dark = QCheckBox("어두운 테마")
        self.dark.setChecked(values.get("dark", False))
        f.addRow(self.dark)
        self.zoom = QSpinBox()
        self.zoom.setRange(-4, 12)
        self.zoom.setValue(values.get("zoom", 0))
        self.zoom.setToolTip("0이 기본 크기예요. 1 올릴 때마다 1pt씩 커져요 (Ctrl+휠로도 바꿀 수 있어요)")
        f.addRow("코드 글자 크기 (0 = 기본)", self.zoom)
        self.legend = QCheckBox("코드 아래 색 범례 보이기")
        self.legend.setChecked(values.get("legend", True))
        f.addRow(self.legend)
        self.explorer = QCheckBox("왼쪽 탐색기 보이기 (Ctrl+B)")
        self.explorer.setChecked(values.get("explorer", True))
        f.addRow(self.explorer)
        self.tips = QCheckBox("처음 쓰는 사람용 안내 줄 보이기")
        self.tips.setChecked(values.get("tips", True))
        f.addRow(self.tips)
        lay.addWidget(look)

        start = QGroupBox("시작과 저장")
        f = QFormLayout(start)
        self.restore = QCheckBox("켤 때 지난번에 열어 둔 파일 다시 열기")
        self.restore.setChecked(values.get("restore", True))
        f.addRow(self.restore)
        self.update = QCheckBox("켤 때 새 버전이 있는지 확인 (GitHub, 하루 한 번)")
        self.update.setChecked(values.get("update", True))
        f.addRow(self.update)
        self.backup = QComboBox()
        for label, sec in BACKUP_CHOICES:
            self.backup.addItem(label, sec)
        i = self.backup.findData(values.get("backup", 20))
        self.backup.setCurrentIndex(i if i >= 0 else 1)
        f.addRow("저장 안 한 코드 자동 백업", self.backup)
        lay.addWidget(start)

        more = QGroupBox("다른 설정 창")
        ml = QVBoxLayout(more)
        row = QHBoxLayout()
        for i, (label, fn) in enumerate(actions.items()):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
            if i % 2 == 1:
                ml.addLayout(row)
                row = QHBoxLayout()
        if row.count():
            row.addStretch(1)
            ml.addLayout(row)
        lay.addWidget(more)
        lay.addWidget(ThemedLabel("<span style='color:#888'>API 키는 이 PC의 Windows 자격 증명 관리자에만 저장돼요.</span>"))

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("적용")
        bb.button(QDialogButtonBox.Cancel).setText("취소")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def values(self) -> dict:
        return {"dark": self.dark.isChecked(), "zoom": self.zoom.value(), "legend": self.legend.isChecked(),
                "explorer": self.explorer.isChecked(), "tips": self.tips.isChecked(),
                "restore": self.restore.isChecked(), "update": self.update.isChecked(),
                "backup": self.backup.currentData()}
