"""해설 패널: 줄 해설(오프라인) + AI 해설/리뷰 + API 키 설정 대화상자."""
from html import escape

from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QMenu, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QFileDialog, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
                             QWidget)

import re

from . import ai, explain, notes, theme
from .theme import ThemedBrowser, ThemedLabel, chrome


# ------------------------------------------------------------- line explainer
AI_LINK = "ai:line"          # link at the bottom of a line explanation -> ask the AI about this line


class LineExplainView(ThemedBrowser):
    def __init__(self):
        super().__init__()
        self.setOpenLinks(False)
        self.vault = None
        self._last = None
        self.show_line([], -1)

    def show_line(self, lines, idx):
        key = (idx, lines[idx] if 0 <= idx < len(lines) else None)
        if key == self._last:
            return
        self._last = key
        if not (0 <= idx < len(lines)) or not lines[idx].strip():
            self.setHtml("<p style='color:#888'>Main.py에서 궁금한 줄을 클릭하면 "
                         "<b>무엇을 하는지</b>와 <b>왜 이렇게 썼는지</b>가 여기 나와요.</p>")
            return
        line = lines[idx]
        items = explain.explain_line(line)
        ctx = explain.context_of(lines, idx)
        h = [f"<div style='font-size:10pt'>",
             f"<pre style='background:{theme.T['pre_bg']};padding:4px;white-space:pre-wrap'>"
             f"{idx + 1:>3}  {escape(line.strip())}</pre>"]
        if ctx:
            h.append(f"<p style='color:#0b6bcb;margin:2px 0 6px 0'>📍 {escape(ctx)}</p>")
        if not items:
            h.append("<p style='color:#888'>이 줄에 대한 준비된 해설이 없어요. "
                     "아래 링크를 누르면 AI에게 물어볼 수 있어요.</p>")
        for n in items:
            h.append(f"<p style='margin:8px 0 2px 0'><b>{escape(n.title)}</b></p>")
            h.append(f"<p style='margin:0 0 0 10px'>• {escape(n.what)}</p>")
            if n.why:
                h.append(f"<p style='margin:2px 0 0 10px;color:#2b6e2b'>왜? {escape(n.why)}</p>")
            if n.pitfall:
                h.append(f"<p style='margin:2px 0 0 10px;color:#c0392b'>주의! {escape(n.pitfall)}</p>")
        links = []
        for cls in dict.fromkeys(re.findall(r"\b(Q[A-Z]\w+)", line)):
            hit = next(iter(notes.search(self.vault, cls, 1)), None) if self.vault else None
            if hit:
                links.append(f"<a href='{notes.obsidian_url(self.vault, hit)}'>{escape(notes.label(self.vault, hit))}</a>")
        if links:
            h.append("<p style='margin:10px 0 0 0'>📘 내 노트: " + " · ".join(links) + "</p>")
        h.append(f"<p style='margin:12px 0 0 0'><a href='{AI_LINK}'>🤖 이 줄을 AI에게 더 자세히 물어보기</a>"
                 " <span style='color:#888'>(Ctrl+E)</span></p>")
        h.append("</div>")
        self.setHtml("".join(h))


