"""Signal helper: plan the connect line + slot stub to insert into Main.py.

Pure text logic (no Qt widgets) so it can be tested on the exercise files.
"""
import ast
import keyword
import re
from dataclasses import dataclass

# C++ signal argument type -> (python type for overload index, parameter name)
ARG_NAMES = {
    "bool": ("bool", "checked"), "int": ("int", "value"), "double": ("float", "value"),
    "QString": ("str", "text"), "QModelIndex": (None, "index"), "QListWidgetItem*": (None, "item"),
    "QTreeWidgetItem*": (None, "item"), "QTableWidgetItem*": (None, "item"),
    "QAbstractButton*": (None, "button"), "QDate": (None, "date"), "QTime": (None, "time"),
    "QDateTime": (None, "datetime"), "QPoint": (None, "pos"), "QUrl": (None, "url"),
    "QAction*": (None, "action"), "QObject*": (None, "obj"),
}


@dataclass
class Plan:
    connect_line: str          # full line incl. indentation
    connect_after: int         # 0-based line index to insert after
    stub: str                  # method text (several lines) incl. indentation, '' if exists
    stub_after: int            # 0-based line index to insert after
    existing: int | None = None  # line of an identical connect that already exists
    note: str = ""


def parse_signature(sig: str) -> tuple[str, list[str]]:
    """'clicked(bool)' -> ('clicked', ['bool'])"""
    m = re.match(r"(\w+)\((.*)\)", sig)
    name, args = m.group(1), m.group(2).strip()
    return name, [a.strip() for a in args.split(",")] if args else []


def param_names(arg_types: list[str]) -> list[str]:
    out = []
    for t in arg_types:
        n = ARG_NAMES.get(t.replace("const ", "").replace("&", "").strip(), (None, "arg"))[1]
        while n in out:
            n += "2"
        out.append(n)
    return out


def overload_index(sig: str, all_sigs: list[str]) -> str:
    """'[str]' when the chosen overload isn't PyQt's default (the first declared one)."""
    name, args = parse_signature(sig)
    same = [parse_signature(s)[1] for s in all_sigs if parse_signature(s)[0] == name]
    if len(same) <= 1 or not args:
        return ""
    first = same[0]
    if args == first or args == first[:len(args)]:
        return ""
    pys = [ARG_NAMES.get(a, (None, None))[0] for a in args]
    if all(pys):
        return "[" + ", ".join(pys) + "]"
    return ""


def default_slot_name(widget: str, signal: str) -> str:
    # NOT on_<widget>_<signal>: setupUi() auto-connects that name too -> the slot would run twice
    return f"{widget}_{signal}"


def valid_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_]\w*", name)) and not keyword.iskeyword(name)


def _indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _form_class(lines: list[str]) -> tuple[int, int] | None:
    """(class line, last line of class body) of the class that calls self.setupUi(self)."""
    setup = next((i for i, l in enumerate(lines) if "self.setupUi(" in l), None)
    classes = [i for i, l in enumerate(lines) if re.match(r"^class\s+\w+", l)]
    if not classes:
        return None
    if setup is not None:
        cls = max((c for c in classes if c < setup), default=classes[0])
    else:
        cls = classes[0]
    end = cls
    for i in range(cls + 1, len(lines)):
        l = lines[i]
        if l.strip() and not l.startswith((" ", "\t")) and not l.lstrip().startswith("#"):
            break
        if l.strip():
            end = i
    return cls, end


