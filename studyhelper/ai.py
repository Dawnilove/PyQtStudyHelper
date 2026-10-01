"""AI 해설 / 코드 리뷰 (Claude API). The user's own API key lives in Windows Credential Manager."""
import os

from PyQt5.QtCore import QSettings, QThread, pyqtSignal

SERVICE = "PyQtStudyHelper"
MODELS = [
    ("claude-opus-5-5", "Claude Opus 5.5 — 가장 정확 (기본)"),
    ("claude-sonnet-5-5", "Claude Sonnet 5.5 — 빠르고 더 저렴"),
    ("claude-haiku-4-5", "Claude Haiku 4.5 — 가장 빠르고 저렴"),
]
DEFAULT_MODEL = MODELS[0][0]
KEY_PAGE = "https://console.anthropic.com/settings/keys"

SYSTEM = """당신은 PyQt5를 처음 배우는 학생을 돕는 친절한 튜터입니다.
학생은 Qt Designer로 만든 .ui 파일을 pyuic로 변환해 Main.py에서 상속해 쓰는 방식으로 배우고 있습니다.

답변 규칙:
- 한국어로, 짧은 문장과 글머리표 위주로 답합니다. 긴 문단은 피합니다.
- 코드를 설명할 때는 "무엇을 하는지"와 "왜 이렇게 썼는지"를 꼭 구분해서 말합니다.
- 초보자가 자주 하는 실수나 함정이 있으면 "주의"로 짚어 줍니다.
- 줄을 언급할 때는 줄 번호를 붙입니다 (예: 23줄).
- self.이름 이 .ui의 위젯이면 어떤 위젯(클래스)인지 알려 줍니다. 위젯 목록은 <ui_widgets>에 있습니다.
- 학생이 직접 생각해 볼 수 있게, 전체 코드를 다시 써 주기보다 필요한 부분만 짧게 보여 줍니다.
- 모르는 것은 추측하지 말고 모른다고 말합니다."""

EXPLAIN_TASK = """아래 부분이 무엇을 하는지, 왜 이렇게 썼는지 설명해 주세요.
형식: ## 한 줄 요약 → ## 무엇을 하나요 → ## 왜 이렇게 썼나요 → ## 주의할 점 (해당될 때만)

```python
{code}
```"""

REVIEW_TASK = """Main.py 전체를 초보자 눈높이로 코드 리뷰해 주세요.
형식: ## 잘한 점 → ## 버그·실수 (실행하면 문제가 되는 것, 줄 번호와 함께) → ## 더 좋게 만들기 (2~4개, 짧은 예시 코드) → ## 다음에 공부할 것 (1~2개)
문제가 없으면 억지로 만들지 말고 없다고 말해 주세요."""


# ---------------------------------------------------------------- key storage
def get_key() -> str:
    env = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if env:
        return env
    try:
        import keyring
        return keyring.get_password(SERVICE, "api_key") or ""
    except Exception:
        return QSettings(SERVICE, SERVICE).value("ai/key_fallback", "") or ""


def key_source() -> str:
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return "환경변수 ANTHROPIC_API_KEY"
    return "Windows 자격 증명 관리자"


def set_key(key: str):
    key = key.strip()
    try:
        import keyring
        if key:
            keyring.set_password(SERVICE, "api_key", key)
        else:
            try:
                keyring.delete_password(SERVICE, "api_key")
            except Exception:
                pass
    except Exception:  # keyring unavailable: fall back to per-user settings
        QSettings(SERVICE, SERVICE).setValue("ai/key_fallback", key)


def get_model() -> str:
    m = QSettings(SERVICE, SERVICE).value("ai/model", DEFAULT_MODEL)
    return m if m in dict(MODELS) else DEFAULT_MODEL


def set_model(model: str):
    QSettings(SERVICE, SERVICE).setValue("ai/model", model)


def available() -> bool:
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def friendly_error(e: Exception) -> str:
    import anthropic
    if isinstance(e, anthropic.AuthenticationError):
        return "API 키가 올바르지 않아요. 설정에서 키를 다시 확인해 주세요."
    if isinstance(e, anthropic.PermissionDeniedError):
        return "이 API 키로는 이 모델을 쓸 권한이 없어요. 다른 모델을 골라 보세요."
    if isinstance(e, anthropic.NotFoundError):
        return "모델을 찾지 못했어요. 설정에서 다른 모델을 골라 보세요."
    if isinstance(e, anthropic.RateLimitError):
        return "요청이 너무 많아요. 잠시 뒤에 다시 시도해 주세요."
    if isinstance(e, anthropic.BadRequestError):
        msg = getattr(e, "message", str(e))
        if "credit" in msg.lower() or "balance" in msg.lower():
            return "API 크레딧(잔액)이 부족해요. Anthropic 콘솔의 Billing에서 충전해 주세요."
        return f"요청이 거절됐어요: {msg}"
    if isinstance(e, anthropic.APIStatusError):
        if e.status_code >= 500:
            return f"Anthropic 서버 오류({e.status_code})예요. 잠시 뒤에 다시 시도해 주세요."
        return f"API 오류({e.status_code}): {getattr(e, 'message', e)}"
    if isinstance(e, anthropic.APIConnectionError):
        return "인터넷에 연결할 수 없어요. 네트워크를 확인해 주세요."
    return f"{type(e).__name__}: {e}"


def test_key(key: str, model: str) -> str | None:
    """None when the key works, otherwise a friendly error. Costs no tokens."""
    try:
        import anthropic
        anthropic.Anthropic(api_key=key, max_retries=0, timeout=15).models.retrieve(model)
        return None
    except Exception as e:
        return friendly_error(e)


def request_kwargs(model: str) -> dict:
    kw = dict(model=model, max_tokens=16000, system=SYSTEM,
              cache_control={"type": "ephemeral"})          # follow-up questions reuse the cached code
    if model != "claude-haiku-4-5":
        kw["output_config"] = {"effort": "medium"}
        # if a safety classifier declines, retry on Anthropic's recommended fallback model
        kw["betas"] = ["server-side-fallback-2026-07-01"]
        kw["fallbacks"] = "default"
    return kw


# ------------------------------------------------------------------- worker
class AiWorker(QThread):
    chunk = pyqtSignal(str)
    done = pyqtSignal(object)        # assistant content blocks (to keep the conversation)
    failed = pyqtSignal(str)

    def __init__(self, key, model, messages, parent=None):
        super().__init__(parent)
        self.key, self.model, self.messages = key, model, messages
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.key)
            with client.beta.messages.stream(messages=self.messages,
                                             **request_kwargs(self.model)) as stream:
                for event in stream:
                    if self._stop:
                        return
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        self.chunk.emit(event.delta.text)
                final = stream.get_final_message()
            if final.stop_reason == "refusal":
                self.failed.emit("이 요청에는 답할 수 없다는 응답을 받았어요. 질문을 바꿔서 다시 시도해 보세요.")
                return
            if final.stop_reason == "max_tokens":
                self.chunk.emit("\n\n*(답변이 길어 여기서 잘렸어요. '이어서 설명해 줘'라고 질문해 보세요.)*")
            self.done.emit(final.content)
        except Exception as e:
            if not self._stop:
                self.failed.emit(friendly_error(e))
