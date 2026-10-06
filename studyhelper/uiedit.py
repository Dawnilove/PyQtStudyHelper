"""미리보기 간단 편집: 위젯 추가·삭제·순서 바꾸기 — the .ui XML is changed directly, saved the way Designer does.

Only the simple, safe cases: widgets in a vertical / horizontal box layout, and containers without a layout
(widgets at fixed x/y). Grid / form layouts and special containers (tabs, stacked pages, scroll areas,
splitters) are left to Designer. Every function returns an error message (or None) instead of raising for
the student's mistakes.
"""
import keyword
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .ui_model import NAMED_TAGS, UiModel, _read, _write

BOX = ("QVBoxLayout", "QHBoxLayout")
CONTAINERS = ("QWidget", "QFrame", "QGroupBox")        # "안에 넣기" works for these
MAIN_WINDOW_BARS = ("QMenuBar", "QStatusBar", "QToolBar", "QDockWidget")
DESIGNER_ONLY = ("여기는 격자(Grid)·폼(Form) 레이아웃이거나 탭·스크롤 영역 같은 특별한 칸이라 도우미에서 바꿀 수 없어요. "
                 "Designer에서 바꿔 주세요 (Ctrl+D).")

# class, name prefix, Korean name, size when placed at fixed x/y, what the text box is for
CLASSES = [
    ("QPushButton", "btn", "버튼", (100, 28), "text"),
    ("QLabel", "lbl", "라벨", (120, 24), "text"),
    ("QLineEdit", "edt", "입력칸", (160, 26), "placeholder"),
    ("QCheckBox", "chk", "체크박스", (140, 24), "text"),
    ("QRadioButton", "rdo", "라디오 버튼", (140, 24), "text"),
    ("QComboBox", "cmb", "콤보박스", (140, 26), "items"),
    ("QSpinBox", "spn", "숫자 상자", (80, 26), None),
    ("QListWidget", "lst", "리스트", (200, 120), "items"),
    ("QTextEdit", "txt", "여러 줄 입력칸", (220, 100), "placeholder"),
    ("QSlider", "sld", "슬라이더", (160, 24), None),
    ("QProgressBar", "prg", "진행 막대", (160, 24), None),
]
BY_CLASS = {c[0]: c for c in CLASSES}


# ------------------------------------------------------------------ names
def name_problem(name: str, taken) -> str | None:
    if not name:
        return "objectName을 넣어 주세요."
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or keyword.iskeyword(name):
        return "영문자·숫자·_ 만 쓰고, 숫자로 시작하지 않게 해 주세요 (파이썬 이름 규칙)."
    if name in taken:
        return f"'{name}' 는 이미 있는 이름이에요."
    return None


def suggest_name(cls: str, taken) -> str:
    """btnNew, btnNew2, … — the first free one."""
    base = BY_CLASS[cls][1] + "New" if cls in BY_CLASS else "widgetNew"
    n, name = 1, base
    while name in taken:
        n += 1
        name = f"{base}{n}"
    return name


def _names(root) -> set:
    return {e.get("name") for e in root.iter() if e.tag in NAMED_TAGS + ("spacer",) and e.get("name")}


def taken_names(path) -> set:
    """Every name already used in the .ui (widgets, layouts, spacers, actions …)."""
    root, _ = _read(Path(path))
    return _names(root)


# ------------------------------------------------------------------ XML helpers
def _parents(root) -> dict:
    return {c: p for p in root.iter() for c in p}


def _named(root, name, tags=("widget", "layout")):
    return next((e for e in root.iter() if e.tag in tags and e.get("name") == name), None)


def _depth(elem, parents) -> int:
    d = 0
    while elem in parents:
        elem = parents[elem]
        d += 1
    return d


def _place(parent, index, elem, parents):
    """Insert `elem` as child number `index`, indented like Designer (one space per level)."""
    depth = _depth(parent, parents) + 1
    ind = "\n" + " " * depth
    ET.indent(elem, space=" ", level=depth)
    kids = list(parent)
    if not kids:
        parent.text = ind
        elem.tail = "\n" + " " * (depth - 1)
    elif index >= len(kids):
        elem.tail = kids[-1].tail
        kids[-1].tail = ind
    else:
        elem.tail = ind
    parent.insert(index, elem)


def _remove(parent, elem):
    kids = list(parent)
    i = kids.index(elem)
    if i == len(kids) - 1 and i > 0:
        kids[i - 1].tail = elem.tail              # the one before now closes the parent
    parent.remove(elem)
    if not len(parent):
        parent.text = None                        # <layout …/> like Designer


def _box_of(elem, parents):
    """(layout, item) when `elem` sits in a layout, else None."""
    item = parents.get(elem)
    if item is None or item.tag != "item":
        return None
    lay = parents.get(item)
    return (lay, item) if lay is not None and lay.tag == "layout" else None