def _layout_ast(src: str, lines: list[str], target_class: str | None = None):
    """(class end, method indent, anchor line, statement indent) using the parser.

    The anchor is the END line of the last top-level statement in __init__ that calls .connect(
    (so a connect spanning several lines, or one inside an if-block, isn't split or joined),
    else the setupUi(...) statement, else the last statement.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]

    def init_of(c):
        return next((f for f in c.body if isinstance(f, ast.FunctionDef) and f.name == "__init__"), None)

    cls = next((c for c in classes if c.name == target_class and init_of(c)), None) or \
        next((c for c in classes if init_of(c) and "setupUi(" in (ast.get_source_segment(src, init_of(c)) or "")),
             next((c for c in classes if init_of(c)), None))
    if cls is None:
        return None
    init = init_of(cls)
    seg = lambda n: ast.get_source_segment(src, n) or ""
    stmts = init.body
    anchor_stmt = next((s for s in reversed(stmts) if ".connect(" in seg(s)), None) \
        or next((s for s in stmts if "setupUi(" in seg(s)), None) or stmts[-1]
    first = lines[anchor_stmt.lineno - 1]
    stmt_indent = first[:len(first) - len(first.lstrip())]
    method_line = lines[init.lineno - 1]
    body_indent = method_line[:len(method_line) - len(method_line.lstrip())]
    return cls.end_lineno - 1, body_indent, anchor_stmt.end_lineno - 1, stmt_indent


def _layout_lines(lines: list[str]):
    """Fallback for files that don't parse yet: indentation-based."""
    rng = _form_class(lines)
    if rng is None:
        raise ValueError("Main.py에서 class 를 찾지 못했어요.")
    cls, cls_end = rng
    init = next((i for i in range(cls, cls_end + 1) if re.match(r"\s+def __init__\(", lines[i])), None)
    if init is None:
        raise ValueError("클래스 안에서 def __init__ 을 찾지 못했어요.")
    body_indent = _indent(lines[init])
    init_end = init
    for i in range(init + 1, cls_end + 1):
        l = lines[i]
        if l.strip() and len(_indent(l)) <= len(body_indent) and not l.lstrip().startswith("#"):
            break
        if l.strip():
            init_end = i
    anchor = None
    for i in range(init, init_end + 1):
        if ".connect(" in lines[i] and not lines[i].lstrip().startswith("#"):
            anchor = i
    if anchor is None:
        anchor = next((i for i in range(init, init_end + 1) if "self.setupUi(" in lines[i]), init_end)
    stmt_indent = _indent(lines[anchor]) if anchor != init else body_indent + "    "
    return cls_end, body_indent, anchor, stmt_indent


def plan_insert(src: str, widget: str, sig: str, all_sigs: list[str], slot: str,
                target_class: str | None = None) -> Plan:
    lines = src.split("\n")
    signal, args = parse_signature(sig)
    idx = overload_index(sig, all_sigs)
    params = param_names(args)

    # already connected?
    rx = re.compile(rf"self\.{re.escape(widget)}\.{re.escape(signal)}\b.*\.connect\(")
    for i, l in enumerate(lines):
        if rx.search(l) and not l.lstrip().startswith("#"):
            return Plan("", -1, "", -1, existing=i, note="이미 연결돼 있어요")

    layout = _layout_ast(src, lines, target_class) or _layout_lines(lines)
    cls_end, body_indent, anchor, stmt_indent = layout
    connect = f"{stmt_indent}self.{widget}.{signal}{idx}.connect(self.{slot})"

    note = ""
    if re.search(rf"^\s*def\s+{re.escape(slot)}\(", src, re.M):
        stub = ""
        note = f"함수 {slot}() 은 이미 있어서 연결 줄만 넣어요."
    else:
        sig_params = ", ".join(["self"] + params)
        what = f"{widget} 의 {signal} 시그널이 오면 실행돼요"
        doc_args = "".join(f"\n{body_indent}    # {p}: 시그널이 넘겨준 값 ({ARG_NAMES.get(t, (None,))[0] or t})"
                           for p, t in zip(params, args))
        stub = (f"\n{body_indent}def {slot}({sig_params}):\n"
                f"{body_indent}    # {what}{doc_args}\n"
                f"{body_indent}    print('{slot}'{''.join(', ' + p for p in params)})  # TODO: 할 일을 여기에\n")
    return Plan(connect, anchor, stub, cls_end, note=note)
