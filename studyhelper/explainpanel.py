"""해설 패널: 줄 해설(오프라인) + AI 해설/리뷰 + API 키 설정 대화상자."""
from html import escape

from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                             QTextBrowser, QVBoxLayout, QWidget)

import re

from . import ai, explain, notes


# ------------------------------------------------------------- line explainer
class LineExplainView(QTextBrowser):
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
             f"<pre style='background:#f4f4f4;padding:4px;white-space:pre-wrap'>"
             f"{idx + 1:>3}  {escape(line.strip())}</pre>"]
        if ctx:
            h.append(f"<p style='color:#0b6bcb;margin:2px 0 6px 0'>📍 {escape(ctx)}</p>")
        if not items:
            h.append("<p style='color:#888'>이 줄에 대한 준비된 해설이 없어요. "
                     "<b>AI 해설</b> 탭에서 물어볼 수 있어요 (줄을 선택하고 Ctrl+E).</p>")
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
        h.append("</div>")
        self.setHtml("".join(h))


# ------------------------------------------------------------------ settings
class AiSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 해설 설정")
        self.setMinimumWidth(600)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>1. 쓸 AI 모델 고르기</b> "
                             "<span style='color:#888'>(목록에 없는 최신 모델 이름은 직접 입력해도 돼요)</span>"))
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setInsertPolicy(QComboBox.NoInsert)
        self._fill_models()
        self.model.currentIndexChanged.connect(lambda _: self._on_model())
        self.model.lineEdit().editingFinished.connect(self._on_model)
        lay.addWidget(self.model)
        self.free_note = QLabel()
        self.free_note.setWordWrap(True)
        self.free_note.setOpenExternalLinks(True)
        lay.addWidget(self.free_note)

        lay.addSpacing(8)
        self.key_title = QLabel()
        lay.addWidget(self.key_title)
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
        self.key_help = QLabel()
        self.key_help.setWordWrap(True)
        self.key_help.setOpenExternalLinks(True)
        lay.addWidget(self.key_help)

        test_row = QHBoxLayout()
        self.test_btn = QPushButton("연결 테스트")
        self.test_btn.clicked.connect(self._test)
        test_row.addWidget(self.test_btn)
        self.result = QLabel("")
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
        for prov in ("gemini", "claude", "openai", "ollama"):
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
        is_local = prov == "ollama"
        self.key_row.setVisible(not is_local)
        self.delete_btn.setVisible(not is_local)
        self.key_title.setText("<b>2. 연결 확인</b>" if is_local else f"<b>2. {p['name']} API 키</b>")
        self.key.setPlaceholderText(p["hint"])
        self.key.setText(self._keys.get(prov, ai.get_key(prov) if not is_local else ""))
        self.key_help.setText("" if is_local else
                              f"<span style='color:#777'>키 발급: <a href='{p['key_page']}'>{p['key_page']}</a><br>"
                              f"키는 이 PC의 <b>{ai.key_source(prov)}</b>에 저장돼요. 파일이나 저장소에는 남지 않아요.</span>")
        if not ai.package_ok(prov):
            self.result.setText(f"<span style='color:#c0392b'>{p['package']} 패키지가 없어요. "
                                "install.bat 을 다시 실행해 주세요.</span>")
        else:
            self.result.setText("")

    def _test(self):
        model = self.current_model()
        key = self.key.text().strip() if self._prov != "ollama" else "local"
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
            if prov != "ollama" and k.strip() != ai.get_key(prov):
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
    explainRequested = pyqtSignal()      # main window supplies the selected code
    reviewRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        top = QHBoxLayout()
        self.b_explain = QPushButton("선택 부분 설명 (Ctrl+E)")
        self.b_explain.setToolTip("Main.py에서 선택한 줄들(선택이 없으면 현재 줄)을 설명해 줘요")
        self.b_explain.clicked.connect(self.explainRequested)
        self.b_review = QPushButton("파일 전체 리뷰")
        self.b_review.setToolTip("Main.py 전체를 보고 잘한 점·버그·개선점을 알려 줘요")
        self.b_review.clicked.connect(self.reviewRequested)
        self.b_stop = QPushButton("중지")
        self.b_stop.setEnabled(False)
        self.b_stop.clicked.connect(self.stop)
        self.b_model = QPushButton()
        self.b_model.setToolTip("AI 모델·API 키 설정")
        self.b_model.clicked.connect(self.settingsRequested)
        for b in (self.b_explain, self.b_review, self.b_stop):
            top.addWidget(b)
        top.addStretch(1)
        top.addWidget(self.b_model)
        lay.addLayout(top)

        self.view = QTextBrowser()
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
        self.show_welcome()

    @property
    def messages(self):
        return self.history

    # --- display -----------------------------------------------------------
    def show_welcome(self):
        model = ai.get_model()
        self.b_model.setText(f"모델: {model.replace('ollama:', '')}  ⚙")
        if not ai.ready(model):
            self.view.setHtml(
                "<h3>AI 해설 시작하기</h3><p>내 코드를 AI가 설명하고 리뷰해 줘요.</p>"
                "<ol><li>오른쪽 위 <b>모델 ⚙</b>을 눌러 AI를 고르고 키를 넣어요 (한 번만).<br>"
                "<span style='color:#2b8a3e'>무료: Gemini Flash(무료 티어) 또는 내 PC의 Ollama</span></li>"
                "<li>Main.py에서 궁금한 줄을 선택하고 <b>Ctrl+E</b>.</li>"
                "<li>답을 본 뒤 아래 칸에 이어서 질문할 수 있어요.</li></ol>"
                "<p style='color:#888'>키가 없어도 <b>줄 해설</b> 탭은 그대로 쓸 수 있어요.</p>")
        else:
            self.view.setHtml(
                f"<p>준비됐어요. <span style='color:#888'>({escape(ai.label_of(model))})</span></p>"
                "<ul><li>Main.py에서 줄을 선택 → <b>Ctrl+E</b> 또는 우클릭 → AI에게 설명 듣기</li>"
                "<li><b>파일 전체 리뷰</b>로 잘한 점·버그·개선점 받기</li></ul>")

    def _render(self):
        self.view.setMarkdown(self.transcript + self.current)
        sb = self.view.verticalScrollBar()
        sb.setValue(sb.maximum())

    # --- requests ------------------------------------------------------------
    def start(self, context: str, task: str, title: str):
        """New conversation: code context + task, on the currently chosen model."""
        if not ai.ready():
            self.settingsRequested.emit()
            if not ai.ready():
                return
        self.stop()
        self.history = []
        self.conv_model = ai.get_model()
        self.transcript = f"*{escape(ai.label_of(self.conv_model))}*\n\n"
        self._send(f"{context}\n\n{task}", f"## 🧑 {title}\n\n")

    def _ask(self):
        q = self.question.text().strip()
        if not q or self.busy():
            return
        if not self.history:
            self.view.setHtml("<p style='color:#c0392b'>먼저 <b>선택 부분 설명</b>이나 "
                              "<b>파일 전체 리뷰</b>를 시작해 주세요.</p>")
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
