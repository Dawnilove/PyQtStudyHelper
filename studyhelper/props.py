"""Right-side panel: properties, signals, generated code, raw .ui XML of the selection."""
from html import escape

from PyQt5.QtCore import QMetaMethod, QObject, Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QHeaderView, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit,
                             QTabWidget, QTableWidget, QTableWidgetItem, QTextBrowser,
                             QVBoxLayout, QWidget)

from . import codeview

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
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        pl.addWidget(self.table, 3)
        pl.addWidget(QLabel("Main.py에서 쓰는 곳 (더블클릭하면 이동)"))
        self.uses = QListWidget()
        self.uses.setFont(MONO)
        self.uses.itemDoubleClicked.connect(lambda it: self.lineRequested.emit(it.data(Qt.UserRole)))
        pl.addWidget(self.uses, 2)
        self.tabs.addTab(page, "속성")

        self.signals = QListWidget()
        self.signals.setFont(MONO)
        self.tabs.addTab(self.signals, "시그널")

        self.code = QTextBrowser()
        self.tabs.addTab(self.code, "코드로 보기")

        self.xml = QPlainTextEdit()
        self.xml.setReadOnly(True)
        self.xml.setFont(MONO)
        self.xml.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.tabs.addTab(self.xml, ".ui 원본")

        self.clear()

    def clear(self):
        self.header.setText("<span style='color:#888'>Main.py의 <b>파란 변수</b>에 마우스를 올리거나, "
                            "미리보기·위젯 트리에서 위젯을 클릭해 보세요.</span>")
        self.table.setRowCount(0)
        self.uses.clear()
        self.signals.clear()
        self.code.clear()
        self.xml.clear()

    def show_node(self, model, node, obj, generated_code, editor):
        visible = obj is not None and getattr(obj, "isVisible", lambda: True)()
        note = "" if visible or node.kind == "action" else \
            " <span style='color:#c0392b'>(지금 화면에 보이지 않음)</span>"
        self.header.setText(
            f"<b style='font-size:13pt'>{escape(node.name)}</b> &nbsp; "
            f"<span style='color:#0b6bcb'>{escape(node.cls)}</span>{note}<br>"
            f"<span style='color:#555'>위치: {escape(node.position_text())}</span>")

        props = node.props
        self.table.setRowCount(len(props))
        for r, (k, v) in enumerate(props):
            self.table.setItem(r, 0, QTableWidgetItem(k))
            self.table.setItem(r, 1, QTableWidgetItem(v))

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
        if obj is not None:
            last = None
            for cls, sig in signals_of(obj):
                if cls != last:
                    head = QListWidgetItem(f"── {cls}")
                    head.setFlags(Qt.NoItemFlags)
                    self.signals.addItem(head)
                    last = cls
                self.signals.addItem(QListWidgetItem(f"  {sig}"))
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
