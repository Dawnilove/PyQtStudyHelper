"""Name checker: catches the classic PyQt beginner mistakes before running.

- self.<name> that is in no .ui, not defined in the file and not a Qt attribute (typo -> AttributeError)
- .connect(self.<slot>) whose slot function doesn't exist
- converting one .ui with pyuic but importing a different module
- syntax errors
- .connect(self.f()) — calling the slot instead of passing it
- a .ui class that never calls setupUi(), or uses its widgets before setupUi()
- a Qt subclass whose __init__ forgets super().__init__()
- a .ui widget used without self. (btnOk.clicked…)
"""
import ast
import difflib
import re
from dataclasses import dataclass

from PyQt5 import QtCore, QtGui, QtWidgets

QT_MODULES = (QtWidgets, QtGui, QtCore)
SELF_USE = re.compile(r"\bself\.(\w+)")
CONNECT = re.compile(r"\.connect\(\s*self\.(\w+)\s*\)")
CONNECT_CALL = re.compile(r"\.connect\(\s*self\.(\w+)\(([^()]*)\)\s*\)")


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


def _ui_form_names(tree) -> set:
    """Names that hold a Designer form class: `form_class = uic.loadUiType("x.ui")[0]` (and Ui_* imports)."""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and "loadUiType" in ast.dump(n.value):
            for t in n.targets:
                for e in ast.walk(t):
                    if isinstance(e, ast.Name):
                        out.add(e.id)
    return out


def _base_name(b) -> str:
    if isinstance(b, ast.Name):
        return b.id
    if isinstance(b, ast.Attribute):
        return b.attr
    return ""


def _calls(node, attr: str) -> list:
    """Calls like x.<attr>(...) / <attr>(...) inside node, in source order."""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if (isinstance(f, ast.Attribute) and f.attr == attr) or (isinstance(f, ast.Name) and f.id == attr):
                out.append(n)
    return sorted(out, key=lambda c: (c.lineno, c.col_offset))


def _class_issues(tree, ui_names) -> list[Issue]:
    """setupUi() missing or too late; super().__init__() missing."""
    issues = []
    forms = _ui_form_names(tree)
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        bases = [_base_name(b) for b in cls.bases]
        init = next((b for b in cls.body if isinstance(b, ast.FunctionDef) and b.name == "__init__"), None)
        qt_bases = [b for b in bases if b.startswith("Q") and qt_class(b) is not None]
        ui_base = next((b for b in bases if b.startswith("Ui_") or b in forms), None)
        line, col = cls.lineno - 1, cls.col_offset
        name_end = col + len("class ") + len(cls.name)

        if ui_base and qt_bases:
            setups = _calls(cls, "setupUi") + _calls(cls, "loadUi")
            if not setups:
                issues.append(Issue(line, col + 6, name_end, "error",
                                    f"{cls.name} 는 화면 설계({ui_base})를 상속하지만 self.setupUi(self) 를 부르지 않아요 "
                                    "→ 위젯이 만들어지지 않아서 self.위젯 을 쓰면 AttributeError가 나요. "
                                    "__init__ 안 super().__init__() 다음 줄에 넣어 주세요."))
            elif init is not None:
                first = next((c for c in setups if init.lineno <= c.lineno <= (init.end_lineno or c.lineno)), None)
                if first is not None:
                    for n in ast.walk(init):
                        if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self"
                                and n.attr in ui_names and (n.lineno, n.col_offset) < (first.lineno, first.col_offset)):
                            issues.append(Issue(n.lineno - 1, n.end_col_offset - len(n.attr), n.end_col_offset, "error",
                                                f"self.{n.attr} 를 setupUi() 보다 먼저 썼어요 → 이때는 아직 위젯이 "
                                                "없어서 AttributeError가 나요. setupUi(self) 아래로 옮겨 주세요."))

        if qt_bases and init is not None:
            supers = [c for c in _calls(init, "__init__")
                      if isinstance(c.func, ast.Attribute)
                      and ((isinstance(c.func.value, ast.Call) and _base_name(c.func.value.func) == "super")
                           or _base_name(c.func.value) in bases)]
            if not supers:
                issues.append(Issue(init.lineno - 1, init.col_offset + 4, init.col_offset + 12, "error",
                                    f"__init__ 에서 super().__init__() 를 부르지 않아요 → {qt_bases[0]} 가 준비되지 않아 "
                                    "'super-class __init__() ... was never called' 에러가 나요. 첫 줄에 넣어 주세요."))
    return issues


def _missing_self(tree, src_lines, ui_names, defined) -> list[Issue]:
    """`btnOk.clicked.connect(...)` where btnOk is a .ui widget and nothing local is called that."""
    local = set(defined)
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            local.add(n.id)
        elif isinstance(n, ast.arg):
            local.add(n.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            local |= {(a.asname or a.name).split(".")[0] for a in n.names}
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            local.add(n.name)
    issues = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and isinstance(n.value.ctx, ast.Load):
            name = n.value.id
            if name in ui_names and name not in local:
                ln, col = n.value.lineno - 1, n.value.col_offset
                if 0 <= ln < len(src_lines) and not _in_comment_or_string(src_lines[ln], col):
                    issues.append(Issue(ln, col, col + len(name), "error",
                                        f"'{name}' 앞에 self. 가 빠졌어요 → self.{name} "
                                        "(.ui 위젯은 self.이름 으로 써야 해요)"))
    return issues


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

    lines = src.split("\n")
    in_docs = set()                      # lines inside multi-line strings / docstrings (examples, not code)
    if tree is not None:
        issues += _class_issues(tree, set(ui_names))
        issues += _missing_self(tree, lines, set(ui_names), defined)
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.end_lineno != n.lineno:
                in_docs |= set(range(n.lineno - 1, n.end_lineno))

    for i, line in enumerate(lines):
        if i in in_docs:
            continue
        for m in CONNECT_CALL.finditer(line):
            if _in_comment_or_string(line, m.start()):
                continue
            slot, args = m.group(1), m.group(2).strip()
            if args:
                msg = (f"connect(self.{slot}({args})) 는 지금 바로 {slot}() 을 실행하고 그 결과를 연결해요. "
                       f"값을 넘기려면 connect(lambda: self.{slot}({args})) 로 써요.")
            else:
                msg = (f"connect(self.{slot}()) 처럼 괄호를 붙이면 지금 바로 실행돼요 → "
                       f"connect(self.{slot}) 로 함수 이름만 넘겨요.")
            issues.append(Issue(i, m.start(1), m.end(2) + 1, "error", msg))
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
