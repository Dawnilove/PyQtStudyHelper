"""코드 과제: "버튼을 누르면 라벨이 바뀌게 하세요" 같은 과제와 채점 단계.

Pure data + small helpers (no Qt GUI here), so the grader process can import it cheaply.
Each task makes its own task.ui and a starter Main.py; grader.py runs the student's Main.py in a
separate process, plays the steps (type, click …) and checks what the widgets show.
"""
from dataclasses import dataclass, field
from xml.sax.saxutils import escape


@dataclass
class Task:
    id: str
    title: str
    goal: str                       # what the program should do (shown to the student)
    widgets: list                   # rows for the .ui: widget spec or ("h", [specs])
    steps: list                     # grading steps, see grader.py
    hints: list = field(default_factory=list)
    level: int = 1                  # 1 쉬움 · 2 보통 · 3 도전
    window_title: str = ""


def W(cls, name, **props):
    return (cls, name, props)


TASKS = [
    Task("greet", "인사하기",
         "이름을 입력하고 <b>인사</b> 버튼을 누르면, 아래 라벨에 <code>안녕하세요, 민수님!</code>처럼 "
         "입력한 이름이 들어간 인사가 나오게 하세요.",
         [W("QLabel", "lblTitle", text="이름을 입력하세요"), W("QLineEdit", "edtName"),
          W("QPushButton", "btnGreet", text="인사"), W("QLabel", "lblResult", text="")],
         [("set", "edtName", "민수"), ("click", "btnGreet"),
          ("expect", "lblResult", "text", "contains", "민수", "인사 버튼을 누르면 라벨에 입력한 이름이 나와요"),
          ("set", "edtName", "지수"), ("click", "btnGreet"),
          ("expect", "lblResult", "text", "contains", "지수", "다른 이름을 넣어도 그 이름이 나와요 (이름을 고정해서 쓰지 않았어요)")],
         ["버튼이 눌렸을 때 실행할 함수를 만들고 <code>self.btnGreet.clicked.connect(self.함수)</code>로 연결해요.",
          "입력칸 글자는 <code>self.edtName.text()</code>, 라벨에 쓰기는 <code>self.lblResult.setText(...)</code>.",
          "글자 이어 붙이기: <code>f\"안녕하세요, {name}님!\"</code>"]),
    Task("counter", "숫자 세기",
         "<b>+1</b>을 누르면 숫자가 1 커지고, <b>-1</b>을 누르면 1 작아지고, <b>0으로</b>를 누르면 0이 되게 하세요. "
         "숫자는 라벨 <code>lblCount</code>에 보여요.",
         [W("QLabel", "lblCount", text="0"),
          ("h", [W("QPushButton", "btnMinus", text="-1"), W("QPushButton", "btnPlus", text="+1"),
                 W("QPushButton", "btnReset", text="0으로")])],
         [("click", "btnPlus"), ("click", "btnPlus"), ("click", "btnPlus"),
          ("expect", "lblCount", "text", "eq", "3", "+1을 세 번 누르면 3이 돼요"),
          ("click", "btnMinus"), ("expect", "lblCount", "text", "eq", "2", "-1을 누르면 하나 줄어요"),
          ("click", "btnReset"), ("expect", "lblCount", "text", "eq", "0", "0으로를 누르면 0이 돼요"),
          ("click", "btnPlus"), ("expect", "lblCount", "text", "eq", "1", "0으로 한 뒤 다시 세면 1부터 시작해요")],
         ["지금 숫자를 기억할 변수를 <code>__init__</code>에서 만들어요: <code>self.count = 0</code>",
          "버튼마다 함수를 하나씩 만들어 연결해요.",
          "라벨은 글자만 받아요: <code>self.lblCount.setText(str(self.count))</code>"]),
    Task("add", "더하기 계산기",
         "두 칸에 숫자를 넣고 <b>더하기</b>를 누르면 결과 라벨에 합이 나오게 하세요. "
         "숫자가 아닌 글자를 넣고 눌러도 <b>프로그램이 꺼지지 않아야</b> 해요 (안내 문구를 보여 주면 더 좋아요).",
         [("h", [W("QLineEdit", "edtA"), W("QLabel", "lblPlus", text="+"), W("QLineEdit", "edtB")]),
          W("QPushButton", "btnAdd", text="더하기"), W("QLabel", "lblResult", text="")],
         [("set", "edtA", "3"), ("set", "edtB", "4"), ("click", "btnAdd"),
          ("expect", "lblResult", "text", "contains", "7", "3 + 4 를 하면 7이 나와요"),
          ("set", "edtA", "12"), ("set", "edtB", "30"), ("click", "btnAdd"),
          ("expect", "lblResult", "text", "contains", "42", "12 + 30 을 하면 42가 나와요 (글자 이어 붙이기 '1230'이 아니에요)"),
          ("set", "edtA", "abc"), ("set", "edtB", "1"), ("click", "btnAdd"),
          ("no_error", "숫자가 아닌 값을 넣어도 프로그램이 꺼지지 않아요")],
         ["<code>text()</code>는 글자라서 <code>int(...)</code>로 숫자로 바꿔야 해요. 안 바꾸면 '12'+'30' = '1230'.",
          "<code>try:</code> … <code>except ValueError:</code> 로 숫자가 아닐 때를 처리해요.",
          "결과는 <code>str(합)</code>으로 바꿔서 setText 해요."], level=2),
    Task("agree", "동의해야 다음",
         "<b>약관에 동의합니다</b>를 체크했을 때만 <b>다음</b> 버튼을 누를 수 있게 하세요. 체크를 풀면 다시 못 누르게 돼요. "
         "(처음에는 .ui에서 다음 버튼이 꺼져 있어요)",
         [W("QCheckBox", "chkAgree", text="약관에 동의합니다"), W("QPushButton", "btnNext", text="다음", enabled=False)],
         [("expect", "btnNext", "enabled", "eq", False, "처음에는 다음 버튼을 누를 수 없어요"),
          ("set", "chkAgree", True),
          ("expect", "btnNext", "enabled", "eq", True, "체크하면 다음 버튼이 켜져요"),
          ("set", "chkAgree", False),
          ("expect", "btnNext", "enabled", "eq", False, "체크를 풀면 다시 꺼져요")],
         ["체크박스가 바뀔 때마다 오는 시그널: <code>toggled(bool)</code> — 켜졌으면 True, 꺼졌으면 False가 와요.",
          "버튼 켜고 끄기: <code>self.btnNext.setEnabled(True / False)</code>",
          "한 줄로도 돼요: <code>self.chkAgree.toggled.connect(self.btnNext.setEnabled)</code>"]),
    Task("todo", "할 일 목록",
         "입력칸에 할 일을 쓰고 <b>추가</b>를 누르면 목록에 들어가고 입력칸은 비워지게 하세요. "
         "빈 칸일 때는 추가하지 않아요. 목록에서 하나를 고르고 <b>선택 삭제</b>를 누르면 그 항목이 지워져요.",
         [("h", [W("QLineEdit", "edtItem"), W("QPushButton", "btnAdd", text="추가")]),
          W("QListWidget", "lstItems"), W("QPushButton", "btnDelete", text="선택 삭제")],
         [("set", "edtItem", "숙제"), ("click", "btnAdd"),
          ("expect", "lstItems", "count", "eq", 1, "추가를 누르면 목록에 한 줄이 생겨요"),
          ("expect", "edtItem", "text", "eq", "", "추가한 뒤에는 입력칸이 비워져요"),
          ("set", "edtItem", "운동"), ("click", "btnAdd"),
          ("set", "edtItem", "   "), ("click", "btnAdd"),
          ("expect", "lstItems", "count", "eq", 2, "빈 칸(공백만)일 때는 추가하지 않아요"),
          ("set", "lstItems", 0), ("click", "btnDelete"),
          ("expect", "lstItems", "count", "eq", 1, "선택 삭제를 누르면 하나가 지워져요"),
          ("expect", "lstItems", "item0", "eq", "운동", "고른 항목(첫 줄)이 지워져요")],
         ["추가: <code>self.lstItems.addItem(글자)</code>, 입력칸 비우기: <code>self.edtItem.clear()</code>",
          "빈 칸 확인: <code>text = self.edtItem.text().strip()</code> 후 <code>if not text: return</code>",
          "선택한 줄 번호: <code>row = self.lstItems.currentRow()</code> → <code>self.lstItems.takeItem(row)</code>"],
         level=2),
    Task("combo", "과일 고르기",
         "콤보박스에서 과일을 고르면 라벨에 <code>고른 과일: 포도</code>처럼 고른 과일 이름이 나오게 하세요.",
         [W("QComboBox", "cmbFruit", items=["사과", "바나나", "포도"]), W("QLabel", "lblSelected", text="")],
         [("set", "cmbFruit", 2),
          ("expect", "lblSelected", "text", "contains", "포도", "포도를 고르면 라벨에 포도가 나와요"),
          ("set", "cmbFruit", 1),
          ("expect", "lblSelected", "text", "contains", "바나나", "바나나를 고르면 바나나로 바뀌어요")],
         ["선택이 바뀔 때 오는 시그널: <code>currentIndexChanged(int)</code> 또는 <code>currentTextChanged(str)</code>",
          "지금 고른 글자: <code>self.cmbFruit.currentText()</code>"]),
    Task("slider", "볼륨 조절",
         "슬라이더를 움직이면 라벨에 그 숫자가 나오고, 진행 막대도 같은 값이 되게 하세요.",
         [W("QSlider", "sldVolume", maximum=100, orientation="Qt::Horizontal"), W("QLabel", "lblValue", text="0"),
          W("QProgressBar", "prgVolume", value=0)],
         [("set", "sldVolume", 42),
          ("expect", "lblValue", "text", "contains", "42", "슬라이더를 42로 하면 라벨에 42가 나와요"),
          ("expect", "prgVolume", "value", "eq", 42, "진행 막대도 42가 돼요"),
          ("set", "sldVolume", 7),
          ("expect", "prgVolume", "value", "eq", 7, "다시 움직이면 따라 바뀌어요")],
         ["슬라이더가 움직일 때 오는 시그널: <code>valueChanged(int)</code> — 새 값이 함께 와요.",
          "슬롯 함수에서 값을 받아요: <code>def on_volume(self, value):</code>",
          "진행 막대: <code>self.prgVolume.setValue(value)</code>"]),
    Task("hello_box", "알림 창 띄우기",
         "이름을 쓰고 <b>인사</b>를 누르면 <code>QMessageBox</code> 알림 창에 <code>민수님 반가워요!</code>처럼 "
         "이름이 들어간 인사가 나오게 하세요.",
         [W("QLineEdit", "edtName"), W("QPushButton", "btnHello", text="인사")],
         [("set", "edtName", "민수"), ("click", "btnHello"),
          ("msgbox", "민수", "인사 버튼을 누르면 이름이 들어간 알림 창이 떠요"),
          ("set", "edtName", "지수"), ("click", "btnHello"),
          ("msgbox", "지수", "다른 이름도 알림 창에 나와요")],
         ["알림 창 한 줄: <code>QMessageBox.information(self, '제목', '내용')</code>",
          "<code>from PyQt5.QtWidgets import *</code> 를 했다면 QMessageBox를 바로 쓸 수 있어요."], level=2),
]
BY_ID = {t.id: t for t in TASKS}


