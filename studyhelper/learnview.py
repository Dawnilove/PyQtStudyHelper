"""학습 기록 보기: 공부한 날, 실행 횟수, 많이 본 위젯, 자주 만난 에러, 푼 과제·도전, 아직 안 본 위젯 추천."""
from datetime import date, timedelta
from html import escape

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout

from . import learnlog, tasks
from .theme import ThemedBrowser, chrome

# short meaning of the errors students meet most
ERROR_MEANINGS = {
    "AttributeError": "없는 이름(속성·메서드)을 썼어요 — objectName 오타, self. 빠뜨림, setupUi 전에 사용",
    "NameError": "만들지 않은 변수·함수 이름을 썼어요 (철자, import 확인)",
    "TypeError": "값의 종류나 함수에 넘긴 인자 개수가 맞지 않아요 (예: '3' + 4, connect(self.f()))",
    "ValueError": "값이 알맞지 않아요 (예: int('abc'))",
    "IndexError": "목록의 범위를 벗어난 번호를 썼어요",
    "KeyError": "사전(dict)에 없는 키를 찾았어요",
    "ModuleNotFoundError": "모듈(파일)을 찾지 못했어요 — 이름, 폴더, 설치 확인",
    "ImportError": "가져오려는 이름이 그 모듈에 없어요 (Ui_ 클래스 이름 확인)",
    "SyntaxError": "문법 오류 — 괄호·따옴표·콜론(:) 확인",
    "IndentationError": "들여쓰기가 맞지 않아요 (스페이스 4칸)",
    "TabError": "탭과 스페이스를 섞어 썼어요",
    "ZeroDivisionError": "0으로 나눴어요",
    "FileNotFoundError": "파일을 찾지 못했어요 — 경로와 실행 폴더 확인",
    "UnboundLocalError": "함수 안에서 값을 넣기 전에 변수를 썼어요",
    "RecursionError": "함수가 자기 자신을 끝없이 불렀어요",
    "RuntimeError": "실행 중 문제 — 이미 지워진 위젯을 쓰는 경우가 많아요",
}

# widgets worth meeting early, with what they are for
SUGGEST = [
    ("QPushButton", "누르는 버튼 — clicked"),
    ("QLabel", "글자·그림 보여 주기 — setText"),
    ("QLineEdit", "한 줄 입력 — text(), returnPressed"),
    ("QCheckBox", "켜기/끄기 — isChecked(), toggled"),
    ("QRadioButton", "여럿 중 하나 고르기"),
    ("QComboBox", "목록에서 고르기 — currentText()"),
    ("QSpinBox", "숫자 입력 — value(), valueChanged"),
    ("QListWidget", "목록 — addItem, currentRow()"),
    ("QTableWidget", "표 — setItem, cellClicked"),
    ("QTextEdit", "여러 줄 글 — toPlainText()"),
    ("QSlider", "끌어서 숫자 고르기 — valueChanged"),
    ("QProgressBar", "진행 막대 — setValue"),
    ("QGroupBox", "위젯 묶음 상자"),
    ("QTabWidget", "탭으로 화면 나누기"),
    ("QDateEdit", "날짜 고르기 — date()"),
]
BAR = 18                      # longest bar, in blocks


def streak(days: list[str], today: date | None = None) -> int:
    """Days in a row up to today (or yesterday, if today isn't studied yet)."""
    have = set(days)
    d = today or date.today()
    if d.isoformat() not in have:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in have:
        n += 1
        d -= timedelta(days=1)
    return n


def _section(title: str) -> str:
    return f"<h3 style='margin-top:16px;margin-bottom:4px'>{title}</h3>"


def summary_html(data: dict, today: date | None = None) -> str:
    try:
        return _summary(data, today)
    except Exception:                       # a hand-edited / broken file must not crash the window
        return ("<p>학습 기록 파일을 읽지 못했어요. <b>기록 지우기</b>로 새로 시작할 수 있어요.</p>"
                f"<p style='color:#888'>{escape(str(learnlog.path()))}</p>")


