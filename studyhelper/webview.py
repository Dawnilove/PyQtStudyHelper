"""웹 AI 창 (내장 브라우저). PyQtWebEngine이 설치돼 있을 때만 쓴다.

The site is used exactly like in a normal browser: the student pastes and presses Enter,
and copies the answer with the site's copy button (the AI panel picks it up from the clipboard).
Nothing on the page is typed, clicked or read automatically.
"""
from PyQt5.QtCore import QSettings, Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QGuiApplication
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

SITES = [("ChatGPT", "https://chatgpt.com/"), ("Gemini", "https://gemini.google.com/app"),
         ("Claude", "https://claude.ai/new")]

_profile = None          # one persistent profile for the app's lifetime (keeps you logged in)


def available() -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec("PyQt5.QtWebEngineWidgets") is not None
    except (ImportError, ValueError):
        return False


def _get_profile():
    global _profile
    if _profile is None:
        from PyQt5.QtWebEngineWidgets import QWebEngineProfile, QWebEngineSettings
        _profile = QWebEngineProfile("PyQtStudyHelper")          # named profile = saved on disk
        _profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        st = _profile.settings()
        st.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)   # sites' copy buttons
        st.setAttribute(QWebEngineSettings.JavascriptCanPaste, True)
    return _profile


def _make_page(parent):
    from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView

    class Page(QWebEnginePage):
        popups = []

        def createWindow(self, _type):
            # login pop-ups (e.g. "sign in with …") open in a small window of their own
            win = QWebEngineView()
            win.setAttribute(Qt.WA_DeleteOnClose)
            p = Page(_get_profile(), win)
            win.setPage(p)
            p.windowCloseRequested.connect(win.close)
            win.resize(520, 680)
            win.setWindowTitle("로그인")
            win.show()
            Page.popups.append(win)
            win.destroyed.connect(lambda *_: Page.popups.remove(win) if win in Page.popups else None)
            return p

    return Page(_get_profile(), parent)


class WebAiWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        from PyQt5.QtWebEngineWidgets import QWebEngineView
        self.setWindowTitle("웹 AI — PyQt 학습 도우미")
        self.settings = QSettings("PyQtStudyHelper", "PyQtStudyHelper")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        bar = QHBoxLayout()
        for name, url in SITES:
            b = QPushButton(name)
            b.setToolTip(f"{name} 열기")
            b.clicked.connect(lambda _=False, u=url: self.open_site(u, force=True))
            bar.addWidget(b)
        bar.addSpacing(12)
        back = QPushButton("◀ 뒤로")
        reload_ = QPushButton("새로고침")
        ext = QPushButton("기본 브라우저로 열기")
        ext.setToolTip("로그인이 안 되거나 화면이 이상하면 크롬·엣지에서 열어요")
        bar.addWidget(back)
        bar.addWidget(reload_)
        bar.addStretch(1)
        bar.addWidget(ext)
        lay.addLayout(bar)
        tip = QLabel("<span style='color:#555'>입력칸 클릭 → <b>Ctrl+V</b> → <b>Enter</b>. "
                     "답 아래 <b>복사 버튼</b>을 누르면 도우미로 들어가요. "
                     "로그인은 한 번만 하면 유지돼요. (구글 계정 로그인이 막히거나 보안 확인 화면에서 넘어가지 않으면 "
                     "<b>기본 브라우저로 열기</b>를 써 주세요 — 특히 Claude)</span>")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        self.view = QWebEngineView(self)
        self.page = _make_page(self.view)
        self.view.setPage(self.page)
        lay.addWidget(self.view, 1)
        back.clicked.connect(self.view.back)
        reload_.clicked.connect(self.view.reload)
        ext.clicked.connect(lambda: QDesktopServices.openUrl(self.view.url()))
        self.view.titleChanged.connect(lambda t: self.setWindowTitle(f"{t} — 웹 AI" if t else "웹 AI"))
        geo = self.settings.value("web/geometry")
        if geo is None or not self.restoreGeometry(geo):
            self._place_default()

    def _place_default(self):
        """Right side of the screen, next to the helper."""
        scr = QGuiApplication.primaryScreen().availableGeometry()
        w = min(760, scr.width() // 2)
        self.setGeometry(scr.right() - w, scr.top() + 30, w, scr.height() - 60)

    def open_site(self, url: str, force=False):
        cur = self.view.url()
        if force or cur.isEmpty() or QUrl(url).host() != cur.host():
            self.view.load(QUrl(url))      # keep the current chat if we're already on that site
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        self.settings.setValue("web/geometry", self.saveGeometry())
        self.hide()                        # keep the page (and the chat) for next time
        e.ignore()

    def shutdown(self):
        """App is quitting: close login pop-ups too (they have no parent)."""
        self.settings.setValue("web/geometry", self.saveGeometry())
        for w in list(getattr(type(self.page), "popups", [])):
            w.close()
        self.hide()
