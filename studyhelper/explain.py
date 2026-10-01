"""Offline line explainer: what a line of Main.py does and *why* it is written that way.

Each rule: (regex, title, what, why, pitfall). Several rules can match one line.
Text may use {0}, {1}... for regex groups.
"""
import re
from dataclasses import dataclass


@dataclass
class Note:
    title: str
    what: str
    why: str = ""
    pitfall: str = ""


R = []


def rule(pattern, title, what, why="", pitfall=""):
    R.append((re.compile(pattern), title, what, why, pitfall))


# --- imports / setup -------------------------------------------------------
rule(r"^import\s+sys\b|^import\s+sys,", "import sys",
     "파이썬 실행 환경을 다루는 sys 모듈을 가져와요.",
     "QApplication(sys.argv)에 명령줄 인자를 넘기고, sys.exit()로 종료 코드를 돌려주는 데 써요.")
rule(r"subprocess", "subprocess",
     "다른 프로그램(명령)을 파이썬 안에서 실행하는 모듈이에요.",
     "여기서는 pyuic로 .ui → .py 변환을 실행할 때마다 자동으로 돌리려고 써요.")
rule(r"from PyQt5\.(\w+) import \*", "from PyQt5.{0} import *",
     "PyQt5.{0} 모듈의 모든 이름(클래스)을 가져와요.",
     "QtWidgets = 버튼·창 같은 위젯, QtCore = 시그널·타이머·Qt 상수, QtGui = 그림·폰트·색. "
     "* 로 가져오면 QMessageBox 처럼 바로 쓸 수 있어요.",
     "* 는 편하지만 이름이 어디서 왔는지 안 보여요. 큰 프로젝트에선 필요한 것만 import 해요.")
rule(r"^\s*(\w+_FILE_NAME)\s*=\s*['\"](\w+)['\"]", "{0} = '{1}'",
     "변환할 .ui 파일 이름을 변수에 담아요.",
     "아래 pyuic 명령에서 {1}.ui → {1}.py 로 같은 이름을 두 번 쓰니까, 한 곳만 바꾸면 되게 하려고요.",
     "이 이름과 아래 `from ... import` 의 모듈 이름이 같아야 해요. 다르면 고친 .ui가 반영 안 돼요.")
rule(r"PyQt5\.uic\.pyuic", "pyuic 변환",
     "`python -m PyQt5.uic.pyuic -x gui.ui -o gui.py` 명령을 실행해 .ui를 파이썬 코드로 바꿔요.",
     "Main.py를 실행할 때마다 변환하니까, Designer에서 저장만 하면 다음 실행에 바로 반영돼요.")
rule(r"'-x'", "-x 옵션", "생성된 gui.py 끝에 `if __name__ == '__main__':` 실행 코드를 붙여요.",
     "gui.py만 따로 실행해도 화면을 확인할 수 있게 하려는 옵션이에요.")
rule(r"'-o'", "-o 옵션", "결과를 저장할 파일 이름(output)을 지정해요.")
rule(r"from (\w+) import (Ui_\w+)", "from {0} import {1}",
     "pyuic가 만든 {0}.py 에서 화면 설계 클래스 {1} 를 가져와요.",
     "{1} 에는 setupUi() 가 들어 있어서, 상속하면 Designer에서 만든 위젯이 생겨요.",
     "클래스 이름은 Designer 최상위 위젯의 objectName으로 정해져요 (QDialog면 보통 Ui_Dialog).")
rule(r"uic\.loadUiType\(", "uic.loadUiType()",
     ".ui 파일을 실행 중에 바로 읽어 (설계 클래스, 기반 클래스) 두 개를 돌려줘요.",
     "pyuic 변환 없이 .ui를 직접 쓰는 방법이에요. gui.py 파일이 필요 없어요.")
rule(r"uic\.loadUi\(", "uic.loadUi()",
     ".ui 파일을 읽어 위젯을 바로 만들어요.",
     "변환 파일 없이 .ui를 그대로 쓰는 가장 간단한 방법이에요.")

# --- class / init -------------------------------------------------------------
rule(r"^\s*class\s+(\w+)\((Q\w+),\s*(\w+)\)", "class {0}({1}, {2})",
     "{0} 클래스를 만들면서 {1} 와 {2} 를 함께 상속해요 (다중 상속).",
     "{1} 에게서 '창'의 기능(show, close, 시그널…)을, {2} 에게서 '위젯 배치(setupUi)'를 받아요. "
     "그래서 self.버튼이름 으로 위젯에 바로 접근할 수 있어요.")
