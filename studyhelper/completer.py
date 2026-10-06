"""Autocomplete candidates for the Main.py editor.

Sources, best first: .ui widget names after ``self.``, Qt members after ``self.<widget>.``,
jedi (PyQt5 names, locals, imports), and — when jedi is missing — keywords and words of the file.
Pure logic: no Qt event loop, so the editor can run it on a worker thread.
"""
import importlib
import keyword
import re
from dataclasses import dataclass
from functools import lru_cache

MIN_PREFIX = 2                      # letters typed before the popup opens by itself
MAX_ITEMS = 100
_QT_MODULES = ("QtWidgets", "QtGui", "QtCore")

_WORD_END = re.compile(r"\w*$")
_SELF_ATTR = re.compile(r"\bself\.\w*$")
_SELF_WIDGET_MEMBER = re.compile(r"\bself\.(\w+)\.\w*$")
_QT_ENUM = re.compile(r"\bQt\.\w*$")                  # Qt.AlignCenter, QtCore.Qt.Horizontal ...
_WORD = re.compile(r"[A-Za-z_]\w*")

_JEDI_KINDS = {"module": "모듈", "class": "클래스", "function": "함수", "instance": "변수",
               "statement": "변수", "param": "인자", "property": "속성", "keyword": "키워드"}


@dataclass(frozen=True)
class Item:
    name: str
    kind: str


def _in_string_or_comment(before: str) -> bool:
    """True if the end of `before` (one line, up to the cursor) is inside a string or a # comment."""
    quote, i = None, 0
    while i < len(before):
        ch = before[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            return True
        i += 1
    return quote is not None


@lru_cache(maxsize=None)
def qt_members(cls_name: str) -> tuple:
    """Signals first, then methods, of the PyQt5 class called `cls_name` (empty if there is none)."""
    from PyQt5 import QtCore
    for mod_name in _QT_MODULES:
        cls = getattr(importlib.import_module(f"PyQt5.{mod_name}"), cls_name, None)
        if isinstance(cls, type):
            break
    else:
        return ()
    signals, methods = [], []
    for name in dir(cls):
        if name.startswith("_"):
            continue
        attr = getattr(cls, name, None)
        if isinstance(attr, QtCore.pyqtSignal):
            signals.append(Item(name, "시그널"))
        elif callable(attr) and not isinstance(attr, type):
            methods.append(Item(name, "메서드"))
    return tuple(signals + methods)


@lru_cache(maxsize=None)
def qt_constants() -> tuple:
    """Enum constants of ``Qt`` (AlignCenter, ...). PyQt5 5.15.11 stubs hide them from jedi, so read them at runtime."""
    from PyQt5 import QtCore
    return tuple(Item(n, "상수") for n in dir(QtCore.Qt)
                 if not n.startswith("_") and not callable(getattr(QtCore.Qt, n, None)))


class Completer:
    def __init__(self, use_jedi: bool = True):
        self._jedi = None
        if use_jedi:
            try:
                import jedi
                self._jedi = jedi
            except ImportError:
                pass
        self.widgets: dict[str, str] = {}          # .ui object name -> Qt class name

    def set_widgets(self, widgets: dict[str, str]):
        self.widgets = dict(widgets)               # swapped as a whole: safe to read from another thread

    def warmup(self):
        """jedi needs a few seconds to read the PyQt5 stubs the first time; do that ahead of typing."""
        if not self._jedi:
            return
        src = "from PyQt5 import QtWidgets\nQtWidgets.QLabel().setT"
        try:
            self._jedi.preload_module(*(f"PyQt5.{m}" for m in _QT_MODULES))
            self._jedi.Script(src).complete(2, len("QtWidgets.QLabel().setT"))
        except Exception:
            pass

    def complete(self, source: str, line: int, col: int, force: bool = False):
        """Candidates for the cursor at (line, col), both 0-based. Returns (items, length of the typed prefix)."""
        lines = source.split("\n")
        before = (lines[line] if line < len(lines) else "")[:col]
        if _in_string_or_comment(before):
            return [], 0
        prefix = _WORD_END.search(before).group()
        after_dot = before[:len(before) - len(prefix)].endswith(".")
        if not force and len(prefix) < MIN_PREFIX and not after_dot:
            return [], 0

        items: list[Item] = []
        member = _SELF_WIDGET_MEMBER.search(before)
        if member and member.group(1) in self.widgets:
            items += self._filter(qt_members(self.widgets[member.group(1)]), prefix)
        elif _SELF_ATTR.search(before):
            items += self._filter((Item(n, "위젯") for n in sorted(self.widgets)), prefix)
        elif _QT_ENUM.search(before):
            items += self._filter(qt_constants(), prefix)
        if not items:
            if self._jedi:
                items += self._jedi_items(source, line, col, prefix)
            elif not after_dot:
                items += self._plain_items(source, line, col, prefix)

        seen, out = set(), []
        for it in items:
            if it.name not in seen and it.name != prefix:
                seen.add(it.name)
                out.append(it)
        return out[:MAX_ITEMS], len(prefix)

    @staticmethod
    def _filter(items, prefix):
        low = prefix.lower()
        return [i for i in items if i.name.lower().startswith(low)]

    def _jedi_items(self, source, line, col, prefix):
        try:
            found = self._jedi.Script(source).complete(line + 1, col)
        except Exception:                          # half-typed code can trip jedi; just offer nothing
            return []
        return [Item(c.name, _JEDI_KINDS.get(c.type, "변수")) for c in found
                if prefix.startswith("_") or not c.name.startswith("_")]

    def _plain_items(self, source, line, col, prefix):
        offset = sum(len(l) + 1 for l in source.split("\n")[:line]) + col
        rest = source[:offset - len(prefix)] + source[offset:]        # the word being typed is not a candidate
        found = [Item(k, "키워드") for k in keyword.kwlist]
        found += [Item(w, "단어") for w in sorted(set(_WORD.findall(rest)))]
        return self._filter(found, prefix)
