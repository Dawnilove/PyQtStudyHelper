"""objectName 바꾸기: .ui 와 Main.py 를 함께 바꾼다 (미리 보기 → 적용)."""
import keyword
import re

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLineEdit, QPlainTextEdit, QVBoxLayout

from .theme import ThemedLabel, chrome


def plan_py_rename(src: str, old: str, new: str, is_top: bool, allowed=None) -> tuple[str, list]:
    """(new source, [(line_no, before, after)]) — renames self.old, and Ui_old for the top widget.

    allowed: set of line numbers that may change (the classes built from this .ui), None = all.
    """
    pats = [(re.compile(rf"\bself\.{re.escape(old)}\b"), f"self.{new}")]
    if is_top:   # pyuic names the class Ui_<top objectName>
        pats.append((re.compile(rf"\bUi_{re.escape(old)}\b"), f"Ui_{new}"))
    out, changes = [], []
    for i, line in enumerate(src.split("\n")):
        after = line
        if allowed is None or i in allowed:
            for rx, rep in pats[:1]:
                after = rx.sub(rep, after)
        for rx, rep in pats[1:]:          # Ui_<class> appears in import lines outside the class
            after = rx.sub(rep, after)
        if after != line:
            changes.append((i, line, after))
        out.append(after)
    return "\n".join(out), changes


class RenameDialog(QDialog):
    def __init__(self, old, cls, names, src, is_top, parent=None, allowed=None):
        super().__init__(parent)
        chrome(self)                           # the app look for this dialog
        self.old, self.names, self.src, self.is_top = old, set(names), src, is_top
        self.allowed = allowed
        self.new_src, self.changes = src, []
        self.setWindowTitle("objectName 바꾸기")
        self.setMinimumWidth(640)
        lay = QVBoxLayout(self)
        intro = ThemedLabel(f"<b>{old}</b> ({cls}) 의 이름을 바꿔요. "
                       ".ui 파일과 Main.py의 <code>self." + old + "</code> 를 <b>한꺼번에</b> 바꿔서 짝이 깨지지 않게 해요.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        lay.addWidget(ThemedLabel("새 이름"))
        self.name = QLineEdit(old)
        self.name.selectAll()
        self.name.textChanged.connect(self._update)
        lay.addWidget(self.name)
        self.msg = ThemedLabel()
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        lay.addWidget(ThemedLabel("Main.py에서 바뀌는 줄"))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Consolas", 10))
        self.preview.setMinimumHeight(180)
        lay.addWidget(self.preview)
        self.save_py = QCheckBox("Main.py도 바로 저장 (권장: .ui는 바로 저장되니까 둘이 어긋나지 않게)")
        self.save_py.setChecked(True)
        lay.addWidget(self.save_py)
        tip = ThemedLabel("<span style='color:#888'>이름 짓기 팁: 종류를 앞에 붙이면 코드에서 알아보기 쉬워요 — "
                     "btnSave(버튼), lblResult(라벨), lineName(입력칸), chkAgree(체크박스)</span>")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        self.btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btns.button(QDialogButtonBox.Ok).setText("바꾸기")
        self.btns.button(QDialogButtonBox.Cancel).setText("취소")
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)
        lay.addWidget(self.btns)
        self._update()

    @property
    def new(self):
        return self.name.text().strip()

    def _update(self):
        new = self.new
        ok = self.btns.button(QDialogButtonBox.Ok)
        err = None
        if new == self.old:
            err = "새 이름을 입력해 주세요."
        elif not re.fullmatch(r"[A-Za-z_]\w*", new) or keyword.iskeyword(new):
            err = "영문·숫자·_ 로, 숫자가 아닌 글자로 시작해야 해요 (파이썬 변수 이름 규칙)."
        elif new in self.names:
            err = f"'{new}' 는 이미 .ui에 있는 이름이에요."
        if err:
            self.msg.setText(f"<span style='color:#c0392b'>{err}</span>")
            ok.setEnabled(False)
            self.preview.clear()
            return
        self.new_src, self.changes = plan_py_rename(self.src, self.old, new, self.is_top, self.allowed)
        warn = []
        if self.is_top:
            warn.append(f"최상위 위젯이라 pyuic가 만드는 클래스 이름도 Ui_{self.old} → Ui_{new} 로 바뀌어요. "
                        "import 줄도 같이 바꿔요.")
        if re.search(rf"\bdef\s+on_{re.escape(self.old)}_", self.src):
            warn.append(f"on_{self.old}_… 함수는 이름으로 자동 연결되던 것이라, 이름을 바꾸면 자동 연결이 끊겨요.")
        text = "\n".join(f"{i + 1:>4}- {a.strip()}\n{i + 1:>4}+ {b.strip()}" for i, a, b in self.changes)
        self.preview.setPlainText(text or "(Main.py에서는 아직 이 이름을 안 써요 — .ui만 바뀌어요)")
        self.msg.setText("<span style='color:#b35c00'>" + "<br>".join(warn) + "</span>" if warn else
                         f"<span style='color:#2b8a3e'>.ui의 이름과 참조, Main.py {len(self.changes)}줄을 바꿔요.</span>")
        ok.setEnabled(True)