def _end_index(lay) -> int:
    """Where "at the end" goes: before a trailing spacer (it keeps pushing things together), else last."""
    kids = list(lay)
    if kids and kids[-1].tag == "item" and kids[-1].find("spacer") is not None:
        return len(kids) - 1
    return len(kids)


def _rect(e):
    r = e.find("property[@name='geometry']/rect")
    if r is None:
        return None
    try:
        return tuple(int(r.findtext(k) or 0) for k in ("x", "y", "width", "height"))
    except ValueError:
        return None


def _overlap(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _central(root, elem):
    """A QMainWindow stands for its central widget."""
    if elem is root.find("widget") and elem.get("class") == "QMainWindow":
        return next((c for c in elem.findall("widget") if c.get("class") not in MAIN_WINDOW_BARS), None)
    return elem


def _is_central(root, elem, parents) -> bool:
    top = root.find("widget")
    return parents.get(elem) is top and top.get("class") == "QMainWindow" \
        and elem.get("class") not in MAIN_WINDOW_BARS


# ------------------------------------------------------------------ where a new widget can go
def _spots(root, near):
    """{key: spot} where key is before / after / inside, and a spot is
    ("layout", layout elem, child index, label) or ("free", parent widget elem, near elem or None, label)."""
    parents = _parents(root)
    elem = _named(root, near)
    if elem is None:
        return {}, f"{near} 를 .ui에서 찾지 못했어요."
    elem = _central(root, elem)
    if elem is None:
        return {}, "이 창에는 위젯을 넣을 칸(centralwidget)이 없어요."
    top = root.find("widget")
    name = elem.get("name", "")
    spots = {}
    if elem.tag == "layout":
        if elem.get("class") not in BOX:
            return {}, DESIGNER_ONLY
        spots["inside"] = ("layout", elem, _end_index(elem), f"{name} 안 맨 끝에")
        return spots, None
    box = _box_of(elem, parents)
    if box is not None:
        lay, item = box
        if lay.get("class") in BOX:
            i = list(lay).index(item)
            horiz = lay.get("class") == "QHBoxLayout"
            spots["before"] = ("layout", lay, i, f"{name} {'왼쪽' if horiz else '위'}에")
            spots["after"] = ("layout", lay, i + 1, f"{name} {'오른쪽' if horiz else '아래'}에")
    elif elem is not top and not _is_central(root, elem, parents):
        parent = parents.get(elem)
        if parent is not None and parent.tag == "widget" and parent.find("layout") is None \
                and _inside_ok(root, parent):
            spots["after"] = ("free", parent, elem, f"{name} 아래에")
    if _inside_ok(root, elem):
        lay = elem.find("layout")
        if lay is None:
            spots["inside"] = ("free", elem, None, f"{name} 안에")
        elif lay.get("class") in BOX:
            spots["inside"] = ("layout", lay, _end_index(lay), f"{name} 안 맨 {'오른쪽' if lay.get('class') == 'QHBoxLayout' else '아래'}에")
    if not spots:
        return {}, DESIGNER_ONLY
    return spots, None


def _inside_ok(root, elem) -> bool:
    if elem.tag != "widget":
        return False
    top = root.find("widget")
    if elem is top:
        return elem.get("class") in ("QWidget", "QDialog")
    return elem.get("class") in CONTAINERS


def insert_places(path, near) -> tuple[list, str | None]:
    """[(key, label)] the add dialog offers for `near` (a widget or layout name), or an error."""
    root, _ = _read(Path(path))
    spots, err = _spots(root, near)
    order = ["after", "before", "inside"] if "after" in spots else ["inside"]
    return [(k, spots[k][-1]) for k in order if k in spots], err


# ------------------------------------------------------------------ add
def _prop(parent, name, tag, value):
    p = ET.SubElement(parent, "property", {"name": name})
    ET.SubElement(p, tag).text = value
    return p


def new_widget(cls: str, name: str, text: str = "") -> ET.Element:
    w = ET.Element("widget", {"class": cls, "name": name})
    kind = BY_CLASS[cls][4] if cls in BY_CLASS else None
    text = text.strip()
    if kind == "text" and text:
        _prop(w, "text", "string", text)
    elif kind == "placeholder" and text:
        _prop(w, "placeholderText", "string", text)
    elif kind == "items":
        for t in (x.strip() for x in text.split(",")):
            if t:
                _prop(ET.SubElement(w, "item"), "text", "string", t)
    if cls == "QSlider":
        _prop(w, "orientation", "enum", "Qt::Horizontal")
    elif cls == "QProgressBar":
        _prop(w, "value", "number", "0")
    return w


def _free_geometry(parent, near, size):
    rects = [r for r in (_rect(c) for c in parent.findall("widget")) if r]
    w, h = size
    nr = _rect(near) if near is not None else None
    if nr:
        cand = (nr[0], nr[1] + nr[3] + 8, w, h)
        if not any(_overlap(cand, r) for r in rects):
            return cand
    x = nr[0] if nr else (min(r[0] for r in rects) if rects else 20)
    bottom = max((r[1] + r[3] for r in rects), default=10)
    return (x, bottom + 10, w, h)


def _grow_top(root, bottom, right):
    """A form without layouts: make the window big enough to show the new widget."""
    top = root.find("widget")
    r = top.find("property[@name='geometry']/rect")
    if r is None or r.find("height") is None or r.find("width") is None:
        return
    extra = 60 if top.get("class") == "QMainWindow" else 12        # menu + status bars
    try:
        if int(r.findtext("height")) < bottom + extra:
            r.find("height").text = str(bottom + extra)
        if int(r.findtext("width")) < right + 12:
            r.find("width").text = str(right + 12)
    except ValueError:
        pass


def _min_size(w, height, width, parents):
    """A container sized by a layout: ask for at least this much room (minimumSize)."""
    size = w.find("property[@name='minimumSize']/size")
    if size is None:
        p = ET.Element("property", {"name": "minimumSize"})
        size = ET.SubElement(p, "size")
        ET.SubElement(size, "width").text = "0"
        ET.SubElement(size, "height").text = "0"
        _place(w, 0, p, parents)
    for k, v in (("width", width), ("height", height)):
        e = size.find(k)
        try:
            if e is not None and int(e.text or 0) < v:
                e.text = str(v)
        except ValueError:
            pass


def _fit(root, parents, w, bottom, right):
    """Make every container from `w` up to the window big enough to show a widget placed at fixed x/y."""
    top = root.find("widget")
    while w is not None and w.tag == "widget":
        if w is top or _is_central(root, w, parents):
            _grow_top(root, bottom, right)
            return
        if _box_of(w, parents) is not None:                 # its size comes from a layout
            _min_size(w, bottom + 10, right + 10, parents)
            return
        r = _rect(w)
        if r is None:
            return
        x, y, ww, hh = r
        nw, nh = max(ww, right + 10), max(hh, bottom + 10)
        if (nw, nh) == (ww, hh):
            return
        rect = w.find("property[@name='geometry']/rect")
        rect.find("width").text, rect.find("height").text = str(nw), str(nh)
        bottom, right, w = y + nh, x + nw, parents.get(w)


def _stretch(lay, change):
    """Keep a box layout's stretch="0,1,0" (one factor per item, by position) in step with its items."""
    s = lay.get("stretch")
    if s is None:
        return
    vals = [v.strip() for v in s.split(",")]
    change(vals)
    if all(v in ("", "0") for v in vals):
        del lay.attrib["stretch"]
    else:
        lay.set("stretch", ",".join(vals))


def add_widget(path, near, where, cls, name, text="") -> str | None:
    path = Path(path)
    if cls not in BY_CLASS:
        return f"{cls} 는 여기서 추가할 수 없어요. Designer에서 추가해 주세요."
    root, crlf = _read(path)
    err = name_problem(name, _names(root))
    if err:
        return err
    spots, err = _spots(root, near)
    if err:
        return err
    if where not in spots:
        return "그 위치에는 넣을 수 없어요."
    parents = _parents(root)
    w = new_widget(cls, name, text)
    spot = spots[where]
    if spot[0] == "layout":
        _, lay, index, _label = spot
        at = sum(1 for c in list(lay)[:index] if c.tag == "item")
        _stretch(lay, lambda v: v.insert(at, "0") if at <= len(v) else None)
        item = ET.Element("item")
        item.append(w)
        _place(lay, index, item, parents)
    else:
        _, parent, near_elem, _label = spot
        x, y, gw, gh = _free_geometry(parent, near_elem, BY_CLASS[cls][3])
        geo = ET.Element("property", {"name": "geometry"})
        rect = ET.SubElement(geo, "rect")
        for k, v in (("x", x), ("y", y), ("width", gw), ("height", gh)):
            ET.SubElement(rect, k).text = str(v)
        w.insert(0, geo)
        kids = list(parent)
        last_widget = max((i for i, c in enumerate(kids) if c.tag == "widget"), default=None)
        last_prop = max((i for i, c in enumerate(kids) if c.tag in ("property", "attribute")), default=-1)
        _place(parent, (last_widget if last_widget is not None else last_prop) + 1, w, parents)
        _fit(root, parents, parent, y + gh, x + gw)
    _write(path, root, crlf)
    return None


# ------------------------------------------------------------------ delete
def why_not_delete(model: UiModel, name: str) -> str | None:
    """None when the helper may delete this node, else why not."""
    node = model.nodes.get(name)
    if node is None:
        return f"{name} 를 .ui에서 찾지 못했어요."
    if node.kind != "widget":
        return "레이아웃·액션·버튼 묶음은 Designer에서 지워 주세요."
    if node is model.top:
        return "최상위 창은 지울 수 없어요."
    if node.parent is model.top and model.top.cls == "QMainWindow" and node.cls not in MAIN_WINDOW_BARS:
        return f"{name} 은(는) QMainWindow의 가운데 칸이라 지울 수 없어요. 안에 있는 위젯을 지워 주세요."
    return None


def delete_widget(path, name) -> tuple[str | None, list]:
    """Remove a widget (and everything inside it) plus every reference to those names. Returns (error, names)."""
    path = Path(path)
    root, crlf = _read(path)
    parents = _parents(root)
    elem = _named(root, name, NAMED_TAGS)
    if elem is None:
        return f"{name} 를 .ui에서 찾지 못했어요.", []
    if elem.tag != "widget":
        return "레이아웃·액션·버튼 묶음은 Designer에서 지워 주세요.", []
    if elem is root.find("widget"):
        return "최상위 창은 지울 수 없어요.", []
    if _is_central(root, elem, parents):
        return f"{name} 은(는) QMainWindow의 가운데 칸이라 지울 수 없어요. 안에 있는 위젯을 지워 주세요.", []
    removed = [e.get("name") for e in elem.iter() if e.tag in NAMED_TAGS and e.get("name")]
    gone = set(removed)
    target = parents[elem] if parents[elem].tag == "item" else elem
    holder = parents[target]
    if target.tag == "item" and holder.get("class") in BOX:
        at = [c for c in holder if c.tag == "item"].index(target)
        _stretch(holder, lambda v: v.pop(at) if at < len(v) else None)
    _remove(holder, target)
    # references to the removed names
    for c in list(root.iter("connection")):
        if (c.findtext("sender") or "").strip() in gone or (c.findtext("receiver") or "").strip() in gone:
            _remove(parents[c], c)
    for tag in ("tabstop", "zorder"):
        for t in list(root.iter(tag)):
            if (t.text or "").strip() in gone:
                _remove(parents[t], t)
    for t in list(root.iter("tabstops")):
        if not len(t):
            _remove(parents[t], t)
    for a in list(root.iter("addaction")):
        if a.get("name") in gone:
            _remove(parents[a], a)
    for p in list(root.iter("property")):
        if p.get("name") == "buddy" and (p.findtext("cstring") or "").strip() in gone:
            _remove(parents[p], p)
    _write(path, root, crlf)
    return None, removed


# ------------------------------------------------------------------ reorder
def move_info(model: UiModel, name: str):
    """(can go back, can go forward, horizontal) for a node in a box layout, else None."""
    node = model.nodes.get(name)
    if node is None or node.item is None or node.layout is None or node.layout.cls not in BOX:
        return None
    items = [c for c in node.layout.elem if c.tag == "item"]
    if node.item not in items:
        return None
    i = items.index(node.item)
    return i > 0, i < len(items) - 1, node.layout.cls == "QHBoxLayout"


def move_widget(path, name, step: int) -> str | None:
    """Swap with the neighbour in the same box layout (step -1: up / left, +1: down / right)."""
    path = Path(path)
    root, crlf = _read(path)
    parents = _parents(root)
    elem = _named(root, name)
    if elem is None:
        return f"{name} 를 .ui에서 찾지 못했어요."
    box = _box_of(elem, parents)
    if box is None or box[0].get("class") not in BOX:
        return ("세로·가로 레이아웃(QVBoxLayout / QHBoxLayout) 안의 위젯만 순서를 바꿀 수 있어요. "
                "자리를 옮기려면 Designer에서 끌어서 옮겨 주세요 (Ctrl+D).")
    lay, item = box
    items = [c for c in lay if c.tag == "item"]
    j = items.index(item) + step
    if not 0 <= j < len(items):
        return "더 옮길 수 없어요 (이미 맨 " + ("앞" if step < 0 else "끝") + "이에요)."
    other = items[j]
    i = items.index(item)

    def swap(v):
        if max(i, j) < len(v):
            v[i], v[j] = v[j], v[i]
    _stretch(lay, swap)
    kids = list(lay)
    a, b = kids.index(item), kids.index(other)
    kids[a], kids[b] = kids[b], kids[a]
    item.tail, other.tail = other.tail, item.tail          # each place keeps its indentation
    for k in list(lay):
        lay.remove(k)
    lay.extend(kids)
    _write(path, root, crlf)
    return None
