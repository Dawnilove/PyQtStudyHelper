"""Find the .ui file a Python file uses (and the reverse)."""
import ast
import re
from pathlib import Path


def read_text(path) -> tuple[str, str, bool]:
    """(text, encoding, uses_crlf) — text always uses '\\n'."""
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            pass
    else:
        enc, text = "utf-8", data.decode("utf-8", errors="replace")
    crlf = "\r\n" in text
    return text.replace("\r\n", "\n"), enc, crlf


def _resolve(expr, consts):
    """Best-effort string value of an expression (constants, names, f-strings, +)."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.Name):
        return consts.get(expr.id)
    if isinstance(expr, ast.JoinedStr):
        parts = []
        for v in expr.values:
            s = _resolve(v.value if isinstance(v, ast.FormattedValue) else v, consts)
            if s is None:
                return None
            parts.append(s)
        return "".join(parts)
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        a, b = _resolve(expr.left, consts), _resolve(expr.right, consts)
        return a + b if a is not None and b is not None else None
    return None


def ui_candidates(py_path, include_folder=True) -> list[Path]:
    """Ordered .ui candidates for a Python file (existing files only).

    1) imported module name + '.ui'  (from gui import Ui_MainWindow -> gui.ui);
       that module is what actually runs, so it wins over strings
    2) '.ui' strings in the code (variables and f-strings resolved)
    3) any other .ui in the same folder
    """
    py = Path(py_path).resolve()
    folder = py.parent
    src = read_text(py)[0]
    found: list[Path] = []

    def add(rel):
        p = (folder / rel).resolve()
        if p.suffix.lower() == ".ui" and p.exists() and p not in found:
            found.append(p)

    try:
        tree = ast.parse(src)
    except SyntaxError:
        tree = None

    if tree is not None:
        consts = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) \
                    and isinstance(n.value.value, str):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        consts[t.id] = n.value.value
        imports, strings = [], []
        for n in ast.walk(tree):
            if isinstance(n, (ast.Constant, ast.JoinedStr, ast.BinOp)):
                s = _resolve(n, consts)
                if s and s.lower().endswith(".ui"):
                    strings.append(s)
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                imports.append((n.lineno, n.module))
            elif isinstance(n, ast.Import):
                imports += [(n.lineno, a.name) for a in n.names]
        for _, mod in sorted(imports):
            add(mod.replace(".", "/") + ".ui")
        for s in strings:
            add(s)
    else:
        for mod in re.findall(r"^\s*from\s+([\w.]+)\s+import", src, re.M):
            add(mod.replace(".", "/") + ".ui")
        for s in re.findall(r"""['"]([^'"\n]+\.ui)['"]""", src):
            add(s)

    if include_folder:
        for p in sorted(folder.glob("*.ui")):
            add(p.name)
    return found


def is_generated(py_path) -> bool:
    """True for files written by pyuic (gui.py etc.)."""
    head = read_text(py_path)[0][:400]
    return "generated from reading ui file" in head


def py_for_ui(ui_path) -> Path | None:
    """A Python file in the same folder that explicitly uses this .ui (Main.py first)."""
    ui = Path(ui_path).resolve()
    pys = sorted(ui.parent.glob("*.py"), key=lambda p: (p.stem.lower() != "main", p.name.lower()))
    for py in pys:
        try:
            if is_generated(py):
                continue
            if ui in ui_candidates(py, include_folder=False):
                return py
        except OSError:
            continue
    return None


def main_py_in(folder) -> Path | None:
    folder = Path(folder)
    for name in ("Main.py", "main.py"):
        if (folder / name).exists():
            return folder / name
    for ui in sorted(folder.glob("*.ui")):
        py = py_for_ui(ui)
        if py:
            return py
    return None


def import_mismatch(py_path) -> tuple[int, str] | None:
    """(0-based line, message) when pyuic converts one .ui but the code imports another module.

    e.g. GUI_FILE_NAME = 'gui_sol' (converts gui_sol.ui) but `from gui import Ui_MainWindow`.
    """
    py = Path(py_path).resolve()
    src = read_text(py)[0]
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    consts = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) \
                and isinstance(n.value.value, str):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = n.value.value
    converted = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Constant, ast.JoinedStr, ast.BinOp)):
            s = _resolve(n, consts)
            if s and s.lower().endswith(".ui"):
                converted.add(Path(s).stem)
    if not converted:
        return None
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and n.level == 0 \
                and (py.parent / f"{n.module}.ui").exists() and n.module not in converted:
            conv = ", ".join(sorted(f"{c}.ui" for c in converted))
            return (n.lineno - 1,
                    f"pyuic로 변환하는 건 {conv} 인데 import하는 건 '{n.module}' 예요 → "
                    f"{n.module}.ui 를 고쳐도 {n.module}.py 가 다시 만들어지지 않아요.")
    return None