rule(r"^\s*class\s+(\w+)\((Q\w+)\)", "class {0}({1})",
     "{1} 를 상속해서 나만의 위젯/창 클래스를 만들어요.",
     "상속하면 {1} 의 기능은 그대로 쓰고, 필요한 메서드(이벤트 처리 등)만 바꿔 쓸 수 있어요.")
rule(r"def __init__\(self", "def __init__(self…)",
     "객체가 만들어질 때 자동으로 실행되는 '생성자'예요.",
     "창이 뜨기 전에 위젯 만들기, 시그널 연결 같은 준비 작업을 여기서 해요.")
rule(r"super\(\)\.__init__\(", "super().__init__()",
     "부모 클래스(QMainWindow 등)의 생성자를 먼저 실행해요.",
     "부모가 창을 제대로 만들어야 그 위에 위젯을 올릴 수 있어요.",
     "빼먹으면 'super-class __init__() was never called' 에러가 나요.")
rule(r"self\.setupUi\(self\)", "self.setupUi(self)",
     "Designer에서 만든 위젯들을 이 창(self) 위에 실제로 만들어 붙여요.",
     "이 줄이 실행된 뒤부터 self.btn이름 같은 위젯 변수가 생겨요.",
     "이 줄보다 먼저 self.위젯 을 쓰면 AttributeError가 나요.")
rule(r"self\.retranslateUi\(", "retranslateUi()", "위젯의 글자(text, 제목)를 설정해요.",
     "언어 번역을 바꿀 때 글자만 다시 넣을 수 있게 분리돼 있어요.")

# --- signals / slots -----------------------------------------------------------
SIGNAL_ARGS = {
    "clicked": "bool (체크 상태)", "toggled": "bool (켜짐/꺼짐)", "pressed": "없음", "released": "없음",
    "textChanged": "str (바뀐 글자) — QPlainTextEdit은 인자 없음", "textEdited": "str",
    "returnPressed": "없음", "editingFinished": "없음",
    "valueChanged": "int/float (새 값)", "currentIndexChanged": "int (새 번호)",
    "currentTextChanged": "str", "stateChanged": "int (0/1/2: 꺼짐/부분/켜짐)",
    "triggered": "bool", "timeout": "없음", "buttonClicked": "QAbstractButton (눌린 버튼)",
    "itemClicked": "항목 객체", "accepted": "없음", "rejected": "없음", "activated": "int",
    "sliderMoved": "int", "dateChanged": "QDate", "timeChanged": "QTime",
}
rule(r"self\.(\w+)\.(\w+)\.connect\(self\.(\w+)\)", "시그널 연결",
     "{0} 의 {1} 시그널이 발생하면 self.{2}() 를 자동으로 호출하게 연결해요.",
     "Qt는 '이벤트가 생기면 함수 호출'을 시그널-슬롯으로 처리해요. 직접 호출하는 게 아니라 연결만 해 두는 거예요.",
     "connect(self.{2}()) 처럼 괄호를 붙이면 지금 바로 실행돼 버려요. 함수 이름만 넘겨요.")
rule(r"\.(\w+)\.connect\(\s*lambda", "lambda로 연결",
     "{0} 시그널에 이름 없는 함수(lambda)를 연결해요.",
     "슬롯에 내가 정한 값을 넘기고 싶을 때 써요. 예: connect(lambda: self.calc('+')).",
     "반복문 안에서 lambda를 만들면 마지막 값만 쓰여요 → lambda x=i: ... 처럼 기본값으로 묶어요.")
rule(r"\.(\w+)\.connect\(", "{0} 시그널",
     "{0} 시그널이 넘겨주는 값: {sig}",
     "슬롯 함수는 이 값을 받을 자리가 있어야 해요 (없으면 무시해도 되는 시그널도 있어요).")
rule(r"(\w+)\s*=\s*pyqtSignal\(", "pyqtSignal()",
     "나만의 시그널 {0} 를 만들어요.",
     "다른 객체(다른 창, 스레드)에 '일이 생겼다'고 알릴 때 써요.",
     "클래스 몸통(메서드 밖)에 만들어야 해요. __init__ 안에서 만들면 동작하지 않아요.")
rule(r"\.emit\(", ".emit()", "시그널을 직접 발생시켜요. 연결된 슬롯들이 호출돼요.")
rule(r"self\.sender\(\)", "self.sender()",
     "지금 슬롯을 호출한 위젯(시그널을 보낸 쪽)을 알려줘요.",
     "버튼 여러 개를 슬롯 하나에 연결하고, 어느 버튼인지 구분할 때 써요.")

