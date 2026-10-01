"""해설 패널: 줄 해설(오프라인) + AI 해설/리뷰 + API 키 설정 대화상자."""
from html import escape

from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
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
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)

        intro = QLabel(
            "AI 해설은 Anthropic의 Claude API를 써요. <b>내 API 키</b>를 한 번만 넣으면 돼요.<br>"
            f"키 발급: <a href='{ai.KEY_PAGE}'>Anthropic 콘솔 → API Keys</a> "
            "(사용한 만큼 요금이 나가요)")
        intro.setOpenExternalLinks(True)
        intro.setWordWrap(True)
        lay.addWidget(intro)

        form = QFormLayout()
        row = QHBoxLayout()
        self.key = QLineEdit(ai.get_key())
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("sk-ant-...")
        self.key.setClearButtonEnabled(True)
        row.addWidget(self.key, 1)
        show = QCheckBox("보기")
        show.toggled.connect(lambda on: self.key.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        row.addWidget(show)
        paste = QPushButton("붙여넣기")
        paste.clicked.connect(self._paste)
        row.addWidget(paste)
        form.addRow("API 키", row)

        self.model = QComboBox()
        for mid, label in ai.MODELS:
            self.model.addItem(label, mid)
        self.model.setCurrentIndex([m for m, _ in ai.MODELS].index(ai.get_model()))
        form.addRow("모델", self.model)
        lay.addLayout(form)

        test_row = QHBoxLayout()
        self.test_btn = QPushButton("연결 테스트")
        self.test_btn.clicked.connect(self._test)
        test_row.addWidget(self.test_btn)
        self.result = QLabel("")
        self.result.setWordWrap(True)
        test_row.addWidget(self.result, 1)
        lay.addLayout(test_row)

        note = QLabel(f"<span style='color:#777'>키는 이 PC의 <b>{ai.key_source()}</b>에 저장돼요. "
                      "파일이나 저장소에는 남지 않아요.</span>")
        note.setWordWrap(True)
        lay.addWidget(note)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setText("저장")
        btns.button(QDialogButtonBox.Cancel).setText("취소")
        delete = btns.addButton("키 삭제", QDialogButtonBox.DestructiveRole)
        delete.clicked.connect(self._delete)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        if not ai.available():
            self.result.setText("<span style='color:#c0392b'>anthropic 패키지가 없어요: "
                                "pip install anthropic keyring</span>")

    def _paste(self):
        from PyQt5.QtWidgets import QApplication
        self.key.setText(QApplication.clipboard().text().strip())

    def _test(self):
        k = self.key.text().strip()
        if not k:
            self.result.setText("<span style='color:#c0392b'>키를 먼저 넣어 주세요.</span>")
            return
        self.result.setText("확인 중…")
        self.test_btn.setEnabled(False)
        QTimer.singleShot(0, lambda: self._do_test(k))

    def _do_test(self, k):
        from PyQt5.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            err = ai.test_key(k, self.model.currentData())
        finally:
            QApplication.restoreOverrideCursor()
            self.test_btn.setEnabled(True)
        self.result.setText("<span style='color:#2b8a3e'>연결 성공! 저장을 눌러 주세요.</span>" if err is None
                            else f"<span style='color:#c0392b'>{escape(err)}</span>")

    def _save(self):
        ai.set_key(self.key.text())
        ai.set_model(self.model.currentData())
        self.accept()

    def _delete(self):
        if QMessageBox.question(self, "키 삭제", "저장된 API 키를 지울까요?") == QMessageBox.Yes:
            ai.set_key("")
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
        gear = QPushButton("설정")
        gear.setToolTip("API 키와 모델 설정")
        gear.clicked.connect(self.settingsRequested)
        for b in (self.b_explain, self.b_review, self.b_stop):
            top.addWidget(b)
        top.addStretch(1)
        top.addWidget(gear)
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

        self.messages = []          # conversation sent to the API
        self.transcript = ""        # markdown shown
        self.current = ""
        self.worker = None
        self._render_timer = QTimer(self, singleShot=True, interval=80, timeout=self._render)
        self.show_welcome()

    # --- display -----------------------------------------------------------
    def show_welcome(self):
        if not ai.available():
            self.view.setHtml("<p>AI 해설을 쓰려면 <code>pip install anthropic keyring</code> 이 필요해요.</p>")
        elif not ai.get_key():
            self.view.setHtml(
                "<h3>AI 해설 시작하기</h3><p>내 코드를 AI가 설명하고 리뷰해 줘요.</p>"
                "<ol><li>오른쪽 위 <b>설정</b>을 눌러 API 키를 넣어요 (한 번만).</li>"
                "<li>Main.py에서 궁금한 줄을 선택하고 <b>Ctrl+E</b>.</li>"
                "<li>답을 본 뒤 아래 칸에 이어서 질문할 수 있어요.</li></ol>"
                "<p style='color:#888'>API 키가 없어도 <b>줄 해설</b> 탭은 그대로 쓸 수 있어요.</p>")
        else:
            model = dict(ai.MODELS).get(ai.get_model(), "")
            self.view.setHtml(
                f"<p>준비됐어요. <span style='color:#888'>({escape(model)})</span></p>"
                "<ul><li>Main.py에서 줄을 선택 → <b>Ctrl+E</b> 또는 우클릭 → AI에게 설명 듣기</li>"
                "<li><b>파일 전체 리뷰</b>로 잘한 점·버그·개선점 받기</li></ul>")

    def _render(self):
        self.view.setMarkdown(self.transcript + self.current)
        sb = self.view.verticalScrollBar()
        sb.setValue(sb.maximum())

    # --- requests ------------------------------------------------------------
    def _need_key(self) -> bool:
        if not ai.available() or not ai.get_key():
            self.settingsRequested.emit()
            return not ai.get_key()
        return False

    def start(self, context: str, task: str, title: str):
        """New conversation: code context + task."""
        if self._need_key():
            return
        self.messages = []
        self.transcript = ""
        self._send(f"{context}\n\n{task}", f"## 🧑 {title}\n\n")

    def _ask(self):
        q = self.question.text().strip()
        if not q or self.busy():
            return
        if not self.messages:
            self.view.setHtml("<p style='color:#c0392b'>먼저 <b>선택 부분 설명</b>이나 "
                              "<b>파일 전체 리뷰</b>를 시작해 주세요.</p>")
            return
        if self._need_key():
            return
        self.question.clear()
        self._send(q, f"\n\n---\n\n## 🧑 {q}\n\n")

    def _send(self, user_text, header_md):
        self.messages.append({"role": "user", "content": user_text})
        self.transcript += header_md + "**🤖 AI**\n\n"
        self.current = "_생각하는 중…_"
        self._render()
        self.current = ""
        self.worker = ai.AiWorker(ai.get_key(), ai.get_model(), list(self.messages), self)
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

    def _on_done(self, content):
        self.messages.append({"role": "assistant", "content": content})
        self.transcript += self.current
        self.current = ""
        self._render()

    def _on_failed(self, msg):
        self.messages.pop()                  # drop the unanswered question
        self.transcript += f"\n\n> ⚠️ {msg}\n"
        self.current = ""
        self._render()

    def stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
            if self.messages and self.messages[-1]["role"] == "user":
                self.messages.pop()
            self.transcript += self.current + "\n\n> (중지함)\n"
            self.current = ""
            self._render()

    def busy(self) -> bool:
        return bool(self.worker and self.worker.isRunning())

    def _set_busy(self, on):
        self.b_stop.setEnabled(on)
        for b in (self.b_explain, self.b_review, self.b_ask):
            b.setEnabled(not on)