# ------------------------------------------------------------------ files for a task
def _prop(name, value) -> str:
    if isinstance(value, bool):
        return f'<property name="{name}"><bool>{"true" if value else "false"}</bool></property>'
    if isinstance(value, int):
        return f'<property name="{name}"><number>{value}</number></property>'
    if name == "orientation":
        return f'<property name="{name}"><enum>{value}</enum></property>'
    return f'<property name="{name}"><string>{escape(str(value))}</string></property>'


def _widget(spec, indent) -> str:
    cls, name, props = spec
    pad = " " * indent
    inner = []
    for k, v in props.items():
        if k == "items":
            inner += [f'{pad} <item>{_prop("text", it)}</item>' for it in v]
        else:
            inner.append(f"{pad} {_prop(k, v)}")
    if not inner:
        return f'{pad}<widget class="{cls}" name="{name}"/>'
    return f'{pad}<widget class="{cls}" name="{name}">\n' + "\n".join(inner) + f"\n{pad}</widget>"


def ui_xml(task: Task) -> str:
    rows, n = [], 0
    for r in task.widgets:
        if isinstance(r, tuple) and r[0] == "h":
            n += 1
            inner = "\n".join(f"      <item>\n{_widget(s, 8)}\n      </item>" for s in r[1])
            rows.append(f'    <item>\n     <layout class="QHBoxLayout" name="row{n}">\n{inner}\n     </layout>\n    </item>')
        else:
            rows.append(f"    <item>\n{_widget(r, 5)}\n    </item>")
    title = escape(task.window_title or task.title)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<ui version="4.0">\n <class>MainWindow</class>\n'
            ' <widget class="QMainWindow" name="MainWindow">\n'
            '  <property name="geometry"><rect><x>0</x><y>0</y><width>360</width><height>260</height></rect></property>\n'
            f'  <property name="windowTitle"><string>{title}</string></property>\n'
            '  <widget class="QWidget" name="centralwidget">\n   <layout class="QVBoxLayout" name="verticalLayout">\n'
            + "\n".join(rows) + "\n   </layout>\n  </widget>\n </widget>\n <resources/>\n <connections/>\n</ui>\n")


def widget_names(task: Task) -> list[str]:
    out = []
    for r in task.widgets:
        for s in (r[1] if isinstance(r, tuple) and r[0] == "h" else [r]):
            out.append(f"{s[1]} ({s[0]})")
    return out


def starter_main(task: Task) -> str:
    names = "\n".join(f"#   {n}" for n in widget_names(task))
    goal = (task.goal.replace("<b>", "").replace("</b>", "").replace("<code>", "'").replace("</code>", "'"))
    return f'''# 코드 과제: {task.title}
# {goal}
#
# task.ui 에 있는 위젯:
{names}
#
# 다 했으면 저장(Ctrl+S)하세요. 과제 창에서 자동으로 채점해요.
import sys
from PyQt5.QtWidgets import *
from PyQt5 import uic

form_class = uic.loadUiType("task.ui")[0]


class MainWindow(QMainWindow, form_class):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        # TODO: 여기에서 시그널을 연결하세요


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
'''