# --- common widget methods -------------------------------------------------------
rule(r"\.setText\(", ".setText()", "위젯에 보이는 글자를 바꿔요.", "",
     "문자열만 받아요. 숫자는 str(값) 으로 바꿔서 넣어요.")
rule(r"\.text\(\)", ".text()", "위젯에 입력/표시된 글자를 문자열(str)로 가져와요.", "",
     "숫자로 계산하려면 int()/float() 로 바꿔야 해요. 빈 문자열이면 변환 에러가 나요.")
rule(r"\.toPlainText\(\)", ".toPlainText()", "QTextEdit/QPlainTextEdit 의 전체 글자를 가져와요.")
rule(r"\.(setPlainText|appendPlainText|append)\(", ".{0}()", "여러 줄 입력칸에 글자를 넣거나 덧붙여요.")
rule(r"\.isChecked\(\)", ".isChecked()", "체크박스/라디오 버튼이 체크돼 있으면 True를 돌려줘요.")
rule(r"\.setChecked\(", ".setChecked()", "체크 상태를 코드로 바꿔요.", "",
     "상태가 바뀌면 toggled 시그널도 발생해요.")
rule(r"\.checkState\(\)", ".checkState()", "체크 상태를 0/1/2(Qt.Unchecked/PartiallyChecked/Checked)로 돌려줘요.")
rule(r"\.value\(\)", ".value()", "스핀박스/슬라이더 등의 현재 숫자 값을 가져와요 (이미 숫자라 변환 불필요).")
rule(r"\.setValue\(", ".setValue()", "숫자 값을 코드로 바꿔요. valueChanged 시그널이 발생해요.")
rule(r"\.currentText\(\)", ".currentText()", "콤보박스에서 선택된 항목의 글자를 가져와요.")
rule(r"\.currentIndex\(\)", ".currentIndex()", "선택된 항목의 번호(0부터)를 가져와요. 선택이 없으면 -1.")
rule(r"\.addItems?\(", ".addItem()", "콤보박스/리스트에 항목을 추가해요 (addItems는 리스트로 여러 개).")
rule(r"\.clear\(\)", ".clear()", "위젯의 내용을 모두 지워요.")
rule(r"\.setEnabled\(", ".setEnabled()", "위젯을 쓸 수 있게(True)/회색으로 막게(False) 해요.")
rule(r"\.(setVisible|show|hide)\(", ".{0}()", "위젯이나 창을 보이거나 숨겨요.")
rule(r"\.setWindowTitle\(", ".setWindowTitle()", "창 제목 표시줄의 글자를 바꿔요.")
rule(r"\.setStyleSheet\(", ".setStyleSheet()",
     "CSS와 비슷한 문법으로 색·글꼴·테두리를 꾸며요.", "",
     "문법이 틀려도 에러 없이 그냥 무시돼요. 적용이 안 되면 철자와 세미콜론을 확인해요.")
rule(r"\.setPixmap\(", ".setPixmap()", "QLabel에 그림(QPixmap)을 표시해요.")
rule(r"QPixmap\(", "QPixmap()", "화면에 그리기 좋은 형태로 이미지를 불러와요.", "",
     "경로가 틀려도 에러 없이 빈 그림이 돼요. isNull()로 확인할 수 있어요.")
rule(r"\.resize\(", ".resize()", "창이나 위젯의 크기를 바꿔요.")
rule(r"\.adjustSize\(", ".adjustSize()", "내용(글자)에 딱 맞게 크기를 맞춰요.")
rule(r"\.setGeometry\(", ".setGeometry()", "위치(x, y)와 크기(폭, 높이)를 한 번에 정해요.", "",
     "레이아웃 안의 위젯은 레이아웃이 크기를 다시 정하니까 효과가 없을 수 있어요.")
rule(r"\.findChildren\(", ".findChildren()", "자식 위젯 중 특정 종류를 모두 찾아 리스트로 돌려줘요.",
     "같은 종류 위젯 여러 개에 한꺼번에 같은 처리를 하려고 써요.")
rule(r"\.hasAcceptableInput\(\)", ".hasAcceptableInput()",
     "QLineEdit에 설정한 검증기/입력 마스크 조건을 입력값이 만족하는지 확인해요.")
