"""시그널 도우미 대화상자: 슬롯 이름을 정하고, 넣을 코드를 미리 본 뒤 Main.py에 넣는다."""
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QLineEdit, QPlainTextEdit,
                             QVBoxLayout)

from . import codegen
from .theme import ThemedLabel


class SignalInsertDialog(QDialog):
    def __init__(self, src, widget, sig, all_sigs, parent=None, target_class=None):
        super().__init__(parent)
        self.src, self.widget, self.sig, self.all_sigs = src, widget, sig, all_sigs
        self.target_class = target_class
        self.plan = None
        signal, args = codegen.parse_signature(sig)
        self.setWindowTitle("시그널 연결 코드 넣기")
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        params = codegen.param_names(args)
        what = (f"<b>{widget}</b> 의 <b>{signal}</b> 시그널이 생기면 실행할 함수(슬롯)를 만들어요.<br>"
                + (f"이 시그널은 값 <b>{', '.join(f'{p} ({t})' for p, t in zip(params, args))}</b> 를 넘겨줘서 "
                   "함수가 받을 자리를 만들어 둘게요." if args else "이 시그널은 값을 넘겨주지 않아요."))
        info = ThemedLabel(what)
        info.setWordWrap(True)
        lay.addWidget(info)
        lay.addWidget(ThemedLabel("슬롯 함수 이름"))
        self.name = QLineEdit(codegen.default_slot_name(widget, signal))
        self.name.textChanged.connect(self._update)
        lay.addWidget(self.name)
        self.msg = ThemedLabel()
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        lay.addWidget(ThemedLabel("Main.py에 들어갈 코드 (넣은 뒤 Ctrl+Z로 한 번에 되돌릴 수 있어요)"))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        f = QFont("Consolas", 10)
        self.preview.setFont(f)
        self.preview.setMinimumHeight(180)
        lay.addWidget(self.preview)
        self.btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btns.button(QDialogButtonBox.Ok).setText("Main.py에 넣기")
        self.btns.button(QDialogButtonBox.Cancel).setText("취소")
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)
        lay.addWidget(self.btns)
        self._update()

    def _update(self):
        name = self.name.text().strip()
        ok_btn = self.btns.button(QDialogButtonBox.Ok)
        if not codegen.valid_name(name):
            self.msg.setText("<span style='color:#c0392b'>영문·숫자·_ 로, 숫자가 아닌 글자로 시작해 주세요.</span>")
            ok_btn.setEnabled(False)
            self.preview.clear()
            return
        try:
            self.plan = codegen.plan_insert(self.src, self.widget, self.sig, self.all_sigs, name,
                                            self.target_class)
        except ValueError as e:
            self.msg.setText(f"<span style='color:#c0392b'>{e}</span>")
            ok_btn.setEnabled(False)
            return
        if self.plan.existing is not None:
            self.msg.setText(f"<span style='color:#b35c00'>이미 {self.plan.existing + 1}줄에 연결돼 있어요. "
                             "[Main.py에 넣기]를 누르면 그 줄로 이동해요.</span>")
            self.preview.setPlainText("")
            ok_btn.setEnabled(True)
            return
        warn = []
        if name.startswith("on_"):
            warn.append("주의: on_위젯_시그널 이름은 setupUi()가 자동으로 한 번 더 연결해서 "
                        "함수가 두 번 실행될 수 있어요. 다른 이름을 권해요.")
        if self.plan.note:
            warn.append(self.plan.note)
        self.msg.setText("<span style='color:#b35c00'>" + "<br>".join(warn) + "</span>" if warn else
                         f"<span style='color:#2b8a3e'>__init__ 의 {self.plan.connect_after + 2}줄에 연결 줄, "
                         "클래스 끝에 함수 틀을 넣어요.</span>")
        text = f"# {self.plan.connect_after + 2}줄 (__init__ 안)\n{self.plan.connect_line.strip()}\n"
        if self.plan.stub:
            text += f"\n# 클래스 끝\n{self.plan.stub.strip(chr(10))}"
        self.preview.setPlainText(text)
        ok_btn.setEnabled(True)
