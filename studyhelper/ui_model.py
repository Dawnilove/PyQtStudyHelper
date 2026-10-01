"""Parse a Qt Designer .ui file into a simple tree of named nodes."""
import copy
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(eq=False)
class UiNode:
    name: str
    cls: str
    kind: str                       # 'widget' | 'layout' | 'action' | 'buttongroup'
    elem: ET.Element
    item: Optional[ET.Element]      # <item> wrapper when placed in a layout
    layout: Optional["UiNode"]      # layout that holds this node
    parent: Optional["UiNode"]      # tree parent (widget or layout)
    children: list = field(default_factory=list)

    @property
    def props(self) -> list:
        """(name, value) pairs of the node's own <property> elements."""
        out = [(p.get("name", ""), prop_value(p)) for p in self.elem.findall("property")]
        out += [(f"[attr] {p.get('name', '')}", prop_value(p)) for p in self.elem.findall("attribute")]
        return out

    @property
    def grid_pos(self) -> Optional[tuple]:
        """(row, col, rowspan, colspan) when in a grid/form layout."""
        if self.item is None or self.item.get("row") is None:
            return None
        return (int(self.item.get("row")), int(self.item.get("column", 0)),
                int(self.item.get("rowspan", 1)), int(self.item.get("colspan", 1)))

    def position_text(self) -> str:
        if self.kind == "action":
            return "메뉴/툴바에서 쓰는 QAction (화면 위치 없음)"
        if self.kind == "buttongroup":
            return "버튼 묶음 (화면 위치 없음, 속한 버튼은 attribute buttonGroup 으로 표시)"
        if self.layout is None:
            if self.parent is None:
                return "최상위 창"
            if self.elem.find("property[@name='geometry']") is not None:
                return f"{self.parent.name} 안 절대 위치 (레이아웃 없음)"
            return f"{self.parent.name} 안"
        pos = self.grid_pos
        if pos:
            r, c, rs, cs = pos
            span = "" if (rs, cs) == (1, 1) else f", {rs}행×{cs}열 차지"
            return f"{self.layout.name} ({self.layout.cls}) 의 {r}행 {c}열{span}"
        idx = self.layout.children.index(self)
        return f"{self.layout.name} ({self.layout.cls}) 의 {idx}번째"


def prop_value(p: ET.Element) -> str:
    if len(p) == 0:
        return p.text or ""
    v = p[0]
    if len(v) == 0:
        return v.text or ""
    return ", ".join(f"{c.tag}={c.text}" for c in v)


class UiModel:
    def __init__(self, path):
        self.path = Path(path)
        self.root_elem = ET.parse(self.path).getroot()
        self.nodes: dict[str, UiNode] = {}
        self.top: Optional[UiNode] = None
        self.actions: list[UiNode] = []
        top = self.root_elem.find("widget")
        if top is not None:
            self.top = self._widget(top, None, None, None)
        # Designer button groups: <buttongroups><buttongroup name="buttonGroup"/>
        for bg in self.root_elem.findall("buttongroups/buttongroup"):
            self.actions.append(self._add(UiNode(bg.get("name", ""), "QButtonGroup", "buttongroup",
                                                 bg, None, None, None)))

    def _add(self, node: UiNode) -> UiNode:
        if node.name:
            self.nodes[node.name] = node
        if node.parent is not None:
            node.parent.children.append(node)
        return node

    def _widget(self, elem, item, layout, parent) -> UiNode:
        node = self._add(UiNode(elem.get("name", ""), elem.get("class", ""), "widget",
                                elem, item, layout, parent))
        for child in elem:
            if child.tag == "widget":
                self._widget(child, None, None, node)
            elif child.tag == "layout":
                self._layout(child, None, None, node)
            elif child.tag == "action":
                self.actions.append(self._add(UiNode(child.get("name", ""), "QAction", "action",
                                                     child, None, None, None)))
        return node

    def _layout(self, elem, item, layout, parent) -> UiNode:
        node = self._add(UiNode(elem.get("name", ""), elem.get("class", ""), "layout",
                                elem, item, layout, parent))
        for it in elem.findall("item"):
            for child in it:
                if child.tag == "widget":
                    self._widget(child, it, node, node)
                elif child.tag == "layout":
                    self._layout(child, it, node, node)
        return node

    def snippet(self, name: str) -> str:
        """XML of the node (with its <item> wrapper), nested children collapsed."""
        node = self.nodes[name]
        src = node.item if node.item is not None else node.elem
        c = copy.deepcopy(src)
        target = c if node.item is None else c.find(node.elem.tag)
        nested = [x for x in list(target) if x.tag in ("widget", "layout", "item")]
        for x in nested:
            target.remove(x)
        if nested:
            target.append(ET.Comment(f" 자식 요소 {len(nested)}개 생략 "))
        ET.indent(c, space="  ")
        return ET.tostring(c, encoding="unicode")


