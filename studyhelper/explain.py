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
    "itemDoubleClicked": "항목 객체", "itemChanged": "항목 객체", "currentRowChanged": "int (새 행 번호)",
    "currentItemChanged": "(새 항목, 이전 항목)", "cellClicked": "(행, 열) int 두 개",
    "cellDoubleClicked": "(행, 열) int 두 개", "cellChanged": "(행, 열) int 두 개",
    "doubleClicked": "QModelIndex", "selectionChanged": "없음", "cursorPositionChanged": "없음 (QLineEdit은 이전·새 위치)",
    "finished": "int (대화상자 결과 코드) — QThread.finished는 없음", "started": "없음",
    "dateTimeChanged": "QDateTime", "selectedDateChanged": "없음", "idToggled": "(id, bool)",
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

rule(r"QTimer\.singleShot\(", "QTimer.singleShot()",
     "정한 시간(ms)이 지난 뒤 함수를 한 번만 실행해요.",
     "잠깐 기다렸다가 할 일(메시지 지우기 등)에 써요. time.sleep()과 달리 화면이 멈추지 않아요.")
rule(r"\.setInterval\(", ".setInterval()", "타이머가 timeout을 보내는 간격(ms)을 정해요.")
rule(r"\.stop\(\)", ".stop()", "타이머(또는 작업)를 멈춰요. 다시 start() 하면 이어서 돌아요.")
rule(r"\.isActive\(\)", ".isActive()", "타이머가 지금 돌고 있으면 True예요.",
     "시작/정지를 한 버튼으로 바꿀 때 지금 상태를 확인하려고 써요.")
rule(r"\.start\(\)", ".start()", "타이머나 스레드를 시작해요. 스레드면 별도 스레드에서 run() 이 실행돼요.", "",
     "스레드에서 run() 을 직접 부르면 그냥 메인 스레드에서 실행돼서 화면이 멈춰요. 꼭 start() 로 시작해요.")
rule(r"def run\(self", "def run(self)", "QThread를 상속했다면, start() 했을 때 별도 스레드에서 실행될 내용이에요.",
     "오래 걸리는 반복·다운로드를 여기 두면 창이 멈추지 않아요.",
     "여기서 위젯을 직접 바꾸지 말고 시그널.emit() 으로 결과를 보내요.")
rule(r"\.wait\(\)", ".wait()", "스레드가 끝날 때까지 기다려요.", "",
     "메인 스레드에서 부르면 그동안 창이 멈춰요. 보통 창을 닫을 때 정리용으로만 써요.")

# --- tables / lists ------------------------------------------------------------------
rule(r"\.set(RowCount|ColumnCount)\(", ".set{0}()", "표(QTableWidget)의 {0}(행/열 개수)를 정해요.",
     "", "개수를 먼저 늘려야 setItem() 으로 넣은 칸이 보여요.")
rule(r"QTableWidgetItem\(", "QTableWidgetItem()", "표의 칸 하나에 들어갈 항목을 만들어요.", "",
     "글자(str)만 받아요. 숫자는 str(값) 으로 바꿔 넣어요.")
rule(r"\.setItem\(", ".setItem(행, 열, 항목)", "표의 (행, 열) 칸에 항목을 넣어요. 번호는 0부터예요.")
rule(r"\.item\(\s*[\w.()]+\s*,\s*[\w.()]+\s*\)", ".item(행, 열)", "표의 (행, 열) 칸 항목을 가져와요.", "",
     "빈 칸이면 None 이 와요 → 바로 .text() 하면 AttributeError. if 항목: 으로 먼저 확인해요.")
rule(r"\.setHorizontalHeaderLabels\(", ".setHorizontalHeaderLabels()", "표 맨 위 열 제목들을 리스트로 정해요.")
rule(r"\.rowCount\(\)", ".rowCount()", "표의 행 개수를 돌려줘요.",
     "insertRow(rowCount()) 처럼 '맨 끝에 한 줄 추가'할 때 자주 써요.")
rule(r"\.insertRow\(", ".insertRow()", "표의 그 번호 자리에 빈 행을 끼워 넣어요.")
rule(r"\.removeRow\(", ".removeRow()", "표에서 그 번호의 행을 지워요.")
rule(r"\.currentRow\(\)", ".currentRow()", "선택된 행(리스트면 항목) 번호를 돌려줘요. 선택이 없으면 -1.", "",
     "-1 인 채로 removeRow/takeItem 하면 아무 일도 안 일어나거나 엉뚱한 줄이 지워져요. 먼저 확인해요.")
