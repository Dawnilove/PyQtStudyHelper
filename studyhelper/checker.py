"""Name checker: catches the classic PyQt beginner mistakes before running.

- self.<name> that is in no .ui, not defined in the file and not a Qt attribute (typo -> AttributeError)
- .connect(self.<slot>) whose slot function doesn't exist
- converting one .ui with pyuic but importing a different module
- syntax errors
"""
import ast
import difflib
import re
from dataclasses import dataclass

from PyQt5 import QtCore, QtGui, QtWidgets

QT_MODULES = (QtWidgets, QtGui, QtCore)
SELF_USE = re.compile(r"\bself\.(\w+)")
CONNECT = re.compile(r"\.connect\(\s*self\.(\w+)\s*\)")


@dataclass
class Issue:
    line: int          # 0-based
    start: int         # column
    end: int
    level: str         # 'error' | 'warn'
    msg: str


def qt_class(name):
    for m in QT_MODULES:
        c = getattr(m, name, None)
        if isinstance(c, type):
            return c
    return None


def qt_module_of(name) -> str | None:
    for m in QT_MODULES:
        if hasattr(m, name):
            return m.__name__
    return None


def _defined_names(src: str, tree) -> tuple[set, set]:
    """(all names defined in the file, function names)"""
    funcs = set(re.findall(r"^\s*(?:async\s+)?def\s+(\w+)", src, re.M))
    names = set(funcs)
    names |= set(re.findall(r"\bself\.(\w+)\s*(?::[^=\n]*)?=(?!=)", src))      # self.x = ...
    names |= set(re.findall(r"^\s*class\s+(\w+)", src, re.M))
    if tree is not None:
        for n in ast.walk(tree):
            if isinstance(n, ast.ClassDef):
                for b in n.body:
                    if isinstance(b, ast.Assign):
                        names |= {t.id for t in b.targets if isinstance(t, ast.Name)}
            elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                for t in targets:
                    for e in ast.walk(t):
                        if isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name) \
                                and e.value.id == "self":
                            names.add(e.attr)
    return names, funcs


def _qt_attrs(src: str, top_classes) -> set:
    attrs = {"setupUi", "retranslateUi"}
    bases = set(re.findall(r"^\s*class\s+\w+\s*\(([^)]*)\)", src, re.M))
    candidates = {b.strip() for group in bases for b in group.split(",")} | set(top_classes)
    found = False
    for name in candidates:
        c = qt_class(name)
        if c is not None:
            attrs |= set(dir(c))
            found = True
    if not found:
        attrs |= set(dir(QtWidgets.QWidget))
    return attrs


def _in_comment_or_string(line: str, col: int) -> bool:
    quote = None
    for i, ch in enumerate(line[:col]):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            return True
    return quote is not None


def check(src: str, ui_names: set, top_classes=(), extra=()) -> list[Issue]:
    issues: list[Issue] = []
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        tree = None
        ln = max(0, (e.lineno or 1) - 1)
        issues.append(Issue(ln, max(0, (e.offset or 1) - 1), max(1, e.offset or 1), "error",
                            f"문법 오류: {e.msg}"))

    defined, funcs = _defined_names(src, tree)
    qt_attrs = _qt_attrs(src, top_classes)
    known = set(ui_names) | defined | qt_attrs
    pool = sorted(set(ui_names) | defined)

    for i, line in enumerate(src.split("\n")):
        for m in CONNECT.finditer(line):
            slot = m.group(1)
            if _in_comment_or_string(line, m.start()):
                continue
            auto = slot.startswith("on_") and "_" in slot[3:] and slot[3:].rsplit("_", 1)[0] in ui_names
            if auto:
                issues.append(Issue(i, m.start(1), m.end(1), "warn",
                                    f"'{slot}' 는 setupUi()가 이름을 보고 자동으로도 연결해요 → "
                                    "직접 connect까지 하면 두 번 실행돼요. 이름을 바꾸거나 이 줄을 지우세요."))
                continue
            if slot not in funcs and slot not in qt_attrs and slot not in ui_names:
                hint = difflib.get_close_matches(slot, sorted(funcs), n=1)
                more = f" 혹시 '{hint[0]}'?" if hint else " def로 만들어 주세요."
                issues.append(Issue(i, m.start(1), m.end(1), "warn",
                                    f"연결한 슬롯 함수 '{slot}' 가 이 파일에 없어요.{more}"))
        for m in SELF_USE.finditer(line):
            name = m.group(1)
            if name in known or _in_comment_or_string(line, m.start()):
                continue
            hint = difflib.get_close_matches(name, pool, n=1, cutoff=0.6)
            if hint and hint[0] in ui_names:
                msg = f"'{name}' 는 .ui에 없어요. objectName 오타? → '{hint[0]}'"
            elif hint:
                msg = f"'{name}' 가 어디에도 없어요. 혹시 '{hint[0]}'?"
            else:
                msg = f"'{name}' 는 .ui에도, 이 파일에도, Qt 클래스에도 없어요 → 실행하면 AttributeError"
            issues.append(Issue(i, m.start(1), m.end(1), "error", msg))

    issues += list(extra)
    issues.sort(key=lambda x: (x.line, x.start))
    # one issue per (line, column)
    seen, out = set(), []
    for x in issues:
        if (x.line, x.start) not in seen:
            seen.add((x.line, x.start))
            out.append(x)
    return out
