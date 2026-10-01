"""Turn a Python traceback into a plain-Korean hint + the user's code line."""
import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from .checker import qt_module_of

FRAME = re.compile(r'^\s*File "(.+?)", line (\d+)')


@dataclass
class Explained:
    error_line: str            # last line of the traceback, e.g. "AttributeError: ..."
    file: Path | None          # deepest frame inside the project folder
    line: int | None           # 1-based
    hint: str


def frames(text: str) -> list[tuple[Path, int]]:
    out = []
    for raw in text.splitlines():
        m = FRAME.match(raw)
        if m:
            out.append((Path(m.group(1)), int(m.group(2))))
    return out


def explain(stderr: str, folder: Path, ui_names=(), top_name: str | None = None) -> Explained | None:
    if "Traceback" not in stderr and "Error" not in stderr:
        return None
    lines = [l for l in stderr.strip().splitlines() if l.strip()]
    err = next((l.strip() for l in reversed(lines)
                if re.match(r"^[\w.]+(Error|Exception|Warning)\b", l.strip())), None)
    if err is None:
        return None
    mine = [(f, n) for f, n in frames(stderr) if _inside(f, folder)]
    file, line = mine[-1] if mine else (None, None)
    return Explained(err, file, line, _hint(err, set(ui_names), top_name))


def _inside(f: Path, folder: Path) -> bool:
    try:
        f.resolve().relative_to(folder.resolve())
        return True
    except (ValueError, OSError):
        return False


def _hint(err: str, ui_names: set, top_name: str | None) -> str:
    m = re.match(r"AttributeError: '(\w+)' object has no attribute '(\w+)'", err)
    if m:
        obj, attr = m.groups()
        if obj == "NoneType":
            return (f"None에서 .{attr} 를 찾았어요. 값이 None인 변수를 썼어요 — "
                    "함수가 return 없이 끝났거나, 아직 만들어지지 않은 객체일 수 있어요.")
        close = difflib.get_close_matches(attr, sorted(ui_names), n=1, cutoff=0.6)
        if close:
            return (f"'{attr}' 는 .ui에 없는 이름이에요. objectName 오타 같아요 → '{close[0]}'. "
                    "Designer의 objectName과 코드의 self.이름은 글자 하나까지 같아야 해요.")
        if ui_names:
            return (f"'{attr}' 가 없어요. ① .ui에 그 objectName이 정말 있는지 ② self.setupUi(self) "
                    "보다 먼저 쓰지 않았는지 ③ .ui를 고친 뒤 gui.py가 다시 만들어졌는지 확인해 보세요.")
        return f"'{obj}' 객체에는 '{attr}' 라는 속성/메서드가 없어요. 철자와 대소문자를 확인해 보세요."

    m = re.match(r"ModuleNotFoundError: No module named '([\w.]+)'", err)
    if m:
        mod = m.group(1)
        if mod.startswith("PyQt5"):
            return "PyQt5가 이 파이썬에 설치돼 있지 않아요 → pip install PyQt5"
        return (f"'{mod}.py' 가 없어요. Designer 파일이면 {mod}.ui 를 pyuic로 변환해야 생겨요 — "
                ".ui 파일 이름과 import 이름이 같은지 확인해 보세요.")

    m = re.match(r"ImportError: cannot import name '(\w+)' from '(\w+)'", err)
    if m:
        name, mod = m.groups()
        if name.startswith("Ui_"):
            want = f"Ui_{top_name}" if top_name else "Ui_ + 최상위 objectName"
            return (f"{mod}.py 안의 클래스 이름은 '{want}' 예요. pyuic는 Designer 최상위 위젯의 "
                    "objectName으로 클래스 이름을 정해요 (QDialog면 보통 Ui_Dialog).")
        return f"{mod} 모듈 안에 '{name}' 가 없어요. 이름을 확인해 보세요."

    m = re.match(r"NameError: name '(\w+)' is not defined", err)
    if m:
        name = m.group(1)
        mod = qt_module_of(name)
        if mod:
            return f"'{name}' 를 import하지 않았어요 → from {mod} import {name}  (또는 import *)"
        return f"'{name}' 가 정의되지 않았어요. 오타이거나, self. 를 빠뜨렸을 수 있어요."

    m = re.search(r"(\w+)\(\) takes (\d+) positional arguments? but (\d+) were given", err)
    if m:
        fn, want, got = m.groups()
        return (f"{fn}() 이 인자를 {int(got) - 1}개 받았는데, 받을 자리가 {int(want) - 1}개예요. "
                "시그널이 값을 넘겨서 생기는 일이 많아요 (예: clicked(bool) → checked). "
                f"def {fn}(self, value): 처럼 받을 자리를 만들거나, connect(lambda: self.{fn}()) 로 바꿔요.")
    m = re.search(r"(\w+)\(\) missing (\d+) required positional argument", err)
    if m:
        fn = m.group(1)
        return (f"{fn}() 이 기대한 인자를 못 받았어요. 시그널이 보내는 값보다 받는 자리가 더 많아요 — "
                f"시그널 탭에서 인자 개수를 확인하거나, 기본값을 주세요 (def {fn}(self, x=None)).")

    if "argument 1 has unexpected type" in err or "arguments did not match any overloaded call" in err:
        return ("Qt 함수에 다른 타입을 넣었어요. Qt는 타입을 엄격히 따져요 — "
                "예: setText()에는 str만 → setText(str(값)).")

    if err.startswith(("IndentationError", "TabError")):
        return "들여쓰기가 맞지 않아요. 탭과 스페이스를 섞지 말고 스페이스 4칸으로 통일하세요."
    if err.startswith("SyntaxError"):
        return "문법 오류예요. 표시된 줄과 바로 윗줄의 괄호·따옴표·콜론(:)을 확인해 보세요."

    if err.startswith("EOFError"):
        return ("input() 으로 키보드 입력을 기다렸는데, 도우미의 실행 창에서는 입력할 수 없어요. "
                "PyQt에서는 QLineEdit나 QInputDialog로 값을 받아요.")

    m = re.match(r"FileNotFoundError: .*?'(.+?)'", err)
    if m:
        return (f"'{m.group(1)}' 파일을 못 찾았어요. 상대 경로는 '실행한 위치' 기준이에요 — "
                "파일 이름과 폴더를 확인해 보세요.")
    return ""