rule(r"\.resizeColumnsToContents\(\)", ".resizeColumnsToContents()", "열 너비를 내용에 맞게 맞춰요.")
rule(r"\.currentItem\(\)", ".currentItem()", "선택된 항목 객체를 돌려줘요. 글자는 .text() 로 꺼내요.", "",
     "선택이 없으면 None 이에요 → .text() 전에 if 항목: 으로 확인해요.")
rule(r"\.takeItem\(", ".takeItem()", "리스트에서 그 번호의 항목을 빼내요 (화면에서 사라져요).")
rule(r"\.count\(\)", ".count()", "항목 개수를 돌려줘요 (리스트·콤보박스·탭 등).")
rule(r"\.setCurrentIndex\(", ".setCurrentIndex()", "선택(콤보박스 항목, 탭, 쌓인 페이지)을 번호로 바꿔요.",
     "", "바뀌면 currentIndexChanged 시그널도 발생해요.")
rule(r"\.setCurrentText\(", ".setCurrentText()", "콤보박스에서 그 글자의 항목을 선택해요.")

# --- input widgets ------------------------------------------------------------------
rule(r"\.set(Range|Minimum|Maximum)\(", ".set{0}()", "스핀박스·슬라이더·진행바가 가질 수 있는 값의 범위를 정해요.",
     "", "범위 밖 값을 setValue() 하면 끝값으로 잘려요.")
rule(r"\.setSingleStep\(", ".setSingleStep()", "화살표/키 한 번에 바뀌는 크기를 정해요.")
rule(r"\.setPlaceholderText\(", ".setPlaceholderText()", "입력칸이 비었을 때 보이는 흐린 안내 글자예요.",
     "", "안내 글자는 text() 로 읽히지 않아요. 비어 있으면 '' 이에요.")
rule(r"\.setEchoMode\(", ".setEchoMode()", "입력한 글자를 어떻게 보일지 정해요. QLineEdit.Password 면 ●●● 로 가려요.")
rule(r"\.setReadOnly\(", ".setReadOnly()", "읽기만 되고 고칠 수 없게 해요 (선택·복사는 돼요).")
rule(r"\.setMaxLength\(", ".setMaxLength()", "입력할 수 있는 최대 글자 수를 정해요.")
rule(r"Q(Int|Double|RegularExpression|RegExp)Validator\(", "Q{0}Validator()",
     "입력칸에 들어갈 수 있는 값을 제한하는 검사기를 만들어요.",
     "숫자만 받게 해 두면 int() 변환 에러를 미리 막을 수 있어요.")
rule(r"\.setValidator\(", ".setValidator()", "입력칸에 검사기를 붙여요. 조건에 안 맞는 글자는 입력되지 않아요.")
rule(r"\.setFocus\(\)", ".setFocus()", "키보드 입력이 이 위젯으로 가게 해요 (커서가 깜박여요).")
rule(r"\.selectAll\(\)", ".selectAll()", "입력칸의 글자를 모두 선택해요. 다시 입력하기 편하게 할 때 써요.")
rule(r"\.strip\(\)", ".strip()", "문자열 앞뒤의 공백·줄바꿈을 없앤 새 문자열을 돌려줘요.",
     "스페이스만 입력한 경우도 '빈 값'으로 처리하려고 써요.")
rule(r"QButtonGroup\(", "QButtonGroup()", "라디오 버튼·체크박스를 하나의 묶음으로 관리해요.",
     "어느 버튼이 눌렸는지 buttonClicked 시그널 하나로 받을 수 있어요.")
rule(r"\.checked(Button|Id)\(\)", ".checked{0}()", "묶음에서 지금 체크된 버튼(또는 그 id)을 돌려줘요. 없으면 None/-1.")
rule(r"\.selectedDate\(\)", ".selectedDate()", "달력에서 고른 날짜를 QDate로 돌려줘요.")
rule(r"\.(date|time|dateTime)\(\)", ".{0}()", "날짜/시간 값을 꺼내요. QDateEdit 같은 위젯이면 Q{0} 객체가 오고, 글자는 .toString() 으로 바꿔요.")