# ------------------------------------------------------------------ settings
class AiSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        chrome(self)                           # the app look for this dialog
        self.setWindowTitle("AI 해설 설정")
        self.setMinimumWidth(600)
        lay = QVBoxLayout(self)
        lay.addWidget(ThemedLabel("<b>1. 쓸 AI 모델 고르기</b> "
                             "<span style='color:#888'>(목록에 없는 최신 모델 이름은 직접 입력해도 돼요)</span>"))
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setInsertPolicy(QComboBox.NoInsert)
        self._fill_models()
        self.model.currentIndexChanged.connect(lambda _: self._on_model())
        self.model.lineEdit().editingFinished.connect(self._on_model)
        lay.addWidget(self.model)
        self.free_note = ThemedLabel()
        self.free_note.setWordWrap(True)
        self.free_note.setOpenExternalLinks(True)
        lay.addWidget(self.free_note)

        lay.addSpacing(8)
        self.key_title = ThemedLabel()
        lay.addWidget(self.key_title)
        self.login_btn = QPushButton("Claude Code 로그인 창 열기")
        self.login_btn.setToolTip("처음 한 번만 로그인하면 돼요. 로그인을 마친 뒤 [연결 테스트]를 눌러 주세요")
        self.login_btn.clicked.connect(lambda: ai.open_claude_login() or
                                       self.result.setText("<span style='color:#c0392b'>claude.exe를 찾지 못했어요.</span>"))
        self.login_btn.setVisible(False)
        lay.addWidget(self.login_btn)
        self.key_row = QWidget()
        row = QHBoxLayout(self.key_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setClearButtonEnabled(True)
        row.addWidget(self.key, 1)
        show = QCheckBox("보기")
        show.toggled.connect(lambda on: self.key.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        row.addWidget(show)
        paste = QPushButton("붙여넣기")
        paste.clicked.connect(lambda: self.key.setText(QApplication.clipboard().text().strip()))
        row.addWidget(paste)
        lay.addWidget(self.key_row)
        self.key_help = ThemedLabel()
        self.key_help.setWordWrap(True)
        self.key_help.setOpenExternalLinks(True)
        lay.addWidget(self.key_help)

        test_row = QHBoxLayout()
        self.test_btn = QPushButton("연결 테스트")
        self.test_btn.clicked.connect(self._test)
        test_row.addWidget(self.test_btn)
        self.result = ThemedLabel("")
        self.result.setWordWrap(True)
        test_row.addWidget(self.result, 1)
        lay.addLayout(test_row)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setText("저장")
        btns.button(QDialogButtonBox.Cancel).setText("취소")
        self.delete_btn = btns.addButton("이 키 삭제", QDialogButtonBox.DestructiveRole)
        self.delete_btn.clicked.connect(self._delete)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self._keys = {}            # provider -> key typed in this dialog
        self._prov = None
        self._on_model()

    def _fill_models(self):
        cur = ai.get_model()
        self.model.clear()
        groups = {}
        for mid, label, prov, _ in ai.MODELS:
            groups.setdefault(prov, []).append((mid, label))
        local = ai.ollama_models()
        groups["ollama"] = [(f"ollama:{n}", ai.label_of(f"ollama:{n}")) for n in local] or \
                           [(f"ollama:{ai.OLLAMA_SUGGEST}", f"{ai.OLLAMA_SUGGEST} — 내 PC · 완전 무료 (Ollama 설치 필요)")]
        groups["web"] = [(mid, label) for mid, label, _ in ai.WEB_TARGETS]
        groups["claudecode"] = [(ai.CLAUDE_CODE_MODEL, ai.label_of(ai.CLAUDE_CODE_MODEL))]
        for prov in ("claudecode", "web", "gemini", "claude", "openai", "ollama"):
            self.model.addItem(f"── {ai.PROVIDERS[prov]['name']} ──")
            self.model.model().item(self.model.count() - 1).setEnabled(False)
            for mid, label in groups.get(prov, []):
                self.model.addItem(label, mid)
        i = self.model.findData(cur)
        if i >= 0:
            self.model.setCurrentIndex(i)
        else:
            self.model.setEditText(cur)

    def current_model(self) -> str:
        i = self.model.currentIndex()
        if i >= 0 and self.model.itemText(i) == self.model.currentText() and self.model.itemData(i):
            return self.model.itemData(i)
        return self.model.currentText().strip()      # typed custom model id

    def _on_model(self):
        if self._prov:
            self._keys[self._prov] = self.key.text()
        model = self.current_model()
        prov = ai.provider_of(model)
        self._prov = prov
        p = ai.PROVIDERS[prov]
        free = next((f for mid, _, _, f in ai.MODELS if mid == model), prov == "ollama")
        notes_ = {
            "claudecode": ("이 PC에 설치된 <b>Claude Code</b>(Claude 데스크톱 앱 포함)를 창 없이 불러와서, "
                           "<b>내 Claude 구독</b>으로 답을 받아요. <b>API 키가 필요 없고</b> 답이 도우미 안에 바로 나와요.<br>"
                           "Claude 유료 구독(Pro/Max 등)과 Claude Code 로그인이 필요해요. 구독 사용량이 차감돼요. "
                           "도구·파일 접근 없이 답만 받도록 실행해요."),
            "web": ("<b>무료 · 키 필요 없음.</b> Ctrl+E를 누르면 질문(코드 포함)이 <b>복사</b>되고 웹 AI 창이 열려요. "
                    "그 창에 <b>Ctrl+V → Enter</b> 하면 돼요. 무료 계정 로그인이 필요할 수 있어요.<br>"
                    "답은 도우미 안이 아니라 웹 창에 나와요. 내 코드가 그 사이트로 보내진다는 점은 알아 두세요."),
            "gemini": ("Google AI Studio 키로 <b>무료 티어</b>를 쓸 수 있어요 (분당·하루 사용량 제한). "
                       "무료 티어에서는 입력한 내용이 Google 제품 개선에 쓰일 수 있어요."
                       if free else "이 모델은 유료예요 (Google 결제 설정 필요)."),
            "claude": "Anthropic 콘솔에서 결제 후 키를 만들어요. 사용한 만큼 요금이 나가요.",
            "openai": "OpenAI 플랫폼에서 결제 후 키를 만들어요. 사용한 만큼 요금이 나가요.",
            "ollama": ("<b>완전 무료 · 인터넷 없이</b> 내 PC에서 돌아가요. "
                       f"<a href='{p['key_page']}'>Ollama 설치</a> → 명령창에서 "
                       f"<code>ollama pull {ai.OLLAMA_SUGGEST}</code> (약 5GB). "
                       "PC 성능에 따라 느릴 수 있고, 답의 품질은 클라우드 모델보다 낮을 수 있어요."),
        }
        self.free_note.setText(f"<span style='color:#555'>{notes_[prov]}</span>")
        is_local = prov in ("ollama", "web", "claudecode")
        self.login_btn.setVisible(prov == "claudecode")
        self.key_row.setVisible(not is_local)
        self.delete_btn.setVisible(not is_local)
        self.test_btn.setVisible(prov != "web")
        self.key_title.setText("" if prov == "web" else
                               "<b>2. 연결 확인</b>" if is_local else f"<b>2. {p['name']} API 키</b>")
        self.key.setPlaceholderText(p["hint"])
        self.key.setText(self._keys.get(prov, ai.get_key(prov) if not is_local else ""))
        self.key_help.setText("" if is_local else
                              f"<span style='color:#777'>키 발급: <a href='{p['key_page']}'>{p['key_page']}</a><br>"
                              f"키는 이 PC의 <b>{ai.key_source(prov)}</b>에 저장돼요. 파일이나 저장소에는 남지 않아요.</span>")
        if not ai.package_ok(prov):
            self.result.setText(f"<span style='color:#c0392b'>{p['package']} 패키지가 없어요. "
                                "install.bat 을 다시 실행해 주세요.</span>")
        elif prov == "claudecode":        # installed? signed in? (nothing is sent)
            ok, msg = ai.claude_code_status()
            self.result.setText(f"<span style='color:{'#2b8a3e' if ok else '#c0392b'}'>{msg}</span>")
        else:
            self.result.setText("")

    def _test(self):
        model = self.current_model()
        key = self.key.text().strip() if self._prov not in ("ollama", "web", "claudecode") else "local"
        if not key:
            self.result.setText("<span style='color:#c0392b'>키를 먼저 넣어 주세요.</span>")
            return
        self.result.setText("확인 중…")
        self.test_btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            err = ai.test_key(model, key)
        finally:
            QApplication.restoreOverrideCursor()
            self.test_btn.setEnabled(True)
        self.result.setText("<span style='color:#2b8a3e'>연결 성공! 저장을 눌러 주세요.</span>" if err is None
                            else f"<span style='color:#c0392b'>{escape(err)}</span>")

    def _save(self):
        model = self.current_model()
        if not model:
            return
        self._keys[self._prov] = self.key.text()
        for prov, k in self._keys.items():
            if prov not in ("ollama", "web", "claudecode") and k.strip() != ai.get_key(prov):
                ai.set_key(prov, k)
        ai.set_model(model)
        self.accept()

    def _delete(self):
        p = ai.PROVIDERS[self._prov]
        if QMessageBox.question(self, "키 삭제", f"저장된 {p['name']} 키를 지울까요?") == QMessageBox.Yes:
            ai.set_key(self._prov, "")
            self._keys[self._prov] = ""
            self.key.clear()
            self.result.setText("키를 지웠어요.")


# ------------------------------------------------------------------ AI panel
class AiPanel(QWidget):
    settingsRequested = pyqtSignal()
    freeAiRequested = pyqtSignal()       # "무료 AI 켜기" wizard
    explainRequested = pyqtSignal()      # main window supplies the selected code
    reviewRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        top = QHBoxLayout()
        self.b_explain = QPushButton("선택 줄 설명")
        self.b_explain.setToolTip("Main.py에서 선택한 줄들(선택이 없으면 현재 줄)을 설명해 줘요 (Ctrl+E)")
        self.b_explain.clicked.connect(self.explainRequested)
        self.b_review = QPushButton("전체 리뷰")
        self.b_review.setToolTip("Main.py 전체를 보고 잘한 점·버그·개선점을 알려 줘요")
        self.b_review.clicked.connect(self.reviewRequested)
        self.b_stop = QPushButton("중지")
        self.b_stop.setEnabled(False)
        self.b_stop.clicked.connect(self.stop)
        self.b_free = QPushButton("무료 AI 켜기")
        self.b_free.setObjectName("primary")
        self.b_free.setToolTip("구글 계정만 있으면 무료. 키를 한 번만 연결하면 답이 도우미 안에 바로 나와요")
        self.b_free.clicked.connect(self.freeAiRequested)
        self.b_model = QPushButton()
        self.b_model.setToolTip("AI 모델·API 키 설정")
        self.b_model.clicked.connect(self.settingsRequested)
        for b in (self.b_explain, self.b_review, self.b_stop):
            top.addWidget(b)
        self.b_recopy = QPushButton("질문 다시 복사")
        self.b_recopy.setToolTip("웹 AI에 붙여넣을 질문을 클립보드에 다시 복사해요")
        self.b_recopy.clicked.connect(self.recopy)
        self.b_recopy.setVisible(False)
        top2 = QHBoxLayout()                     # second row: situational buttons, so the panel can stay narrow
        top2.addWidget(self.b_recopy)
        top2.addWidget(self.b_free)
        self.b_unwatch = QPushButton("답 가져오기 끝")
        self.b_unwatch.setToolTip("웹 AI에서 복사한 답을 더 이상 가져오지 않아요 (다른 걸 복사해도 안 들어오게)")
        self.b_unwatch.clicked.connect(lambda: self._set_watching(False))
        self.b_unwatch.setVisible(False)
        top2.addWidget(self.b_unwatch)
        self.b_code = QPushButton("코드 복사")
        self.b_code.setToolTip("AI 답에 들어 있는 코드 블록을 클립보드에 복사해요")
        self.b_code.clicked.connect(self._copy_code)
        self.b_code.setVisible(False)
        top2.addWidget(self.b_code)
        self.b_save = QPushButton("대화 저장")
        self.b_save.setToolTip("지금까지의 AI 대화를 .md 파일로 저장해요 (내 노트 폴더에 저장해도 돼요)")
        self.b_save.clicked.connect(self.save_conversation)
        self.b_save.setVisible(False)
        top2.addWidget(self.b_save)
        self.save_dir = ""                       # set by the main window: the open file's folder
        top2.addStretch(1)
        top.addStretch(1)
        top.addWidget(self.b_model)
        lay.addLayout(top)
        lay.addLayout(top2)

        self.view = ThemedBrowser()
        self.view.setOpenExternalLinks(True)
        lay.addWidget(self.view, 1)

        ask = QHBoxLayout()
        self.question = QLineEdit()
        self.question.setPlaceholderText("이어서 질문하기 (예: lambda는 왜 썼어?)  Enter")
        self.question.returnPressed.connect(self._ask)
        self.b_ask = QPushButton("질문")
        self.b_ask.clicked.connect(self._ask)
        ask.addWidget(self.question, 1)
        ask.addWidget(self.b_ask)
        lay.addLayout(ask)

        self.history = []           # [{'role', 'content', 'raw'}]
        self.conv_model = None      # follow-ups stay on the model the conversation started with
        self.transcript = ""
        self.current = ""
        self.worker = None
        self._render_timer = QTimer(self, singleShot=True, interval=80, timeout=self._render)
        # web AI answers come back through the clipboard while we're "watching"
        self._watching = False
        self._own_copies = set()
        self._answers = 0
        self._web_name = ""
        self._watch_timer = QTimer(self, singleShot=True, interval=20 * 60 * 1000,
                                   timeout=lambda: self._set_watching(False))
        QApplication.clipboard().dataChanged.connect(self._on_clipboard)
        self.show_welcome()

    @property
    def messages(self):
        return self.history

    # --- display -----------------------------------------------------------
    def show_welcome(self):
        model = ai.get_model()
        self.b_model.setText(f"AI: {ai.short_name(model)} · 설정")
        self.b_free.setVisible(ai.provider_of(model) == "web" or not ai.ready(model))   # hide once an API AI works
        if ai.provider_of(model) == "web":
            self.question.setPlaceholderText("이어서 물어볼 말을 쓰고 Enter → 복사돼요 (웹 창에 붙여넣기)")
            self.view.setHtml(
                f"<h3>AI 해설 — {escape(ai.short_name(model))} (무료)</h3>"
                "<ol><li>Main.py에서 궁금한 줄을 선택하고 <b>Ctrl+E</b> (또는 <b>전체 리뷰</b>).</li>"
                "<li>질문이 <b>자동으로 복사</b>되고 웹 AI 창이 열려요.</li>"
                "<li>그 창의 입력칸에 <b>Ctrl+V → Enter</b>.</li>"
                "<li>답 아래의 <b>복사 버튼</b>을 누르면 <b>답이 여기로 들어와요.</b></li></ol>"
                "<p style='color:#888'>API 키가 있으면 오른쪽 위 <b>AI · 설정</b>에서 바꾸면 답이 여기 바로 나와요.</p>")
            return
        self.question.setPlaceholderText("이어서 질문하기 (예: lambda는 왜 썼어?)  Enter")
        if not ai.ready(model):
            self.view.setHtml(
                "<h3>AI 해설 시작하기</h3><p>내 코드를 AI가 설명하고 리뷰해 줘요.</p>"
                "<ol><li>오른쪽 위 <b>AI · 설정</b>을 눌러 AI를 고르고 키를 넣어요 (한 번만).<br>"
                "<span style='color:#2b8a3e'>무료: 웹 AI(키 필요 없음), Gemini Flash(무료 티어), 내 PC의 Ollama</span></li>"
                "<li>Main.py에서 궁금한 줄을 선택하고 <b>Ctrl+E</b>.</li>"
                "<li>답을 본 뒤 아래 칸에 이어서 질문할 수 있어요.</li></ol>"
                "<p style='color:#888'>키가 없어도 <b>줄 해설</b> 탭은 그대로 쓸 수 있어요.</p>")
        else:
            self.view.setHtml(
                f"<p>준비됐어요. <span style='color:#888'>({escape(ai.label_of(model))})</span></p>"
                "<ul><li>Main.py에서 줄을 선택 → <b>Ctrl+E</b> 또는 우클릭 → AI에게 설명 듣기</li>"
                "<li><b>전체 리뷰</b>로 잘한 점·버그·개선점 받기</li></ul>")

    def code_blocks(self) -> list[str]:
        """Fenced code blocks of the conversation so far (newest last)."""
        return [m.group(1).strip("\n") for m in re.finditer(r"```[^\n]*\n(.*?)```", self.transcript + self.current, re.S)]

    def _copy_code(self):
        blocks = self.code_blocks()
        if not blocks:
            return
        if len(blocks) == 1:
            self._copy_own(blocks[0])
            return
        menu = QMenu(self)
        for i, b in enumerate(blocks, 1):
            first = next((ln.strip() for ln in b.split("\n") if ln.strip()), "")
            act = menu.addAction(f"{i}. {first[:40]}")
            act.setData(b)
        picked = menu.exec_(self.b_code.mapToGlobal(self.b_code.rect().bottomLeft()))
        if picked is not None:
            self._copy_own(picked.data())

    def conversation_text(self) -> str:
        return (self.transcript + self.current).strip()

    def save_conversation(self, path=None):
        text = self.conversation_text()
        if not text:
            return None
        if not path:
            from datetime import datetime
            from pathlib import Path
            base = Path(self.save_dir) if self.save_dir and Path(self.save_dir).is_dir() else Path.home()
            default = str(base / f"AI해설_{datetime.now():%Y%m%d_%H%M}.md")
            path, _ = QFileDialog.getSaveFileName(self, "AI 대화 저장", default, "Markdown (*.md);;텍스트 (*.txt)")
            if not path:
                return None
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError as e:
            QMessageBox.warning(self, "저장 실패", str(e))
            return None
        return path

    def _render(self):
        self.b_code.setVisible(bool(self.code_blocks()))
        self.b_save.setVisible(bool(self.conversation_text()))
        self.view.setMarkdown(self.transcript + self.current)
        sb = self.view.verticalScrollBar()
        sb.setValue(sb.maximum())

    # --- requests ------------------------------------------------------------
    def start(self, context: str, task: str, title: str):
        """New conversation: code context + task, on the currently chosen model."""
        model = ai.get_model()
        if ai.provider_of(model) == "web":
            self._send_to_web(model, ai.web_prompt(context, task), title)
            return
        self._set_watching(False)
        if not ai.ready():
            self.settingsRequested.emit()
            if not ai.ready():
                return
        self.stop()
        self.history = []
        self.conv_model = ai.get_model()
        self.transcript = f"*{escape(ai.label_of(self.conv_model))}*\n\n"
        self._send(f"{context}\n\n{task}", f"## 🧑 {title}\n\n")

    # --- web AI: copy the question out, bring the answer back via the clipboard ------------
    def _copy_own(self, text):
        """Copy something ourselves (so the clipboard watcher doesn't import it as an answer)."""
        self._own_copies.add(text)
        QApplication.clipboard().setText(text)

    def _send_to_web(self, model, prompt, title):
        self.stop()
        self.history = []
        self.conv_model = model
        self._copy_own(prompt)
        url = ai.web_url(model)
        QDesktopServices.openUrl(QUrl(url))
        name = ai.short_name(model)
        self._web_name = name
        self._answers = 0
        self.transcript = (f"## 🧑 {title}\n\n"
                           f"*{name}에 보낼 질문을 복사했어요 ({len(prompt):,}자: 해설 요청 + 코드 + .ui 위젯 목록).*\n\n")
        self.current = ""
        self.view.setHtml(
            f"<h3>📋 {escape(title)} — 질문을 복사했어요</h3>"
            f"<p><b>{escape(name)}</b> 창이 열렸어요 (안 열리면 <a href='{url}'>여기</a>).</p>"
            "<ol><li>웹 AI의 입력칸을 클릭하고 <b>Ctrl+V</b> → <b>Enter</b></li>"
            "<li>답이 나오면 답 아래의 <b>복사 버튼</b>을 누르세요 (또는 답을 드래그해서 Ctrl+C)</li>"
            "<li><b>→ 답이 자동으로 여기로 들어와요.</b></li></ol>"
            "<p style='color:#888'>이어서 물어볼 땐 아래 칸에 쓰고 Enter → 질문이 복사되니 웹 창에 붙여넣으면 돼요. "
            "복사가 풀렸으면 위의 <b>질문 다시 복사</b>.</p>")
        self._last_web = (model, prompt, title)
        self._set_watching(True)

    def _set_watching(self, on):
        self._watching = on
        self.b_recopy.setVisible(on)
        self.b_unwatch.setVisible(on)
        if on:
            self._watch_timer.start()          # stop listening after a while on its own

    def _on_clipboard(self):
        if not self._watching:
            return
        text = QApplication.clipboard().text()
        if not text.strip() or text in self._own_copies or len(text.strip()) < 15:
            return
        self._own_copies.add(text)             # don't import the same text twice
        self._answers += 1
        head = f"**🤖 {self._web_name} 답 (가져옴)**" if self._answers == 1 else \
            f"\n\n---\n\n**🤖 {self._web_name} 답 {self._answers} (가져옴)**"
        self.transcript += f"{head}\n\n{text.strip()}\n"
        self._render()
        self._watch_timer.start()              # keep listening while answers keep coming

    def recopy(self):
        if getattr(self, "_last_web", None):
            self._copy_own(self._last_web[1])
            self.b_recopy.setText("복사했어요 ✓")
            QTimer.singleShot(1500, lambda: self.b_recopy.setText("질문 다시 복사"))

    def _ask(self):
        q = self.question.text().strip()
        if not q or self.busy():
            return
        if ai.provider_of(self.conv_model or ai.get_model()) == "web":
            if not getattr(self, "_last_web", None):
                self.view.setHtml("<p style='color:#c0392b'>먼저 <b>선택 줄 설명</b>이나 "
                                  "<b>전체 리뷰</b>를 시작해 주세요.</p>")
                return
            self.question.clear()
            self._copy_own(q)
            self.transcript += (f"\n\n---\n\n## 🧑 {q}\n\n"
                                "*질문을 복사했어요 → 웹 창에 Ctrl+V → Enter. 답의 복사 버튼을 누르면 여기로 들어와요.*\n\n")
            self._render()
            self._set_watching(True)
            return
        if not self.history:
            self.view.setHtml("<p style='color:#c0392b'>먼저 <b>선택 줄 설명</b>이나 "
                              "<b>전체 리뷰</b>를 시작해 주세요.</p>")
            return
        self.question.clear()
        self._send(q, f"\n\n---\n\n## 🧑 {q}\n\n")

    def _send(self, user_text, header_md):
        self.history.append({"role": "user", "content": user_text})
        self.transcript += header_md + "**🤖 AI**\n\n"
        self.current = "_생각하는 중…_"
        self._render()
        self.current = ""
        self.worker = ai.AiWorker(self.conv_model, list(self.history), self)
        self.worker.chunk.connect(self._on_chunk)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(lambda: self._set_busy(False))
        self._set_busy(True)
        self.worker.start()

    def _on_chunk(self, text):
        self.current += text
        if not self._render_timer.isActive():
            self._render_timer.start()

    def _on_done(self, text, raw):
        self.history.append({"role": "assistant", "content": text, "raw": raw})
        self.transcript += self.current
        self.current = ""
        self._render()

    def _on_failed(self, msg):
        if self.history and self.history[-1]["role"] == "user":
            self.history.pop()                   # drop the unanswered question
        self.transcript += self.current + f"\n\n> ⚠️ {msg}\n"
        self.current = ""
        self._render()

    def stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            self.transcript += self.current + "\n\n> (중지함)\n"
            self.current = ""
            self._render()

    def busy(self) -> bool:
        return bool(self.worker and self.worker.isRunning())

    def _set_busy(self, on):
        self.b_stop.setEnabled(on)
        for b in (self.b_explain, self.b_review, self.b_ask):
            b.setEnabled(not on)
