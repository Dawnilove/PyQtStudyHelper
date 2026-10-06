"""위젯 추가 창: 종류, objectName(자동 제안), 글자·항목, 넣을 위치."""
from html import escape

from PyQt5.QtWidgets import (QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
                             QRadioButton, QVBoxLayout, QWidget)

from .theme import ThemedLabel, chrome
from .uiedit import BY_CLASS, CLASSES, name_problem, suggest_name

TEXT_LABEL = {"text": "글자", "placeholder": "안내 글자", "items": "항목"}
TEXT_HINT = {"text": "버튼·라벨에 보이는 글자", "placeholder": "비어 있을 때 흐리게 보이는 안내 (예: 이름을 입력하세요)",
             "items": "쉼표로 나눠 쓰세요 (예: 사과, 바나나, 포도)"}
DEFAULT_TEXT = {"QPushButton": "버튼", "QLabel": "라벨", "QCheckBox": "체크박스", "QRadioButton": "선택",
                "QComboBox": "사과, 바나나, 포도"}


class AddWidgetDialog(QDialog):
    def __init__(self, taken, places, parent=None):
        super().__init__(parent)
        chrome(self)
        self.setWindowTitle("위젯 추가")
        self.setMinimumWidth(440)
        self.taken = set(taken)
        self._name_touched = False
        self._text_touched = False
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.cls = QComboBox()
        for cls, _prefix, kor, _size, _kind in CLASSES:
            self.cls.addItem(f"{kor}  ({cls})", cls)
        form.addRow("종류", self.cls)
        self.name = QLineEdit()
        self.name.textEdited.connect(lambda _: setattr(self, "_name_touched", True))
        form.addRow("objectName", self.name)
        self.text = QLineEdit()
        self.text.textEdited.connect(lambda _: setattr(self, "_text_touched", True))
        self.text_label = QLabel("글자")
        form.addRow(self.text_label, self.text)
        lay.addLayout(form)

        lay.addWidget(ThemedLabel("<b>넣을 위치</b>"))
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(8, 0, 0, 0)
        self.places = QButtonGroup(self)
        self._keys = []
        for i, (key, label) in enumerate(places):
            rb = QRadioButton(label)
            rb.setChecked(i == 0)
            self.places.addButton(rb, i)
            self._keys.append(key)
            bl.addWidget(rb)
        lay.addWidget(box)

        self.info = ThemedLabel("")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("추가")
        self.buttons.button(QDialogButtonBox.Ok).setObjectName("primary")
        self.buttons.button(QDialogButtonBox.Cancel).setText("취소")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)

        self.cls.currentIndexChanged.connect(self._on_class)
        self.name.textChanged.connect(self._validate)
        self._on_class()

    def _on_class(self, _=None):
        cls = self.cls.currentData()
        if not self._name_touched:
            self.name.setText(suggest_name(cls, self.taken))
        kind = BY_CLASS[cls][4]
        self.text_label.setVisible(kind is not None)
        self.text.setVisible(kind is not None)
        if kind:
            self.text_label.setText(TEXT_LABEL[kind])
            self.text.setPlaceholderText(TEXT_HINT[kind])
            if not self._text_touched:
                self.text.setText(DEFAULT_TEXT.get(cls, ""))
        self._validate()

    def _validate(self, _=None):
        name = self.name.text().strip()
        err = name_problem(name, self.taken)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(err is None)
        if err:
            self.info.setText(f"<span style='color:#c0392b'>{escape(err)}</span>")
        else:
            self.info.setText(f"<span style='color:#888'>Main.py에서는 <code>self.{escape(name)}</code> 로 써요. "
                              "추가한 뒤 위젯을 우클릭하면 시그널 연결 코드를 넣을 수 있어요.</span>")

    def values(self):
        """(class, objectName, text, where)"""
        i = self.places.checkedId()
        where = self._keys[i] if 0 <= i < len(self._keys) else (self._keys[0] if self._keys else "")
        return self.cls.currentData(), self.name.text().strip(), self.text.text(), where