# --- look ----------------------------------------------------------------------------
rule(r"\.setAlignment\(", ".setAlignment()", "글자를 왼쪽/가운데/오른쪽 등으로 정렬해요. 예: Qt.AlignCenter")
rule(r"QFont\(", "QFont()", "글꼴(이름, 크기, 굵기)을 만들어요. setFont() 로 위젯에 적용해요.")
rule(r"\.setFont\(", ".setFont()", "위젯의 글꼴을 바꿔요.")
rule(r"\.setToolTip\(", ".setToolTip()", "마우스를 올리면 뜨는 작은 설명 글자를 정해요.")
rule(r"QIcon\(", "QIcon()", "버튼·창에 쓸 아이콘을 그림 파일에서 만들어요.")
rule(r"\.setIcon\(", ".setIcon()", "버튼 등에 아이콘을 붙여요.")
rule(r"\.setWindowIcon\(", ".setWindowIcon()", "창 제목줄·작업 표시줄에 보일 아이콘을 정해요.")
rule(r"\.setFixedSize\(", ".setFixedSize()", "창/위젯 크기를 고정해요. 사용자가 크기를 바꿀 수 없어요.")
rule(r"\.setWordWrap\(", ".setWordWrap()", "글자가 길면 줄을 바꿔서 보여줘요 (QLabel).")
rule(r"\.scaled\(", ".scaled()", "그림을 원하는 크기로 바꾼 '새' 그림을 돌려줘요.",
     "Qt.KeepAspectRatio 를 주면 비율을 유지해요.", "원본은 그대로예요. 결과를 받아서 써야 해요.")
rule(r"QColor\(", "QColor()", "색을 만들어요. 이름('red'), '#ff0000', (빨, 초, 파) 숫자로 만들 수 있어요.")
rule(r"\.showMessage\(", ".showMessage()", "창 아래 상태 표시줄에 짧은 안내를 띄워요. 시간(ms)을 주면 그 뒤 사라져요.")
rule(r"\.addTab\(", ".addTab()", "탭 위젯에 새 탭(페이지)을 추가해요.")

# --- layouts made in code ----------------------------------------------------------
rule(r"Q(V|H)BoxLayout\(", "Q{0}BoxLayout()", "위젯을 세로(V) / 가로(H) 로 차례대로 늘어놓는 배치를 만들어요.",
     "좌표를 직접 주지 않아도 창 크기에 맞춰 자동으로 늘고 줄어요.")
rule(r"QGridLayout\(", "QGridLayout()", "위젯을 (행, 열) 칸에 놓는 표 모양 배치를 만들어요.")
rule(r"\.addWidget\(", ".addWidget()", "배치(레이아웃)에 위젯을 추가해요. 추가한 순서대로 놓여요.")
rule(r"\.addLayout\(", ".addLayout()", "배치 안에 다른 배치를 넣어요 (가로줄 여러 개를 세로로 쌓기 등).")
rule(r"\.setLayout\(", ".setLayout()", "위젯(창)에 배치를 적용해요. 이때부터 그 안 위젯이 자동 정렬돼요.", "",
     "QMainWindow에는 바로 못 써요 → 빈 QWidget에 setLayout 한 뒤 setCentralWidget 으로 넣어요.")
rule(r"\.setCentralWidget\(", ".setCentralWidget()", "QMainWindow의 가운데(메뉴·툴바·상태줄을 뺀 영역)에 위젯을 넣어요.")

# --- message box object ------------------------------------------------------------
rule(r"QMessageBox\(\s*(self)?\s*\)", "QMessageBox()", "알림 창을 객체로 직접 만들어요.",
     "아이콘·버튼·글자를 하나씩 정해서 꾸밀 때 써요. 마지막에 exec_() 로 띄워요.")
rule(r"\.setStandardButtons\(", ".setStandardButtons()", "알림 창에 나올 버튼(Yes | No 등)을 정해요.")
rule(r"==\s*QMessageBox\.(\w+)", "== QMessageBox.{0}", "사용자가 누른 버튼이 {0} 인지 비교해요.")

# --- date / time -------------------------------------------------------------------
rule(r"Q(Date|Time|DateTime)\.current(Date|Time|DateTime)\(\)", "Q{0}.current{1}()", "지금 날짜/시간을 가져와요.")
rule(r"\.toString\(\s*['\"]([^'\"]+)['\"]", ".toString('{0}')", "날짜/시간을 '{0}' 모양의 글자로 바꿔요.",
     "yyyy=년, MM=월, dd=일, hh=시, mm=분, ss=초. 대소문자에 따라 뜻이 달라요 (MM 월, mm 분).")
rule(r"datetime\.now\(\)", "datetime.now()", "파이썬 기본 모듈로 지금 날짜·시간을 가져와요.")

# --- python basics that show up in every lesson -----------------------------------
rule(r"\bint\(\s*self\.\w+\.text\(\)", "int(...text())", "입력칸의 글자를 정수로 바꿔요.", "",
     "빈칸이나 '12a' 같은 글자면 ValueError가 나요 → try/except 로 감싸거나 검사기를 붙여요.")