rule(r"\.close\(\)", ".close()", "창을 닫아요. closeEvent가 호출돼요.")
rule(r"\.split\(['\"]/['\"]\)\[-1\]", "split('/')[-1]",
     "경로를 / 로 잘라서 마지막 조각, 즉 파일 이름만 꺼내요.",
     "QFileDialog는 C:/폴더/파일.txt 처럼 / 를 써서 돌려주니까 / 로 잘라요.")
rule(r"QFileInfo\(", "QFileInfo()", "파일 경로에서 이름·확장자·크기 같은 정보를 꺼내는 도우미예요.")

# --- dialogs ---------------------------------------------------------------
rule(r"QFileDialog\.getOpenFileNames?\(", "QFileDialog.getOpenFileName()",
     "'파일 열기' 창을 띄우고, 고른 파일 경로와 선택한 필터를 (경로, 필터) 튜플로 돌려줘요.",
     "값이 2개라서 filepath, filter_type = ... 처럼 나눠 받아요.",
     "취소하면 경로가 빈 문자열('')이에요 → 다음 줄에서 if filepath: 로 확인해요.")
rule(r"QFileDialog\.getSaveFileName\(", "QFileDialog.getSaveFileName()",
     "'다른 이름으로 저장' 창을 띄우고 (경로, 필터) 를 돌려줘요. 파일을 실제로 저장하지는 않아요.",
     "경로만 받아 오고, 저장은 내 코드에서 open(...) 으로 직접 해요.")
rule(r"QFileDialog\.getExistingDirectory\(", "QFileDialog.getExistingDirectory()",
     "폴더 선택 창을 띄우고 고른 폴더 경로(문자열 하나)를 돌려줘요.")
rule(r"QFileDialog\.getExistingDirectoryUrl\(", "getExistingDirectoryUrl()",
     "폴더를 QUrl 형태로 돌려줘요 (file:///C:/...). 글자로 쓰려면 .toString() / .toLocalFile().")
rule(r"\bfilter\s*=", "filter=", "파일 종류 목록이에요. ;; 로 여러 개를 구분해요. 예: '텍스트(*.txt);;모든 파일(*.*)'")
rule(r"QMessageBox\.(information|warning|critical|about)\(", "QMessageBox.{0}()",
     "{0} 아이콘이 있는 알림 창을 띄우고, 사용자가 닫을 때까지 기다려요.",
     "간단한 안내·경고를 한 줄로 띄우는 정적 함수예요.")
rule(r"QMessageBox\.question\(", "QMessageBox.question()",
     "예/아니오를 묻는 창을 띄우고 눌린 버튼 값을 돌려줘요.",
     "돌려받은 값을 QMessageBox.Yes 와 비교해서 분기해요.")
rule(r"QInputDialog\.get(\w+)\(", "QInputDialog.get{0}()",
     "값을 입력받는 작은 창을 띄우고 (값, OK눌림여부) 를 돌려줘요.",
     "", "두 번째 값이 False면 취소예요 → if ok: 로 확인해요.")
rule(r"\.exec_?\(\)", ".exec_()",
     "창(대화상자/앱)을 '모달'로 실행해요. 닫힐 때까지 다음 줄로 넘어가지 않아요.",
     "대화상자는 결과(Accepted=1/Rejected=0)를 돌려줘서 OK/취소를 구분할 수 있어요.")
rule(r"\.accept\(\)", ".accept()", "대화상자를 'OK'로 닫아요 (exec_() 가 1을 돌려줌). 이벤트에선 '처리했음' 표시.")
rule(r"\.reject\(\)", ".reject()", "대화상자를 '취소'로 닫아요 (exec_() 가 0을 돌려줌).")

# --- timers, threads, events --------------------------------------------------
rule(r"QTimer\(", "QTimer()", "일정 시간마다 timeout 시그널을 보내는 타이머를 만들어요.",
     "while + sleep 을 쓰면 화면이 멈추니까, Qt에서는 타이머로 반복 작업을 해요.")
rule(r"\.start\((\d+)\)", ".start({0})", "타이머를 {0}ms(1000 = 1초) 간격으로 시작해요.")
rule(r"QThread", "QThread", "별도 스레드에서 오래 걸리는 작업을 돌려요.",
     "메인(GUI) 스레드에서 오래 걸리는 일을 하면 창이 '응답 없음'이 돼요.",
     "다른 스레드에서 위젯을 직접 바꾸면 안 돼요 → 시그널(emit)로 메인 스레드에 알려요.")
