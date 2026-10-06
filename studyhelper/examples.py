"""위젯별 자주 쓰는 코드 예제 + Qt 문서 주소. {w} = the widget's objectName."""
from PyQt5 import QtWidgets

EXAMPLES = {
    "QPushButton": [
        ("눌렀을 때 함수 실행", "self.{w}.clicked.connect(self.on_{w})\n\ndef on_{w}(self):\n    print('{w} 눌림')"),
        ("버튼 글자 바꾸기", "self.{w}.setText('확인')"),
        ("잠깐 못 누르게 하기", "self.{w}.setEnabled(False)   # 다시 켜기: setEnabled(True)"),
    ],
    "QAbstractButton": [                                  # QCheckBox, QRadioButton, QToolButton …
        ("체크됐는지 확인", "if self.{w}.isChecked():\n    print('켜짐')"),
        ("켜고 끌 때마다 실행", "self.{w}.toggled.connect(self.on_{w}_toggled)\n\n"
                           "def on_{w}_toggled(self, checked):\n    print('켜짐' if checked else '꺼짐')"),
        ("코드로 체크하기", "self.{w}.setChecked(True)"),
    ],
    "QLabel": [
        ("글자 바꾸기", "self.{w}.setText('안녕하세요')"),
        ("숫자 보여주기 (str로 바꿔서)", "self.{w}.setText(str(count))\nself.{w}.setText(f'{{count}}개')"),
        ("그림 보여주기", "from PyQt5.QtGui import QPixmap\n\nself.{w}.setPixmap(QPixmap('cat.png'))\n"
                     "self.{w}.setScaledContents(True)   # 라벨 크기에 맞추기"),
        ("가운데 정렬", "from PyQt5.QtCore import Qt\n\nself.{w}.setAlignment(Qt.AlignCenter)"),
    ],
    "QLineEdit": [
        ("입력한 글자 읽기", "text = self.{w}.text().strip()\nif not text:\n    return   # 비어 있으면 아무것도 안 함"),
        ("숫자로 읽기 (잘못 입력해도 안 꺼지게)", "try:\n    n = int(self.{w}.text())\nexcept ValueError:\n"
                                         "    QMessageBox.warning(self, '입력 오류', '숫자를 입력하세요')\n    return"),
        ("Enter를 누르면 실행", "self.{w}.returnPressed.connect(self.on_{w}_enter)"),
        ("지우기 / 안내 글자", "self.{w}.clear()\nself.{w}.setPlaceholderText('이름을 입력하세요')"),
        ("비밀번호처럼 가리기", "self.{w}.setEchoMode(QLineEdit.Password)"),
    ],
    "QTextEdit": [
        ("전체 글자 읽기", "text = self.{w}.toPlainText()"),
        ("글자 넣기 / 한 줄 덧붙이기", "self.{w}.setPlainText('처음 내용')\nself.{w}.append('새 줄')"),
    ],
    "QPlainTextEdit": [
        ("전체 글자 읽기", "text = self.{w}.toPlainText()"),
        ("글자 넣기 / 한 줄 덧붙이기", "self.{w}.setPlainText('처음 내용')\nself.{w}.appendPlainText('새 줄')"),
    ],
    "QComboBox": [
        ("선택한 글자 / 번호", "text = self.{w}.currentText()\nindex = self.{w}.currentIndex()   # 0부터"),
        ("항목 넣기", "self.{w}.addItems(['사과', '배', '포도'])"),
        ("선택이 바뀌면 실행", "self.{w}.currentIndexChanged.connect(self.on_{w}_changed)\n\n"
                          "def on_{w}_changed(self, index):\n    print(self.{w}.currentText())"),
    ],
    "QAbstractSpinBox": [                                 # QSpinBox, QDoubleSpinBox
        ("값 읽기 / 바꾸기", "n = self.{w}.value()\nself.{w}.setValue(10)"),
        ("범위 정하기", "self.{w}.setRange(0, 100)"),
        ("값이 바뀌면 실행", "self.{w}.valueChanged.connect(self.on_{w}_changed)\n\n"
                        "def on_{w}_changed(self, value):\n    print(value)"),
    ],
    "QAbstractSlider": [                                  # QSlider, QDial, QScrollBar
        ("값 읽기 / 바꾸기", "n = self.{w}.value()\nself.{w}.setValue(50)"),
        ("범위 정하기", "self.{w}.setRange(0, 100)"),
        ("움직이면 실행", "self.{w}.valueChanged.connect(self.on_{w}_changed)\n\n"
                      "def on_{w}_changed(self, value):\n    print(value)"),
    ],
    "QProgressBar": [
        ("진행률 보여주기", "self.{w}.setRange(0, 100)\nself.{w}.setValue(30)"),
    ],
    "QLCDNumber": [
        ("숫자 보여주기", "self.{w}.display(123)"),
    ],
    "QListWidget": [
        ("항목 추가", "self.{w}.addItem('새 항목')"),
        ("선택한 항목 글자", "item = self.{w}.currentItem()\nif item:          # 선택이 없으면 None\n"
                         "    print(item.text())"),
        ("선택한 항목 지우기", "row = self.{w}.currentRow()\nif row >= 0:\n    self.{w}.takeItem(row)"),
        ("항목을 클릭하면 실행", "self.{w}.itemClicked.connect(self.on_{w}_clicked)\n\n"
                            "def on_{w}_clicked(self, item):\n    print(item.text())"),
    ],
    "QTableWidget": [
        ("표 크기와 제목", "self.{w}.setRowCount(3)\nself.{w}.setColumnCount(2)\n"
                       "self.{w}.setHorizontalHeaderLabels(['이름', '점수'])"),
        ("칸에 값 넣기 (글자만 돼요)", "self.{w}.setItem(0, 1, QTableWidgetItem(str(95)))"),
        ("칸 값 읽기", "item = self.{w}.item(0, 1)\nif item:          # 빈 칸이면 None\n    print(item.text())"),
        ("맨 아래에 한 줄 추가", "row = self.{w}.rowCount()\nself.{w}.insertRow(row)"),
        ("칸을 클릭하면 실행", "self.{w}.cellClicked.connect(self.on_{w}_cell)\n\n"
                          "def on_{w}_cell(self, row, col):\n    print(row, col)"),
    ],
    "QDateTimeEdit": [                                    # QDateEdit, QTimeEdit
        ("날짜 읽기 (글자로)", "text = self.{w}.date().toString('yyyy-MM-dd')"),
        ("오늘 날짜로", "from PyQt5.QtCore import QDate\n\nself.{w}.setDate(QDate.currentDate())"),
    ],
    "QCalendarWidget": [
        ("고른 날짜", "d = self.{w}.selectedDate()\nprint(d.toString('yyyy-MM-dd'))"),
        ("날짜를 고르면 실행", "self.{w}.selectionChanged.connect(self.on_{w}_changed)"),
    ],
    "QTabWidget": [
        ("지금 탭 번호 / 탭 바꾸기", "i = self.{w}.currentIndex()\nself.{w}.setCurrentIndex(1)"),
        ("탭이 바뀌면 실행", "self.{w}.currentChanged.connect(self.on_{w}_changed)"),
    ],
    "QStackedWidget": [
        ("보이는 페이지 바꾸기", "self.{w}.setCurrentIndex(1)"),
    ],
    "QGroupBox": [
        ("제목 바꾸기", "self.{w}.setTitle('설정')"),
    ],
    "QDialogButtonBox": [
        ("OK / 취소 연결 (대화상자)", "self.{w}.accepted.connect(self.accept)\nself.{w}.rejected.connect(self.reject)"),
    ],
    "QMainWindow": [
        ("창 제목 / 상태 표시줄", "self.setWindowTitle('내 프로그램')\nself.statusBar().showMessage('저장했어요', 3000)"),
    ],
    "QDialog": [
        ("대화상자 띄우고 결과 받기", "dlg = MyDialog(self)\nif dlg.exec_():          # OK면 1, 취소면 0\n"
                                "    print('확인을 눌렀어요')"),
    ],
    "QAction": [
        ("메뉴를 고르면 실행", "self.{w}.triggered.connect(self.on_{w})"),
    ],
    "QWidget": [
        ("보이기 / 숨기기", "self.{w}.setVisible(False)"),
        ("마우스를 올리면 설명", "self.{w}.setToolTip('여기에 이름을 입력해요')"),
    ],
}


def _qt_class(name):
    c = getattr(QtWidgets, name, None)
    return c if isinstance(c, type) else None


def examples_for(cls_name: str, widget: str, is_top=False) -> list[tuple[str, str]]:
    """Examples for the closest known class in the widget's Qt class hierarchy (+ the general QWidget ones)."""
    c = _qt_class(cls_name)
    chain = [k.__name__ for k in c.__mro__] if c else [cls_name]
    out = []
    for name in chain:
        if name in EXAMPLES and name != "QWidget":
            out = EXAMPLES[name]
            break
    out = out + ([] if is_top else EXAMPLES["QWidget"])
    w = widget
    return [(t, code.format(w=w)) for t, code in out]


def doc_url(cls_name: str) -> str | None:
    """Qt 5 documentation page of a Qt class."""
    return f"https://doc.qt.io/qt-5/{cls_name.lower()}.html" if cls_name.startswith("Q") else None