def _summary(data: dict, today: date | None) -> str:
    solved = data.get("tasks", {})
    widgets = data.get("widgets", {})
    errs = data.get("errors", {})
    chal = data.get("challenges", {})
    days = data.get("days", [])
    n_days, run = len(days), streak(days, today)
    h = ["<table cellspacing=0 cellpadding=6 width='100%'><tr>"]
    for big, small in ((f"{n_days}일", "공부한 날" + (f" · {run}일 연속" if run > 1 else "")),
                       (f"{data.get('runs', 0)}번", "실행(F5)"),
                       (f"{len(data.get('files', []))}개", "연 파일"),
                       (f"{sum(t.id in solved for t in tasks.TASKS)}/{len(tasks.TASKS)}", "푼 코드 과제"),
                       (f"{len(chal)}개", "완성한 도전")):
        h.append(f"<td align=center><span style='font-size:17pt;font-weight:600'>{big}</span><br>"
                 f"<span style='color:#888'>{small}</span></td>")
    h.append("</tr></table>")
    if not (n_days or widgets or errs):
        h.append("<p style='color:#888'>아직 기록이 없어요. 파일을 열고 위젯을 클릭하거나 F5로 실행해 보세요.</p>")

    h.append(_section("많이 본 위젯"))
    if widgets:
        top = sorted(widgets.items(), key=lambda kv: (-kv[1].get("count", 0), kv[0]))[:8]
        most = max(1, top[0][1].get("count", 0))
        h.append("<table cellspacing=0 cellpadding=2>")
        for cls, w in top:
            c = w.get("count", 0)
            bar = "▇" * max(1, round(BAR * c / most))
            h.append(f"<tr><td><code>{escape(cls)}</code>&nbsp;&nbsp;</td>"
                     f"<td><span style='color:#0b6bcb'>{bar}</span> {c}</td></tr>")
        h.append("</table>")
    else:
        h.append("<p style='color:#888'>미리보기나 위젯 트리에서 위젯을 클릭하면 여기에 쌓여요.</p>")

    h.append(_section("자주 만난 에러"))
    if errs:
        h.append("<table cellspacing=0 cellpadding=3>")
        for kind, e in sorted(errs.items(), key=lambda kv: (-kv[1].get("count", 0), kv[0]))[:8]:
            meaning = ERROR_MEANINGS.get(kind, "")
            h.append(f"<tr><td valign=top><b style='color:#c0392b'>{escape(kind)}</b></td>"
                     f"<td valign=top>{e.get('count', 0)}번</td>"
                     f"<td valign=top>{escape(meaning)}"
                     f"<br><span style='color:#888'>마지막: {escape(e.get('last', ''))}</span></td></tr>")
        h.append("</table>")
    else:
        h.append("<p style='color:#888'>아직 에러로 끝난 실행이 없어요.</p>")

    h.append(_section("코드 과제"))
    h.append("<table cellspacing=0 cellpadding=2>")
    for i, t in enumerate(tasks.TASKS, 1):
        if t.id in solved:
            h.append(f"<tr><td style='color:#2b8a3e'>✓ {i}. {escape(t.title)}</td>"
                     f"<td style='color:#888'>&nbsp;&nbsp;{escape(solved[t.id])}</td></tr>")
        else:
            h.append(f"<tr><td style='color:#888'>&nbsp;&nbsp; {i}. {escape(t.title)}</td><td></td></tr>")
    h.append("</table>")

    if chal:
        h.append(_section("완성한 도전"))
        h.append("<ul style='margin-top:0'>" + "".join(
            f"<li>{escape(name)} <span style='color:#888'>{escape(when)}</span></li>"
            for name, when in sorted(chal.items(), key=lambda kv: kv[1])) + "</ul>")

    todo = [(c, why) for c, why in SUGGEST if c not in widgets][:5]
    if todo:
        h.append(_section("다음에 만나 볼 위젯"))
        h.append("<ul style='margin-top:0'>" + "".join(
            f"<li><code>{c}</code> <span style='color:#888'>— {escape(why)}</span></li>" for c, why in todo)
                 + "</ul>")
    h.append(f"<p style='color:#888;font-size:9pt'>기록은 이 PC에만 저장돼요: {escape(str(learnlog.path()))}</p>")
    return "".join(h)


class LearnLogDialog(QDialog):
    tasksRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        chrome(self)
        self.setWindowTitle("학습 기록")
        self.resize(640, 680)
        lay = QVBoxLayout(self)
        self.view = ThemedBrowser()
        self.view.setOpenExternalLinks(False)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)       # long lines wrap instead
        lay.addWidget(self.view, 1)
        row = QHBoxLayout()
        b_tasks = QPushButton("코드 과제 열기")
        b_tasks.setObjectName("primary")
        b_tasks.clicked.connect(lambda: self.tasksRequested.emit())
        b_clear = QPushButton("기록 지우기…")
        b_clear.clicked.connect(self.clear)
        b_close = QPushButton("닫기")
        b_close.clicked.connect(self.accept)
        row.addWidget(b_tasks)
        row.addStretch(1)
        row.addWidget(b_clear)
        row.addWidget(b_close)
        lay.addLayout(row)
        self.refresh()

    def refresh(self):
        self.view.setHtml(summary_html(learnlog.load()))

    def clear(self):
        if QMessageBox.question(self, "학습 기록", "학습 기록을 모두 지울까요? (되돌릴 수 없어요)",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        learnlog.clear()
        self.refresh()
