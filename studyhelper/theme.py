"""밝은 / 어두운 테마. One place for every colour the app picks itself (the rest follows the Qt palette).

Two style sheets:
- app_stylesheet(): set on the whole app. Only rules that can't touch the student's .ui preview
  (our own objectNames, menus, tooltips, splitter handles).
- chrome_stylesheet(): the look of buttons, inputs, tabs, lists, scroll bars … It is set only on the parts
  of the window that are ours (chrome(widget)), never on an ancestor of a .ui preview — so the preview
  keeps looking exactly like Qt Designer shows it.
"""
import re
import weakref

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QLabel, QTextBrowser

# Text colours written into rich text / list items for the light theme -> readable on a dark background.
# (Chip text such as #5c3c00 sits on its own light background, so it is deliberately not here.)
DARK_FG = {
    "#888": "#9aa0a8", "#888888": "#9aa0a8", "#777": "#a0a6ae", "#666": "#aab0b8", "#555": "#b0b6be",
    "#555555": "#b0b6be", "#202020": "#e6e6e6",
    "#2b6e2b": "#8bc98b", "#2b8a3e": "#69db7c", "#c0392b": "#ff8787", "#c92a2a": "#ff8787",
    "#e03131": "#ff6b6b", "#b35c00": "#ffa94d", "#e8890c": "#ffa94d", "#0b6bcb": "#4dabf7",
    "#6f42c1": "#b197fc",
}
_FG = re.compile(r"(?<![\w-])(color\s*:\s*)(#[0-9a-fA-F]{3,6})\b")

LIGHT = {
    # code editor
    "kw": "#0033b3", "self": "#94558d", "str": "#067d17", "comment": "#8c8c8c", "num": "#1750eb",
    "widget": "#0b6bcb",
    "cur_line": "#eef4ff", "flash": "#d3f9d8", "err_line": "#ffe0e0", "mark_line": "#fff4c2", "mark_word": "#ffd666",
    "gutter_bg": "#ffffff", "gutter_fg": "#a3a9b1", "gutter_mark": "#b8860b",
    # side panels / html
    "pre_bg": "#f3f5f8", "muted": "#6a737d", "text": "#1f2328", "unused": "#a0a6ad", "readonly_cell": "#f3f5f8",
    # surfaces
    "window": "#f3f4f6", "base": "#ffffff", "border": "#e1e4e8", "border_strong": "#d0d7de",
    "accent": "#2f6fd0", "accent_hover": "#255db3", "accent_soft": "#dce8fb", "on_accent": "#ffffff",
    "hover": "#e9edf2", "button": "#ffffff", "disabled": "#a0a6ad",
    "scroll": "#c9ced6", "scroll_hover": "#a9b0ba",
    "title_fg": "#57606a", "tips_bg": "#fff8e1", "tips_border": "#f0dca0",
    "icon": "#3b4249", "run": "#2f9e44", "stop": "#e03131",
}
DARK = {
    "kw": "#6fa8ff", "self": "#c792ea", "str": "#8bc98b", "comment": "#7a8088", "num": "#82aaff",
    "widget": "#4da3ff",
    "cur_line": "#232f40", "flash": "#1f4a2a", "err_line": "#4a2326", "mark_line": "#4a4220", "mark_word": "#8a6d1a",
    "gutter_bg": "#181a1d", "gutter_fg": "#5f666e", "gutter_mark": "#e0b341",
    "pre_bg": "#24272b", "muted": "#9aa0a8", "text": "#e6e6e6", "unused": "#6f757d", "readonly_cell": "#24272b",
    "window": "#1f2124", "base": "#181a1d", "border": "#30343a", "border_strong": "#40454d",
    "accent": "#4d8fe6", "accent_hover": "#6aa2ec", "accent_soft": "#24395a", "on_accent": "#ffffff",
    "hover": "#2a2e34", "button": "#26292e", "disabled": "#6a6f76",
    "scroll": "#3d424a", "scroll_hover": "#555b64",
    "title_fg": "#9aa0a8", "tips_bg": "#33301f", "tips_border": "#4d4628",
    "icon": "#d5d9de", "run": "#51cf66", "stop": "#ff6b6b",
}

