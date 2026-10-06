"""AI 해설·리뷰 요청과 AI 설정 창."""
from . import ai
from .explainpanel import AiSettingsDialog


class AiMixin:
    """MainWindow part: AI 해설·리뷰 요청과 AI 설정 창."""

    def _ai_context(self) -> str:
        lines = self.editor.toPlainText().split("\n")
        numbered = "\n".join(f"{i + 1:>4}| {l}" for i, l in enumerate(lines))
        parts = []
        for path, model in self.all_models().items():
            owners = ", ".join(c for _, _, p, c in self._class_ranges if p == path)
            widgets = "\n".join(f"- {n.name}: {n.cls} ({n.position_text()})"
                                 for n in model.nodes.values() if n.kind != "layout")
            parts.append(f"<ui_widgets file='{path.name}'" + (f" used_by_class='{owners}'" if owners else "")
                         + f">\n{widgets}\n</ui_widgets>")
        return (f"<code file='{self.py_path.name if self.py_path else 'Main.py'}'>\n{numbered}\n</code>\n"
                + ("\n".join(parts) or "<ui_widgets>(없음)</ui_widgets>"))

    def ai_explain(self):
        if not self.py_path:
            return
        cur = self.editor.textCursor()
        doc = self.editor.document()
        if cur.hasSelection():
            a = doc.findBlock(cur.selectionStart()).blockNumber()
            b = doc.findBlock(cur.selectionEnd()).blockNumber()
        else:
            a = b = cur.blockNumber()
        lines = self.editor.toPlainText().split("\n")[a:b + 1]
        code = "\n".join(f"{a + i + 1:>4}| {l}" for i, l in enumerate(lines))
        title = f"{a + 1}줄 설명" if a == b else f"{a + 1}~{b + 1}줄 설명"
        self.explain_tabs.setCurrentWidget(self.ai_panel)
        self.ai_panel.start(self._ai_context(), ai.EXPLAIN_TASK.format(code=code), title)

    def ai_review(self):
        if not self.py_path:
            return
        if self.editor.document().isModified():
            self.save_py()
        self.explain_tabs.setCurrentWidget(self.ai_panel)
        self.ai_panel.start(self._ai_context(), ai.REVIEW_TASK, f"{self.py_path.name} 전체 리뷰")

    def free_ai(self):
        from .freeai import FreeAiDialog
        dlg = FreeAiDialog(self)
        dlg.exec_()
        self._update_ai_status()
        if dlg.done_ok:
            self.ai_panel.show_welcome()
            self.explain_tabs.setCurrentWidget(self.ai_panel)
            self._status("무료 AI(Gemini)가 연결됐어요. 코드를 선택하고 Ctrl+E를 눌러 보세요.", 10000)

    def ai_settings(self):
        if AiSettingsDialog(self).exec_():
            self._update_ai_status()
            if not self.ai_panel.history:
                self.ai_panel.show_welcome()
            else:
                self.ai_panel.b_model.setText(f"AI: {ai.short_name(ai.get_model())} · 설정")

    def _update_ai_status(self):
        m = ai.get_model()
        self.ai_status.setText(f"AI: {ai.short_name(m)}" if ai.ready(m)
                               else "AI: 설정 필요 (AI 메뉴 → 모델·키 설정)")
