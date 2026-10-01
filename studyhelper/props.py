"""Right-side panel: properties, signals, generated code, raw .ui XML of the selection."""
from html import escape

from PyQt5.QtCore import QMetaMethod, QObject, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (QHeaderView, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit,
                             QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QTextBrowser,
                             QVBoxLayout, QWidget)

from . import codeview, notes
from .ui_model import editable_value

MONO = QFont("Consolas", 10)
MONO.setStyleHint(QFont.Monospace)


def signals_of(obj: QObject) -> list[tuple[str, str]]:
    """[(defining class, signature)] most specific class first, QObject excluded."""
    out = []
    mo = obj.metaObject()
    while mo is not None and mo.className() != "QObject":
        for i in range(mo.methodOffset(), mo.methodCount()):
            m = mo.method(i)
            if m.methodType() == QMetaMethod.Signal:
                out.append((mo.className(), bytes(m.methodSignature()).decode()))
        mo = mo.superClass()
    return out


class PropertyPanel(QWidget):
    lineRequested = pyqtSignal(int)          # 0-based block number in Main.py
    signalInsertRequested = pyqtSignal(str, str, list)   # widget, signature, all signatures
    propertyEdited = pyqtSignal(str, str, str)          # object name, property, new value
    noteRequested = pyqtSignal(str)                     # obsidian:// url

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.header = QLabel()
        self.header.setTextFormat(Qt.RichText)
        self.header.setWordWrap(True)
        self.header.setMargin(6)
        lay.addWidget(self.header)

        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        # 속성 tab: property table + uses in Main.py
        page = QWidget()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(4, 4, 4, 4)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["속성", "값"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        self.table.itemChanged.connect(self._on_item_changed)
        pl.addWidget(self.table, 3)
        hint = QLabel("<span style='color:#888'>흰 칸 값은 더블클릭해서 고칠 수 있어요 → .ui에 바로 저장</span>")
        pl.addWidget(hint)
        pl.addWidget(QLabel("Main.py에서 쓰는 곳 (더블클릭하면 이동)"))
        self.uses = QListWidget()
        self.uses.setFont(MONO)
        self.uses.itemDoubleClicked.connect(lambda it: self.lineRequested.emit(it.data(Qt.UserRole)))
        pl.addWidget(self.uses, 2)
        self.tabs.addTab(page, "속성")

        sp = QWidget()
        sl = QVBoxLayout(sp)
        sl.setContentsMargins(4, 4, 4, 4)
        self.signals = QListWidget()
        self.signals.setFont(MONO)
        self.signals.itemDoubleClicked.connect(lambda _: self._request_insert())
        sl.addWidget(self.signals, 1)
        self.b_insert = QPushButton("선택한 시그널 → Main.py에 연결 코드 넣기")
        self.b_insert.setToolTip("connect 줄과 슬롯 함수 틀을 넣어 줘요 (시그널을 더블클릭해도 돼요)")
        self.b_insert.clicked.connect(self._request_insert)
        sl.addWidget(self.b_insert)
        self.tabs.addTab(sp, "시그널")

        self.code = QTextBrowser()
        self.tabs.addTab(self.code, "코드로 보기")

        self.xml = QPlainTextEdit()
        self.xml.setReadOnly(True)
        self.xml.setFont(MONO)
        self.xml.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.tabs.addTab(self.xml, ".ui 원본")

        self.notes = QListWidget()
        self.notes.itemActivated.connect(
            lambda it: it.data(Qt.UserRole) and self.noteRequested.emit(it.data(Qt.UserRole)))
        self.tabs.addTab(self.notes, "내 노트")
        self.vault = None
        self._node = None
        self._all_sigs = []
        self._filling = False

        self.clear()

    def clear(self):
        self.header.setText("<span style='color:#888'>Main.py의 <b>파란 변수</b>에 마우스를 올리거나, "
                            "미리보기·위젯 트리에서 위젯을 클릭해 보세요.</span>")
        self.table.setRowCount(0)
        self.uses.clear()
        self.signals.clear()
        self.code.clear()
        self.xml.clear()
        if hasattr(self, "notes"):
            self.notes.clear()
            self._node = None

    def _request_insert(self):
        it = self.signals.currentItem()
        sig = it.data(Qt.UserRole) if it else None
        if self._node is None or not sig:
            self.b_insert.setText("먼저 위 목록에서 시그널을 하나 고르세요")
            return
        self.signalInsertRequested.emit(self._node.name, sig, self._all_sigs)

    def _on_item_changed(self, item):
        if self._filling or self._node is None or item.column() != 1:
            return
        prop = self.table.item(item.row(), 0).text()
        self.propertyEdited.emit(self._node.name, prop, item.text())

    def show_node(self, model, node, obj, generated_code, editor):
        visible = obj is not None and getattr(obj, "isVisible", lambda: True)()
        note = "" if visible or node.kind == "action" else \
            " <span style='color:#c0392b'>(지금 화면에 보이지 않음)</span>"
        self.header.setText(
            f"<b style='font-size:13pt'>{escape(node.name)}</b> &nbsp; "
            f"<span style='color:#0b6bcb'>{escape(node.cls)}</span>{note}<br>"
            f"<span style='color:#555'>위치: {escape(node.position_text())}</span>")

        self._node = node
        props = node.props
        self._filling = True
        self.table.setRowCount(len(props))
        for r, (k, v) in enumerate(props):
            key = QTableWidgetItem(k)
            key.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(r, 0, key)
            val = QTableWidgetItem(v)
            tag = None if k.startswith("[attr]") else editable_value(node.elem, k)
            if tag:
                val.setToolTip(f"더블클릭해서 고치면 .ui에 저장돼요 ({tag})")
            else:
                val.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                val.setBackground(QColor("#f2f2f2"))
                val.setToolTip("복잡한 속성이라 Designer에서 바꿔 주세요")
            self.table.setItem(r, 1, val)
        self._filling = False

        self.uses.clear()
        for b in editor.occurrences(node.name):
            text = editor.document().findBlockByNumber(b).text().strip()
            it = QListWidgetItem(f"{b + 1:>4}  {text}")
            it.setData(Qt.UserRole, b)
            self.uses.addItem(it)
        if self.uses.count() == 0:
            it = QListWidgetItem("(아직 Main.py에서 쓰지 않음)")
            it.setFlags(Qt.NoItemFlags)
            self.uses.addItem(it)

        self.signals.clear()
        self.b_insert.setText("선택한 시그널 → Main.py에 연결 코드 넣기")
        self._all_sigs = []
        if obj is not None:
            last = None
            sigs = signals_of(obj)
            self._all_sigs = [s for _, s in sigs]
            for cls, sig in sigs:
                if cls != last:
                    head = QListWidgetItem(f"── {cls}")
                    head.setFlags(Qt.NoItemFlags)
                    self.signals.addItem(head)
                    last = cls
                it = QListWidgetItem(f"  {sig}")
                it.setData(Qt.UserRole, sig)
                self.signals.addItem(it)
            if self.signals.count():
                tip = QListWidgetItem("  ※ 괄호 안 타입 = 슬롯 함수가 받게 되는 인자")
                tip.setFlags(Qt.NoItemFlags)
                self.signals.insertItem(0, tip)

        is_top = model.top is not None and node is model.top
        rows = codeview.lines_for(generated_code, node.name, is_top) if generated_code else []
        html = ["<div style='font-size:10pt'>",
                "<p style='color:#666'>pyuic가 gui.ui를 파이썬으로 바꿀 때 이 위젯에 대해 만드는 줄이에요.</p>"]
        for line, why in rows:
            html.append(f"<pre style='background:#f4f4f4;margin:6px 0 0 0;padding:4px;white-space:pre-wrap'>"
                        f"{escape(line)}</pre>")
            if why:
                html.append(f"<div style='color:#555;margin:2px 0 0 8px'>→ {escape(why)}</div>")
        if not rows:
            html.append("<p style='color:#888'>(생성되는 코드 없음)</p>")
        html.append("</div>")
        self.code.setHtml("".join(html))

        self.xml.setPlainText(model.snippet(node.name))

        self.notes.clear()
        hits = notes.search(self.vault, node.cls) if self.vault else []
        for h in hits:
            it = QListWidgetItem(f"{notes.label(self.vault, h)}   ({h.count}회)")
            it.setData(Qt.UserRole, notes.obsidian_url(self.vault, h))
            it.setToolTip(str(h.path))
            self.notes.addItem(it)
        if not hits:
            it = QListWidgetItem("(관련 노트 없음)" if self.vault else "(Obsidian 볼트를 찾지 못했어요)")
            it.setFlags(Qt.NoItemFlags)
            self.notes.addItem(it)
        else:
            self.notes.insertItem(0, QListWidgetItem(f"{node.cls} 가 나오는 내 강의노트 — 더블클릭하면 Obsidian에서 열려요"))
            self.notes.item(0).setFlags(Qt.NoItemFlags)
        self.tabs.setTabText(self.tabs.indexOf(self.notes), f"내 노트 ({len(hits)})" if hits else "내 노트")