T = dict(LIGHT)          # the colours in use right now
dark = False
_chromed = {}             # id -> weakref of the widgets that carry chrome_stylesheet()


def set_dark(on: bool):
    global dark
    dark = bool(on)
    T.clear()
    T.update(DARK if dark else LIGHT)


def fg(color: str) -> str:
    """A text colour for the current theme (light colours pass through unchanged)."""
    return DARK_FG.get(color.lower(), color) if dark else color


def html(text: str) -> str:
    """Rich text with its `color:#…` values made readable in the current theme."""
    if not dark or not text or "color" not in text:
        return text
    return _FG.sub(lambda m: m.group(1) + DARK_FG.get(m.group(2).lower(), m.group(2)), text)


class ThemedLabel(QLabel):
    """QLabel that keeps its rich text readable in both themes (and can re-colour itself on a switch)."""

    def __init__(self, *args):
        self._raw = ""
        if args and isinstance(args[0], str):
            self._raw = args[0]
            args = (html(args[0]),) + args[1:]
        super().__init__(*args)

    def setText(self, text):
        self._raw = text
        super().setText(html(text))

    def retheme(self):
        super().setText(html(self._raw))


class ThemedBrowser(QTextBrowser):
    """QTextBrowser whose setHtml() follows the theme."""
    _raw = None

    def setHtml(self, text):
        self._raw = text
        super().setHtml(html(text))

    def setMarkdown(self, text):
        self._raw = None                         # markdown carries no colours of its own
        super().setMarkdown(text)

    def retheme(self):
        if self._raw is not None:
            super().setHtml(html(self._raw))


def retheme_all(root):
    """After a theme switch: re-colour every themed label / browser under `root`."""
    for w in root.findChildren(ThemedLabel) + root.findChildren(ThemedBrowser):
        w.retheme()