rule(r"def (mouse\w+Event|key\w+Event|closeEvent|paintEvent|resizeEvent|wheelEvent|\w+Event)\(self",
     "def {0}(self, e)",
     "{0} 이벤트가 생기면 Qt가 자동으로 부르는 메서드를 '재정의(override)'해요.",
     "부모 클래스의 같은 이름 메서드를 덮어써서, 마우스·키보드·닫기 같은 동작을 내 방식으로 처리해요.",
     "이름 철자가 하나라도 다르면 그냥 새 메서드가 돼서 호출되지 않아요.")
rule(r"QPainter\(", "QPainter()", "위젯 위에 선·도형·글자를 직접 그리는 붓이에요.", "",
     "paintEvent 안에서만 그려야 해요. 다시 그리려면 self.update() 를 불러요.")

# --- main block --------------------------------------------------------------------
rule(r"if __name__ == ['\"]__main__['\"]", "if __name__ == '__main__':",
     "이 파일을 직접 실행했을 때만 아래 코드를 실행해요.",
     "다른 파일에서 import 할 때는 창이 뜨지 않게 하려는 관용구예요.")
rule(r"QApplication\(sys\.argv\)", "QApplication(sys.argv)",
     "Qt 프로그램 전체를 관리하는 앱 객체를 만들어요. 프로그램마다 딱 하나만 있어야 해요.",
     "위젯을 만들기 전에 반드시 먼저 만들어야 해요.")
rule(r"^\s*(\w+)\s*=\s*(Form|MainWindow|Window|MyWindow|\w*Dialog|\w*Window)\(\)", "{0} = {1}()",
     "내가 만든 창 클래스 {1} 의 객체를 만들어요. 이때 __init__ 이 실행돼요.")
rule(r"^\s*\w+\.show\(\)", "창.show()", "창을 화면에 보여줘요.", "만들기만 하면 보이지 않아요. show() 해야 나타나요.")
rule(r"sys\.exit\(\w+\.exec_?\(\)\)", "sys.exit(app.exec_())",
     "이벤트 루프를 시작해 클릭·입력을 계속 기다리고, 창이 모두 닫히면 그 종료 코드로 프로그램을 끝내요.",
     "exec_() 가 없으면 창이 떴다가 바로 꺼져요.")
rule(r"^\s*if\s+(\w+)\s*:\s*$", "if {0}:",
     "{0} 에 값이 있을 때(빈 문자열·None·0·빈 리스트가 아닐 때)만 실행해요.",
     "대화상자를 취소하면 빈 값이 오니까, 그때는 아무것도 하지 않으려고 넣는 확인이에요.")


def _fmt(text, groups, line):
    if not text:
        return ""
    sig = ""
    m = re.search(r"\.(\w+)\.connect\(", line)
    if m:
        sig = SIGNAL_ARGS.get(m.group(1), "Designer 시그널 탭이나 문서에서 확인")
    try:
        return text.format(*groups, sig=sig)
    except (IndexError, KeyError):
        return text


def explain_line(line: str) -> list[Note]:
    code = line.split("#", 1)[0] if "#" in line and not re.search(r"['\"].*#.*['\"]", line) else line
    notes, seen = [], set()
    for rx, title, what, why, pit in R:
        m = rx.search(code)
        if not m:
            continue
        g = [x or "" for x in m.groups()]
        t = _fmt(title, g, code)
        if t in seen:
            continue
        # the generic "<signal> 시그널" rule only adds info when the signal is known
        if title == "{0} 시그널" and g[0] not in SIGNAL_ARGS:
            continue
        seen.add(t)
        notes.append(Note(t, _fmt(what, g, code), _fmt(why, g, code), _fmt(pit, g, code)))
    return notes


def context_of(lines: list[str], idx: int) -> str:
    """Where this line lives: enclosing def, and what triggers it (connect lines)."""
    for i in range(idx, -1, -1):
        m = re.match(r"^(\s*)def\s+(\w+)\(", lines[i])
        if m:
            fn = m.group(2)
            if fn == "__init__":
                return "__init__ 안: 창이 만들어질 때 한 번 실행돼요."
            callers = []
            for l in lines:
                c = re.search(rf"self\.(\w+)\.(\w+)\.connect\(self\.{re.escape(fn)}\)", l)
                if c:
                    callers.append(f"{c.group(1)}.{c.group(2)}")
            if callers:
                return f"{fn}() 안: {', '.join(callers)} 가 일어나면 실행돼요."
            return f"{fn}() 안"
        if re.match(r"^class\s", lines[i]) or (i < idx and re.match(r"^\S", lines[i])
                                                 and not lines[i].startswith(("#", "@"))):
            break
    return ""
