"""'코드로 보기': the pyuic-generated lines for one widget, with plain explanations."""
import io
import re

from PyQt5 import uic


def generate(ui_path) -> str:
    buf = io.StringIO()
    uic.compileUi(str(ui_path), buf)
    return buf.getvalue()


def _explain(line: str) -> str:
    m = re.match(r"self\.(\w+) = QtWidgets\.(\w+)\((.*)\)$", line)
    if m:
        name, cls, parent = m.groups()
        if cls.endswith("Layout"):
            where = f"{parent} 에 바로 설치돼요" if parent else "다른 레이아웃 안에 넣을 거라 부모가 없어요"
            return f"{cls} 레이아웃을 만들어요. {where}."
        if not parent:
            return f"{cls} 객체를 만들어요."
        return f"{cls} 객체를 만들어요. 괄호 안 {parent} 가 부모예요 → 부모 안에 그려지고, 부모가 사라질 때 함께 정리돼요."
    m = re.search(r"\.setObjectName\(\"(\w+)\"\)", line)
    if m:
        return f"objectName 지정. Main.py에서 self.{m.group(1)} 로 부르는 이름이 바로 이것이에요."
    m = re.search(r"(\w+)\.addWidget\(self\.\w+, (\d+), (\d+), (\d+), (\d+)\)", line)
    if m:
        lay, r, c, rs, cs = m.groups()
        return f"{lay} 격자의 {r}행 {c}열에 놓고, {rs}행×{cs}열 크기를 차지해요."
    m = re.search(r"(\w+)\.(addWidget|addLayout)\(self\.\w+\)", line)
    if m:
        what = "위젯" if m.group(2) == "addWidget" else "레이아웃(중첩)"
        return f"{m.group(1)} 에 {what}을 순서대로 추가해요. 박스 레이아웃은 넣은 순서가 곧 배치 순서예요."
    m = re.search(r"(\w+)\.setWidget\((\d+), QtWidgets\.QFormLayout\.(\w+)Role", line)
    if m:
        role = {"Label": "왼쪽(라벨) 칸", "Field": "오른쪽(입력) 칸", "Spanning": "양쪽 칸 전체"}.get(m.group(3), m.group(3))
        return f"폼 레이아웃 {m.group(1)} 의 {m.group(2)}행 {role}에 놓아요."
    m = re.search(r"\.setText\(_translate\(\"\w+\", \"(.*)\"\)\)", line)
    if m:
        return "화면에 보일 글자. .ui의 text 속성이 retranslateUi()에서 이렇게 들어가요."
    m = re.search(r"\.setGeometry\(QtCore\.QRect\((\d+), (\d+), (\d+), (\d+)\)\)", line)
    if m:
        x, y, w, h = m.groups()
        return f"레이아웃 없이 절대 위치 (x={x}, y={y}), 크기 {w}×{h}. 창 크기가 바뀌어도 따라 움직이지 않아요."
    if ".setCentralWidget(" in line:
        return "QMainWindow의 가운데 영역으로 지정해요."
    m = re.search(r"\.connect\(", line)
    if m:
        return "Designer의 시그널/슬롯 편집기에서 연결한 내용이에요."
    m = re.search(r"\.(set\w+)\(", line)
    if m:
        return f".ui에서 바꾼 속성을 {m.group(1)}() 로 설정해요."
    m = re.search(r"\.(add\w+)\(", line)
    if m:
        return f"{m.group(1)}() 로 다른 객체에 추가해요."
    return ""


def lines_for(code: str, name: str, is_top: bool = False) -> list[tuple[str, str]]:
    """[(code_line, explanation)] that mention `name` in the generated code."""
    n = re.escape(name)
    pat = re.compile(rf"\bself\.{n}\b" + (rf"|^\s*{n}\." if is_top else ""))
    out = []
    for raw in code.splitlines():
        if pat.search(raw):
            line = raw.strip()
            out.append((line, _explain(line)))
    return out