rule(r"\bfloat\(", "float()", "글자나 정수를 실수(소수점 숫자)로 바꿔요.", "", "숫자가 아닌 글자면 ValueError가 나요.")
rule(r"\bstr\(", "str()", "값을 글자(문자열)로 바꿔요. setText() 에 숫자를 넣을 때 필요해요.")
rule(r"^\s*try\s*:", "try:", "에러가 날 수도 있는 코드를 감싸요.",
     "에러가 나도 프로그램이 꺼지지 않고 except 쪽으로 가서 안내할 수 있어요.")
rule(r"^\s*except\s+(\w+)", "except {0}:", "위 try 안에서 {0} 에러가 나면 여기를 실행해요.",
     "ValueError(숫자 변환 실패), ZeroDivisionError(0으로 나눔), FileNotFoundError(파일 없음)가 자주 나와요.")
rule(r"^\s*except\s*:", "except:", "try 안에서 어떤 에러가 나든 여기를 실행해요.", "",
     "모든 에러를 숨겨서 진짜 버그를 놓치기 쉬워요. 가능하면 except ValueError: 처럼 종류를 적어요.")
rule(r"with open\(", "with open(...) as f:", "파일을 열고, 블록이 끝나면 자동으로 닫아요.",
     "close() 를 빼먹을 일이 없어서 파일은 보통 with 로 열어요.",
     "한글 파일은 encoding='utf-8' 을 꼭 넣어요. 안 넣으면 윈도우에서 글자가 깨지거나 에러가 나요.")
rule(r"\.read\(\)", ".read()", "파일 내용 전체를 한 번에 읽어 문자열로 돌려줘요.")
rule(r"\.readlines\(\)", ".readlines()", "파일을 줄 단위 리스트로 읽어요. 각 줄 끝에 \\n 이 붙어 있어요.")
rule(r"\.write\(", ".write()", "파일에 글자를 써요. 줄을 바꾸려면 \\n 을 직접 넣어요.")
rule(r"\bf['\"]", "f-문자열", "f'...' 안의 {변수} 자리에 값이 들어간 문자열을 만들어요.",
     "글자와 값을 + 로 이어 붙이지 않아도 돼서 읽기 쉬워요.")
rule(r"for\s+(\w+)\s+in\s+range\(", "for {0} in range()", "{0} 를 0부터 하나씩 늘리며 반복해요 (끝 숫자는 포함 안 함).")
rule(r"for\s+(\w+)\s+in\s+(?!range\()", "for {0} in ...", "목록의 값을 하나씩 {0} 에 담아 반복해요.")
rule(r"random\.(\w+)\(", "random.{0}()", "무작위 값을 만들어요 (randint=정수, choice=목록에서 하나, shuffle=섞기).")
rule(r"os\.path\.(\w+)\(", "os.path.{0}()", "파일 경로를 다루는 함수예요 (exists=있는지, join=이어 붙이기, basename=파일 이름).")
rule(r"\.key\(\)\s*==\s*Qt\.Key_(\w+)", "e.key() == Qt.Key_{0}", "누른 키가 {0} 키인지 확인해요 (keyPressEvent 안에서).")
rule(r"^\s*(\w+)\s*=\s*(\w*(?:Form|Dialog|Window|Dlg|dlg)\w*)\(self\)", "{0} = {1}(self)",
     "{1} 창(대화상자)을 만들면서 부모로 지금 창(self)을 넘겨요.",
     "부모가 있으면 부모 창 가운데에 뜨고, 부모 창이 닫힐 때 같이 정리돼요.")

rule(r"sys\.executable", "sys.executable", "지금 이 프로그램을 실행하고 있는 python.exe 의 경로예요.",
     "'python' 이라고 쓰는 대신 이걸 쓰면, PyQt5가 설치된 바로 그 파이썬으로 명령을 실행해요.")
rule(r"^\s*print\(", "print()", "실행 결과 창(콘솔)에 글자를 출력해요.",
     "화면(GUI)에는 안 보여요. 값이 제대로 들어왔는지 확인하는 디버깅용으로 많이 써요.")
rule(r"^\s*return\b", "return", "함수를 여기서 끝내고, 뒤에 적은 값을 부른 쪽에 돌려줘요 (값이 없으면 None).")
rule(r"^\s*from PyQt5\.(\w+) import (?!\*)(.+)", "from PyQt5.{0} import …",
     "PyQt5.{0} 모듈에서 {1} 만 골라서 가져와요.",
     "필요한 것만 적으면 어떤 이름이 어디서 왔는지 한눈에 보여요.")