EDITABLE_TAGS = ("string", "number", "double", "bool", "cstring")


def editable_value(elem: ET.Element, prop: str) -> Optional[str]:
    """Tag of a simple value we can edit in place (<string>, <number>…), else None."""
    p = elem.find(f"property[@name='{prop}']")
    if p is None or len(p) != 1 or len(p[0]) != 0 or p[0].tag not in EDITABLE_TAGS:
        return None
    return p[0].tag


def set_property(path, obj_name: str, prop: str, value: str) -> Optional[str]:
    """Write one simple property back into the .ui file. Returns an error message or None.

    Keeps the XML declaration, comments and the file's line endings.
    """
    path = Path(path)
    root, crlf = _read(path)
    elem = next((e for e in root.iter() if e.tag in ("widget", "layout", "action")
                 and e.get("name") == obj_name), None)
    if elem is None:
        return f"{obj_name} 를 .ui에서 찾지 못했어요."
    tag = editable_value(elem, prop)
    if tag is None:
        return f"{prop} 는 여기서 바꿀 수 없는 속성이에요. Designer에서 바꿔 주세요."
    v = value
    if tag == "number":
        try:
            v = str(int(value))
        except ValueError:
            return "정수(숫자)만 넣을 수 있어요."
    elif tag == "double":
        try:
            v = repr(float(value))
        except ValueError:
            return "숫자만 넣을 수 있어요."
    elif tag == "bool":
        if value.strip().lower() not in ("true", "false"):
            return "true 또는 false 만 넣을 수 있어요."
        v = value.strip().lower()
    elem.find(f"property[@name='{prop}']")[0].text = v
    _write(path, root, crlf)
    return None


def _read(path: Path):
    raw = path.read_bytes()
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.fromstring(raw, parser=parser), b"\r\n" in raw


def _write(path: Path, root, crlf: bool):
    """Keeps the XML declaration, comments, Designer's <x/> style and the line endings."""
    body = ET.tostring(root, encoding="unicode").replace(" />", "/>")
    text = '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"
    if crlf:
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


NAMED_TAGS = ("widget", "layout", "action", "buttongroup", "actiongroup")
REF_TEXT_TAGS = ("sender", "receiver", "tabstop", "zorder")


def rename_object(path, old: str, new: str) -> tuple[Optional[str], int]:
    """Rename an objectName and every reference to it in the .ui. Returns (error, changes)."""
    path = Path(path)
    root, crlf = _read(path)
    names = {e.get("name") for e in root.iter() if e.tag in NAMED_TAGS}
    if old not in names:
        return f"{old} 를 .ui에서 찾지 못했어요.", 0
    if new in names:
        return f"'{new}' 는 이미 다른 위젯 이름이에요.", 0
    n = 0
    for e in root.iter():
        if e.tag in NAMED_TAGS and e.get("name") == old:
            e.set("name", new)
            n += 1
        elif e.tag == "addaction" and e.get("name") == old:            # menus/toolbars using an action
            e.set("name", new)
            n += 1
        elif e.tag in REF_TEXT_TAGS and (e.text or "").strip() == old:  # signal/slot editor, tab order
            e.text = new
            n += 1
        elif e.tag == "cstring" and e.text == old:                       # e.g. QLabel buddy
            e.text = new
            n += 1
        elif e.tag == "attribute" and e.get("name") == "buttonGroup":    # a button's group membership
            s = e.find("string")
            if s is not None and s.text == old:
                s.text = new
                n += 1
    cls = root.find("class")          # <class>MainWindow</class>: pyuic names Ui_<this>
    if cls is not None and cls.text == old:
        cls.text = new
        n += 1
    _write(path, root, crlf)
    return None, n