def palette(on: bool) -> QPalette:
    t = DARK if on else LIGHT
    c = QColor
    p = QPalette()
    p.setColor(QPalette.Window, c(t["window"]))
    p.setColor(QPalette.WindowText, c(t["text"]))
    p.setColor(QPalette.Base, c(t["base"]))
    p.setColor(QPalette.AlternateBase, c(t["pre_bg"]))
    p.setColor(QPalette.ToolTipBase, c(t["base"]))
    p.setColor(QPalette.ToolTipText, c(t["text"]))
    p.setColor(QPalette.Text, c(t["text"]))
    p.setColor(QPalette.Button, c(t["button"]))
    p.setColor(QPalette.ButtonText, c(t["text"]))
    p.setColor(QPalette.BrightText, c("#ff6b6b"))
    p.setColor(QPalette.Link, c(t["accent"]))
    p.setColor(QPalette.Highlight, c(t["accent"]))
    p.setColor(QPalette.HighlightedText, c("#ffffff"))
    p.setColor(QPalette.PlaceholderText, c(t["disabled"]))
    p.setColor(QPalette.Light, c(t["base"]))
    p.setColor(QPalette.Midlight, c(t["border"]))
    p.setColor(QPalette.Mid, c(t["border_strong"]))
    p.setColor(QPalette.Dark, c(t["border_strong"]))
    p.setColor(QPalette.Shadow, c("#000000"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, c(t["disabled"]))
    return p


def light_palette() -> QPalette:
    """The .ui preview always looks the way it was designed, whatever theme the app is in.

    Every colour is set explicitly: a palette with nothing marked as set would be replaced by the
    (dark) parent's palette as soon as the preview is put into a window.
    """
    from PyQt5.QtWidgets import QApplication
    std = QApplication.style().standardPalette()
    p = QPalette()
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        for role in range(QPalette.NColorRoles):
            r = QPalette.ColorRole(role)
            p.setColor(group, r, std.color(group, r))
    return p


def _id_rules(t) -> str:
    """Rules keyed on our own objectNames (safe anywhere; repeated in the chrome sheet so they win there)."""
    return f"""
QLabel#paneTitle {{ background: {t['window']}; color: {t['title_fg']}; border-bottom: 1px solid {t['border']};
                    padding: 5px 10px; font-size: 9pt; }}
QPushButton#bigButton {{ font-size: 12pt; padding: 10px 22px; background: {t['accent']}; color: {t['on_accent']};
                        border: none; border-radius: 8px; }}
QPushButton#bigButton:hover {{ background: {t['accent_hover']}; }}
QPushButton#primary {{ background: {t['accent']}; color: {t['on_accent']}; border: none; border-radius: 6px;
                      padding: 5px 12px; }}
QPushButton#primary:hover {{ background: {t['accent_hover']}; }}
QWidget#welcome {{ background: {t['window']}; }}
QWidget#tips {{ background: {t['tips_bg']}; border-bottom: 1px solid {t['tips_border']}; }}
QWidget#findBar {{ background: {t['window']}; border-top: 1px solid {t['border']}; }}
QLabel#legend {{ background: {t['window']}; border-top: 1px solid {t['border']}; padding: 4px 10px; font-size: 9pt; }}
QLabel#explorerTitle {{ padding-left: 4px; color: {t['title_fg']}; font-size: 9pt; }}
QLabel#explorerHint {{ font-size: 9pt; color: {t['muted']}; }}
QWidget#explorerPanel {{ background: {t['base']}; }}
QTabBar#fileTabs {{ background: {t['window']}; }}
QTabBar#fileTabs::tab {{ background: {t['window']}; color: {t['muted']}; border: none;
                        border-right: 1px solid {t['border']}; border-top: 2px solid transparent;
                        padding: 5px 8px 5px 12px; min-width: 70px; font-weight: normal; }}
QTabBar#fileTabs::tab:selected {{ background: {t['base']}; color: {t['text']}; border-top: 2px solid {t['accent']}; }}
QTabBar#fileTabs::tab:hover:!selected {{ color: {t['text']}; }}
"""


def app_stylesheet() -> str:
    t = T
    return _id_rules(t) + f"""
QSplitter::handle {{ background: {t['border']}; }}
QSplitter::handle:hover {{ background: {t['accent']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QMainWindow::separator {{ background: {t['border']}; width: 1px; height: 1px; }}
QMenu {{ background: {t['base']}; color: {t['text']}; border: 1px solid {t['border_strong']}; padding: 4px; }}
QMenu::item {{ padding: 5px 28px 5px 24px; border-radius: 4px; }}
QMenu::item:selected {{ background: {t['accent_soft']}; color: {t['text']}; }}
QMenu::item:disabled {{ color: {t['disabled']}; }}
QMenu::separator {{ height: 1px; background: {t['border']}; margin: 4px 8px; }}
QToolTip {{ background: {t['base']}; color: {t['text']}; border: 1px solid {t['border_strong']}; padding: 4px 6px; }}
"""


def chrome_stylesheet() -> str:
    t = T
    return _id_rules(t) + f"""
QToolBar {{ background: {t['window']}; border: none; border-bottom: 1px solid {t['border']}; spacing: 2px; padding: 4px 6px; }}
QToolBar::separator {{ background: {t['border']}; width: 1px; margin: 6px 6px; }}
QToolButton {{ background: transparent; color: {t['text']}; border: 1px solid transparent; border-radius: 6px; padding: 4px 8px; }}
QToolButton:hover {{ background: {t['hover']}; }}
QToolButton:pressed, QToolButton:checked {{ background: {t['accent_soft']}; }}
QToolButton:disabled {{ color: {t['disabled']}; }}
QMenuBar {{ background: {t['window']}; color: {t['text']}; border-bottom: 1px solid {t['border']}; padding: 2px 4px; }}
QMenuBar::item {{ background: transparent; padding: 4px 10px; border-radius: 4px; }}
QMenuBar::item:selected {{ background: {t['hover']}; }}
QStatusBar {{ background: {t['window']}; color: {t['muted']}; border-top: 1px solid {t['border']}; }}
QStatusBar QLabel {{ color: {t['muted']}; padding: 0 8px; }}

QPushButton {{ background: {t['button']}; color: {t['text']}; border: 1px solid {t['border_strong']};
               border-radius: 6px; padding: 5px 12px; }}
QPushButton:hover {{ background: {t['hover']}; }}
QPushButton:pressed {{ background: {t['accent_soft']}; }}
QPushButton:default {{ border-color: {t['accent']}; }}
QPushButton:disabled {{ color: {t['disabled']}; background: {t['window']}; border-color: {t['border']}; }}
QPushButton:flat {{ background: transparent; border: none; padding: 3px 6px; border-radius: 5px; }}
QPushButton:flat:hover {{ background: {t['hover']}; }}

QLineEdit, QComboBox {{ background: {t['base']}; color: {t['text']}; border: 1px solid {t['border_strong']};
                        border-radius: 5px; padding: 4px 6px; selection-background-color: {t['accent']}; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {t['accent']}; }}
QLineEdit:disabled {{ background: {t['window']}; color: {t['disabled']}; border-color: {t['border']}; }}
QComboBox QAbstractItemView {{ background: {t['base']}; border: 1px solid {t['border_strong']};
                               selection-background-color: {t['accent_soft']}; selection-color: {t['text']}; }}

QPlainTextEdit, QTextEdit, QTextBrowser {{ background: {t['base']}; color: {t['text']}; border: none;
                                           selection-background-color: {t['accent']}; selection-color: #ffffff; }}
QTreeView, QListView, QTableView, QTreeWidget, QListWidget, QTableWidget {{
    background: {t['base']}; color: {t['text']}; border: none; outline: 0;
    selection-background-color: {t['accent_soft']}; selection-color: {t['text']}; }}
QTreeView::item, QListView::item {{ padding: 2px 2px; }}
QTreeView::item:hover, QListView::item:hover {{ background: {t['hover']}; }}
QTreeView::item:selected, QListView::item:selected {{ background: {t['accent_soft']}; color: {t['text']}; }}
QTableView {{ gridline-color: {t['border']}; }}
QHeaderView::section {{ background: {t['window']}; color: {t['muted']}; border: none;
                        border-bottom: 1px solid {t['border']}; border-right: 1px solid {t['border']}; padding: 4px 6px; }}

QTabWidget::pane {{ border: none; border-top: 1px solid {t['border']}; top: -1px; background: {t['base']}; }}
QTabBar::tab {{ background: transparent; color: {t['muted']}; border: none; border-bottom: 2px solid transparent;
                padding: 6px 12px; margin-right: 2px; }}
QTabBar::tab:hover {{ color: {t['text']}; }}
QTabBar::tab:selected {{ color: {t['text']}; border-bottom: 2px solid {t['accent']}; font-weight: bold; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t['scroll']}; border-radius: 3px; min-height: 28px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t['scroll']}; border-radius: 3px; min-width: 28px; margin: 2px; }}
QScrollBar::handle:hover {{ background: {t['scroll_hover']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QProgressBar {{ background: {t['base']}; border: 1px solid {t['border_strong']}; border-radius: 6px;
                text-align: center; min-height: 16px; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 5px; }}
QCheckBox {{ spacing: 6px; }}
"""


def chrome(*widgets):
    """Give our own panels / dialogs the app look (and keep it in step with theme switches)."""
    sheet = chrome_stylesheet()
    for w in widgets:
        if w is None:
            continue
        w.setStyleSheet(sheet)
        key = id(w)
        _chromed[key] = weakref.ref(w)
        # Qt-created widgets (menuBar(), statusBar()) leave a dangling Python wrapper when Qt deletes them,
        # so forget a widget the moment Qt destroys it instead of finding out later.
        w.destroyed.connect(lambda _=None, k=key: _chromed.pop(k, None))


def apply(app, on: bool):
    set_dark(on)
    app.setPalette(palette(on))
    app.setStyleSheet(app_stylesheet())
    sheet = chrome_stylesheet()
    for key, ref in list(_chromed.items()):
        w = ref()
        if w is None:
            _chromed.pop(key, None)
            continue
        try:
            w.setStyleSheet(sheet)
        except RuntimeError:                     # the C++ widget is gone
            _chromed.pop(key, None)