rule(r"^\s*(?:from|import)\s+(?!PyQt5|sys\b)(\w+)", "import {0}",
     "{0} 모듈(다른 파일이나 라이브러리)을 가져와요.",
     "내가 만든 파일이면 같은 폴더에 {0}.py 가 있어야 해요.")
rule(r"@pyqtSlot\(", "@pyqtSlot()", "이 함수가 슬롯이라고 Qt에게 알려 주는 표시(데코레이터)예요.",
     "괄호 안 타입은 받을 시그널 값의 종류예요. 없어도 동작하지만, 스레드 간 연결에서 더 정확하고 빨라요.")
rule(r"^\s*def\s+(?!__init__|run\b|\w+Event\b)(\w+)\(self", "def {0}(self…)",
     "{0} 메서드(클래스 안 함수)를 정의해요.",
     "시그널에 connect(self.{0}) 로 연결하거나, 다른 곳에서 self.{0}() 로 불러 써요.")
rule(r"^\s*def\s+(data|headerData|rowCount|columnCount|flags|setData)\(self", "def {0}(self, …)",
     "모델(QAbstractTableModel 등)이 뷰에게 '{0}' 정보를 알려 주는 메서드를 재정의해요.",
     "QTableView 같은 뷰는 화면을 그릴 때 이 메서드를 계속 불러서 칸 값을 물어봐요.")
rule(r"Qt\.(DisplayRole|EditRole|ToolTipRole|TextAlignmentRole|BackgroundRole)", "Qt.{0}",
     "뷰가 지금 무엇을 물어보는지(표시할 글자, 편집 값, 툴팁…)를 나타내는 역할(role) 값이에요.",
     "", "모르는 role 이면 QVariant() / None 을 돌려줘야 빈 값으로 처리돼요.")
rule(r"\.setModel\(", ".setModel()", "뷰(QTableView, QListView)에 데이터를 가진 모델을 연결해요.",
     "데이터(모델)와 화면(뷰)을 나눠 두면, 모델만 바꿔도 화면이 따라 바뀌어요.")
rule(r"QListWidgetItem\(", "QListWidgetItem()", "리스트에 넣을 항목 하나를 만들어요. 글자·아이콘·체크 상태를 따로 정할 수 있어요.")
rule(r"QPixmap\.fromImage\(", "QPixmap.fromImage()", "QImage(계산·변환용 그림)를 화면 표시용 QPixmap으로 바꿔요.")
rule(r"\.quit\(\)", ".quit()", "이벤트 루프(앱 또는 스레드)를 끝내라고 알려요.")
rule(r"QApplication\.processEvents\(\)", "QApplication.processEvents()",
     "긴 반복문 중간에 쌓인 화면 갱신·클릭을 잠깐 처리해요.", "",
     "임시방편이에요. 오래 걸리는 일은 QThread나 QTimer로 나누는 게 좋아요.")
rule(r"self\.(\w+)\s*=\s*\[\s*\]", "self.{0} = []", "빈 리스트를 만들어 self.{0} 에 담아 둬요.",
     "self. 에 담으면 다른 메서드에서도 같은 리스트를 계속 쓸 수 있어요.")
rule(r"^\s*self\.(?!close\b|show\b|hide\b|update\b|accept\b|reject\b|setupUi\b)(\w+)\(\)\s*$", "self.{0}()",
     "이 클래스에 있는 {0}() 메서드를 불러서 실행해요.",
     "같은 일을 여러 곳에서 해야 할 때, 메서드로 만들어 두고 이렇게 불러 써요.")
rule(r"^\s*from PyQt5 import (uic)", "from PyQt5 import uic",
     ".ui 파일을 다루는 uic 모듈을 가져와요.", "uic.loadUi / uic.loadUiType 으로 .ui를 변환 없이 바로 쓸 수 있어요.")
rule(r"\w+\.open\(\)", ".open()", "대화상자를 띄우되, exec_() 와 달리 닫힐 때까지 기다리지 않고 다음 줄로 넘어가요.",
     "결과는 finished / accepted 시그널로 받아요.")
rule(r"QApplication\.exit\(", "QApplication.exit()", "앱의 이벤트 루프를 끝내서 프로그램을 종료해요.")
rule(r"\bnot in\b", "not in", "목록(리스트·문자열·딕셔너리)에 그 값이 없으면 True예요.")
rule(r"re\.(match|search|fullmatch|findall|sub)\(", "re.{0}()", "정규식(글자 패턴)으로 문자열을 검사하거나 찾아요.")

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
