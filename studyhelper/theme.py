"""밝은 / 어두운 테마. One place for every colour the app picks itself (the rest follows the Qt palette)."""
import re

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
    "cur_line": "#eaf2ff", "flash": "#d3f9d8", "err_line": "#ffd9d9", "mark_line": "#fff4c2", "mark_word": "#ffd666",
    "gutter_bg": "#f3f3f3", "gutter_fg": "#999999", "gutter_mark": "#b8860b",
    # side panels / html
    "pre_bg": "#f4f4f4", "muted": "#888888", "text": "#202020", "unused": "#a0a0a0", "readonly_cell": "#f2f2f2",
    # stylesheet
    "title_bg": "#eef2f8", "title_fg": "#1f3a5f", "title_border": "#d3dce9",
    "bar_bg": "#f7f8fa", "bar_border": "#dde3ea", "tips_bg": "#fff8e1", "tips_border": "#f0dca0",
    "hover_bg": "#e6eefb", "hover_border": "#c4d4ee", "handle": "#e3e8ef", "handle_hover": "#9db8e6",
    "status": "#555555", "welcome_bg": "#fafbfd", "disabled": "#aaaaaa",
}
DARK = {
    "kw": "#6fa8ff", "self": "#c792ea", "str": "#8bc98b", "comment": "#7a8088", "num": "#82aaff",
    "widget": "#4da3ff",
    "cur_line": "#2a3a52", "flash": "#1f4a2a", "err_line": "#5a2a2a", "mark_line": "#4a4220", "mark_word": "#8a6d1a",
    "gutter_bg": "#2b2d30", "gutter_fg": "#7d8590", "gutter_mark": "#e0b341",
    "pre_bg": "#2f3238", "muted": "#9aa0a8", "text": "#e6e6e6", "unused": "#6f757d", "readonly_cell": "#33363b",
    "title_bg": "#2a2f38", "title_fg": "#c9d8f0", "title_border": "#3b4350",
    "bar_bg": "#272a2f", "bar_border": "#3a3f47", "tips_bg": "#3a3520", "tips_border": "#5a5030",
    "hover_bg": "#33415a", "hover_border": "#4a5f85", "handle": "#353a42", "handle_hover": "#5b7ab5",
    "status": "#b0b6be", "welcome_bg": "#212326", "disabled": "#6a6f76",
}

T = dict(LIGHT)          # the colours in use right now
dark = False


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
    p = QPalette()
    if not on:
        return p
    c = QColor
    p.setColor(QPalette.Window, c("#232528"))
    p.setColor(QPalette.WindowText, c("#e6e6e6"))
    p.setColor(QPalette.Base, c("#1b1d20"))
    p.setColor(QPalette.AlternateBase, c("#26282c"))
    p.setColor(QPalette.ToolTipBase, c("#2f3238"))
    p.setColor(QPalette.ToolTipText, c("#e6e6e6"))
    p.setColor(QPalette.Text, c("#e6e6e6"))
    p.setColor(QPalette.Button, c("#2e3136"))
    p.setColor(QPalette.ButtonText, c("#e6e6e6"))
    p.setColor(QPalette.BrightText, c("#ff6b6b"))
    p.setColor(QPalette.Link, c("#6fb3ff"))
    p.setColor(QPalette.Highlight, c("#2f6fd0"))
    p.setColor(QPalette.HighlightedText, c("#ffffff"))
    p.setColor(QPalette.PlaceholderText, c("#7d8590"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, c("#6a6f76"))
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


def stylesheet() -> str:
    t = T
    return f"""
QLabel#paneTitle {{ background: {t['title_bg']}; color: {t['title_fg']}; border-bottom: 1px solid {t['title_border']}; padding: 1px 4px; }}
QPushButton#bigButton {{ font-size: 12pt; padding: 10px 18px; background: #2f6fd0; color: white;
                        border: none; border-radius: 6px; }}
QPushButton#bigButton:hover {{ background: #255db3; }}
QWidget#welcome {{ background: {t['welcome_bg']}; }}
QToolBar {{ spacing: 4px; padding: 3px; border-bottom: 1px solid {t['bar_border']}; }}
QToolButton {{ padding: 4px 8px; border: 1px solid transparent; border-radius: 4px; }}
QToolButton:hover {{ background: {t['hover_bg']}; border-color: {t['hover_border']}; }}
QToolButton:disabled {{ color: {t['disabled']}; }}
QSplitter::handle {{ background: {t['handle']}; }}
QSplitter::handle:hover {{ background: {t['handle_hover']}; }}
QSplitter::handle:horizontal {{ width: 3px; }}
QSplitter::handle:vertical {{ height: 3px; }}
QLabel#explorerTitle {{ padding-left: 2px; }}
QLabel#explorerHint {{ font-size: 9pt; }}
QPushButton:flat {{ border: none; padding: 3px 5px; border-radius: 4px; }}
QPushButton:flat:hover {{ background: {t['hover_bg']}; }}
QTabWidget::pane {{ border: 1px solid {t['title_border']}; top: -1px; }}
QTabBar::tab:selected {{ font-weight: bold; }}
QTabBar::tab {{ padding: 5px 14px; }}
QTabBar#fileTabs::tab {{ padding: 4px 12px; min-width: 80px; font-weight: normal; }}
QTabBar#fileTabs::tab:selected {{ font-weight: bold; }}
QStatusBar QLabel {{ color: {t['status']}; padding: 0 6px; }}
QWidget#tips {{ background: {t['tips_bg']}; border-bottom: 1px solid {t['tips_border']}; }}
QWidget#findBar {{ background: {t['bar_bg']}; border-top: 1px solid {t['bar_border']}; }}
QLabel#legend {{ background: {t['bar_bg']}; border-top: 1px solid {t['bar_border']}; padding: 3px 6px; font-size: 9pt; }}
"""


def apply(app, on: bool):
    set_dark(on)
    app.setPalette(palette(on))
    app.setStyleSheet(stylesheet())
