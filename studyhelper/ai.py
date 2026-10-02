"""AI 해설 / 코드 리뷰: Claude, GPT, Gemini, 내 PC의 Ollama.

Keys are the user's own and live in Windows Credential Manager (keyring), one per provider.
"""
import json
import os
import shutil
import subprocess
import urllib.request

from PyQt5.QtCore import QSettings, QThread, pyqtSignal

SERVICE = "PyQtStudyHelper"
_NO_WINDOW = 0x08000000          # CREATE_NO_WINDOW: no console flash when running claude.exe
OLLAMA_URL = "http://localhost:11434"

PROVIDERS = {
    "claude": dict(name="Claude (Anthropic)", key_name="api_key", env=("ANTHROPIC_API_KEY",),
                   key_page="https://console.anthropic.com/settings/keys", package="anthropic",
                   hint="sk-ant-..."),
    "openai": dict(name="GPT (OpenAI)", key_name="openai_key", env=("OPENAI_API_KEY",),
                   key_page="https://platform.openai.com/api-keys", package="openai", hint="sk-..."),
    "gemini": dict(name="Gemini (Google)", key_name="gemini_key", env=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
                   key_page="https://aistudio.google.com/apikey", package="google.genai", hint="AIza..."),
    "ollama": dict(name="내 PC (Ollama)", key_name=None, env=(), key_page="https://ollama.com/download",
                   package="openai", hint=""),
    "web": dict(name="웹 AI (무료 · 키 필요 없음)", key_name=None, env=(), key_page="",
                package=None, hint=""),
    "claudecode": dict(name="Claude Code 구독 (내 PC)", key_name=None, env=(), key_page="",
                       package=None, hint=""),
}

CLAUDE_CODE_MODEL = "cc:claude"        # the Claude Code installed on this PC, signed in with the user's own plan

# Free web chats: the helper copies the question to the clipboard and opens the site;
# the user pastes it there. No API, no key, nothing unofficial.
WEB_TARGETS = [
    ("web:chatgpt", "ChatGPT 웹 — 무료 계정으로 사용", "https://chatgpt.com/"),
    ("web:gemini", "Gemini 웹 — 무료 계정으로 사용", "https://gemini.google.com/app"),
    ("web:claude", "Claude 웹 — 무료 계정으로 사용", "https://claude.ai/new"),
]

# (model id, label, provider, free?)  — checked against each provider's model docs, 2026-10
MODELS = [
    ("gemini-3.8-flash", "Gemini 3.8 Flash — 무료 티어 · 빠르고 똑똑함 (추천)", "gemini", True),
    ("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite — 무료 티어 · 가장 빠름", "gemini", True),
    ("gemini-3.1-pro-preview", "Gemini 3.1 Pro (미리보기) — 유료", "gemini", False),
    ("claude-opus-5-5", "Claude Opus 5.5 — 가장 정확", "claude", False),
    ("claude-sonnet-5-5", "Claude Sonnet 5.5 — 빠르고 더 저렴", "claude", False),
    ("claude-haiku-4-5", "Claude Haiku 4.5 — 가장 빠르고 저렴", "claude", False),
    ("gpt-6-astra", "GPT-6 Astra — OpenAI 최고 성능 · 비쌈", "openai", False),
    ("gpt-6.1-sol", "GPT-6.1 Sol — 성능·가격 균형", "openai", False),
    ("gpt-6-luna", "GPT-6 Luna — 아주 저렴", "openai", False),
]
DEFAULT_MODEL = "web:chatgpt"          # works for everyone right after install (no key)
OLLAMA_SUGGEST = "qwen3:8b"

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


# ------------------------------------------------------------------ models
def provider_of(model: str) -> str:
    if model.startswith("web:"):
        return "web"
    if model.startswith("cc:"):
        return "claudecode"
    for mid, _, prov, _ in MODELS:
        if mid == model:
            return prov
    if model.startswith("ollama:"):
        return "ollama"
    if model.startswith("claude"):
        return "claude"
    if model.startswith("gemini"):
        return "gemini"
    return "openai"                     # gpt-*, o* and other custom ids


def label_of(model: str) -> str:
    for mid, label, _, _ in MODELS:
        if mid == model:
            return label
    for mid, label, _ in WEB_TARGETS:
        if mid == model:
            return label
    if model.startswith("ollama:"):
        return f"{model[7:]} — 내 PC · 완전 무료"
    if model == CLAUDE_CODE_MODEL:
        return "Claude Code — 내 Claude 구독으로 (API 키 필요 없음)"
    return model


def short_name(model: str) -> str:
    """For buttons / status bar."""
    if model.startswith("web:"):
        return {"web:chatgpt": "ChatGPT 웹", "web:gemini": "Gemini 웹", "web:claude": "Claude 웹"}.get(model, model)
    return model.replace("ollama:", "내 PC ")


# ------------------------------------------------------------ Claude Code (subscription)
def find_claude() -> str | None:
    """claude.exe: PATH -> common install places -> inside the Claude desktop app (newest version)."""
    import glob
    import re
    home = os.path.expanduser("~")
    local, roam = os.environ.get("LOCALAPPDATA", ""), os.environ.get("APPDATA", "")
    cands = [shutil.which("claude.exe") or "",
             os.path.join(home, ".local", "bin", "claude.exe"),
             os.path.join(local, "Microsoft", "WinGet", "Links", "claude.exe"),
             os.path.join(local, "Programs", "claude", "claude.exe"),
             os.path.join(home, ".claude", "local", "claude.exe"),
             os.path.join(roam, "npm", "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe")]
    roots = [os.path.join(roam, "Claude", "claude-code")]
    # Microsoft Store install keeps %APPDATA% data under Packages\Claude_*\LocalCache
    roots += glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude", "claude-code"))
    versions = []
    for r in roots:
        try:
            for v in os.listdir(r):
                if re.fullmatch(r"\d+\.\d+\.\d+", v):
                    key = tuple(map(int, v.split(".")))
                    vdir = os.path.join(r, v)
                    # older apps: <version>\claude.exe ; newer: <version>\<hash>\claude.exe
                    versions.append((key, os.path.join(vdir, "claude.exe")))
                    for sub in glob.glob(os.path.join(vdir, "*", "claude.exe")):
                        versions.append((key, sub))
        except OSError:
            pass
    cands += [p for _, p in sorted(versions, reverse=True)]       # newest version first
    return next((p for p in cands if p and os.path.isfile(p)), None)


def _clean_env() -> dict:
    """Make Claude Code use the subscription login, not a leftover API key."""
    return {k: v for k, v in os.environ.items()
            if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")}


def claude_code_status() -> tuple[bool, str]:
    """(usable, message) — installed? signed in? Sends no question."""
    exe = find_claude()
    if not exe:
        return False, ("이 PC에서 Claude Code(claude.exe)를 찾지 못했어요. Claude 데스크톱 앱 또는 Claude Code를 "
                       "설치하고 로그인한 뒤 다시 시도해 주세요.")
    try:
        r = subprocess.run([exe, "auth", "status"], capture_output=True, timeout=30, env=_clean_env(),
                           creationflags=_NO_WINDOW)
        data = json.loads(r.stdout.decode("utf-8", "replace") or "{}")
    except Exception as e:
        return False, f"Claude Code 상태를 확인하지 못했어요: {e}"
    if data.get("loggedIn"):
        return True, "Claude Code에 로그인돼 있어요."
    return False, "Claude Code에 로그인돼 있지 않아요. [로그인 창 열기]를 눌러 한 번 로그인해 주세요."


def open_claude_login() -> bool:
    exe = find_claude()
    if not exe:
        return False
    subprocess.Popen(["cmd.exe", "/c", "start", "Claude Code 로그인", exe, "auth", "login"],
                     creationflags=_NO_WINDOW)
    return True


def web_url(model: str) -> str:
    return next((u for mid, _, u in WEB_TARGETS if mid == model), WEB_TARGETS[0][2])


def web_prompt(context: str, task: str) -> str:
    """One message to paste into a web chat: tutor instructions + code + request."""
    return f"{SYSTEM}\n\n아래는 학생의 코드와 .ui 위젯 목록이에요.\n\n{context}\n\n{task}"


def ollama_models() -> list[str]:
    """Models installed in a running Ollama (empty when Ollama isn't running)."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=1) as r:
            return [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        return []


# ---------------------------------------------------------------- key storage
def _keyring():
    try:
        import keyring
        return keyring
    except Exception:
        return None


def get_key(provider: str) -> str:
    p = PROVIDERS[provider]
    if p["key_name"] is None:
        return "local"
    for e in p["env"]:
        if os.environ.get(e, "").strip():
            return os.environ[e].strip()
    kr = _keyring()
    if kr:
        try:
            return kr.get_password(SERVICE, p["key_name"]) or ""
        except Exception:
            pass
    return QSettings(SERVICE, SERVICE).value(f"ai/{p['key_name']}", "") or ""


def key_source(provider: str) -> str:
    for e in PROVIDERS[provider]["env"]:
        if os.environ.get(e, "").strip():
            return f"환경변수 {e}"
    return "Windows 자격 증명 관리자" if _keyring() else "이 PC의 사용자 설정"


def set_key(provider: str, key: str):
    name = PROVIDERS[provider]["key_name"]
    if name is None:
        return
    key = key.strip()
    kr = _keyring()
    if kr:
        try:
            if key:
                kr.set_password(SERVICE, name, key)
            else:
                try:
                    kr.delete_password(SERVICE, name)
                except Exception:
                    pass
            return
        except Exception:
            pass
    QSettings(SERVICE, SERVICE).setValue(f"ai/{name}", key)


def get_model() -> str:
    return QSettings(SERVICE, SERVICE).value("ai/model", DEFAULT_MODEL) or DEFAULT_MODEL


def set_model(model: str):
    QSettings(SERVICE, SERVICE).setValue("ai/model", model.strip())


def package_ok(provider: str) -> bool:
    """Installed? (find_spec doesn't import — importing google.genai alone takes ~1 s)"""
    import importlib.util
    pkg = PROVIDERS[provider]["package"]
    if pkg is None:
        return True
    try:
        return importlib.util.find_spec(pkg) is not None
    except (ImportError, ValueError):
        return False


def ready(model: str | None = None) -> bool:
    model = model or get_model()
    prov = provider_of(model)
    if prov == "claudecode":
        return find_claude() is not None
    return package_ok(prov) and bool(get_key(prov))


# ------------------------------------------------------------------ errors
def friendly_error(provider: str, e: Exception) -> str:
    if type(e) is RuntimeError:          # our own, already friendly
        return str(e)
    name = type(e).__name__
    msg = str(getattr(e, "message", "") or e)
    low = msg.lower()
    status = getattr(e, "status_code", None) or getattr(e, "code", None)
    if provider == "ollama" and ("connect" in name.lower() or "connection" in low):
        return ("Ollama가 실행 중이 아니에요. ollama.com 에서 설치한 뒤, 명령창에서 "
                f"`ollama pull {OLLAMA_SUGGEST}` 로 모델을 받아 주세요.")
    if name in ("APIConnectionError", "ConnectError", "ConnectTimeout") or "connection" in name.lower():
        return "인터넷에 연결할 수 없어요. 네트워크를 확인해 주세요."
    if status == 401 or name == "AuthenticationError" or "api_key_invalid" in low or "api key not valid" in low:
        return "API 키가 올바르지 않아요. 설정에서 키를 다시 확인해 주세요."
    if status == 403 or name == "PermissionDeniedError":
        return "이 키로는 이 모델을 쓸 권한이 없어요. 다른 모델을 골라 보세요."
    if status == 404 or name == "NotFoundError":
        if provider == "ollama":
            return f"내 PC에 그 모델이 없어요. 명령창에서 `ollama pull {OLLAMA_SUGGEST}` 처럼 받아 주세요."
        return "모델을 찾지 못했어요. 설정에서 다른 모델을 골라 보세요."
    if status == 429 or name == "RateLimitError":
        if "quota" in low or "billing" in low or "credit" in low:
            if provider == "gemini":
                return "무료 사용량을 다 썼어요(분당/하루 한도). 잠시 뒤에 하거나 내일 다시 시도해 주세요."
            return "API 크레딧(잔액)이 부족해요. 결제 페이지에서 충전해 주세요."
        return "요청이 너무 많아요. 잠시 뒤에 다시 시도해 주세요."
    if "credit" in low or "balance" in low or "billing" in low:
        return "API 크레딧(잔액)이 부족해요. 결제 페이지에서 충전해 주세요."
    if isinstance(status, int) and status >= 500:
        return f"AI 서버 오류({status})예요. 잠시 뒤에 다시 시도해 주세요."
    if isinstance(status, int) and status >= 400:
        return f"요청이 거절됐어요 ({status}): {msg[:300]}"
    return f"{name}: {msg[:300]}"


def test_key(model: str, key: str) -> str | None:
    """None when the key + model work. Costs no tokens."""
    prov = provider_of(model)
    try:
        if prov == "claude":
            import anthropic
            anthropic.Anthropic(api_key=key, max_retries=0, timeout=15).models.retrieve(model)
        elif prov == "openai":
            from openai import OpenAI
            OpenAI(api_key=key, max_retries=0, timeout=15).models.retrieve(model)
        elif prov == "gemini":
            from google import genai
            client = genai.Client(api_key=key)          # keep a reference: a dropped client closes itself
            client.models.get(model=model)
        elif prov == "claudecode":
            ok, msg = claude_code_status()
            return None if ok else msg
        else:
            names = ollama_models()
            if not names and not _ollama_running():
                return friendly_error("ollama", ConnectionError("connection refused"))
            if model[7:] not in names:
                return f"내 PC에 '{model[7:]}' 모델이 없어요. 명령창: ollama pull {model[7:]}"
        return None
    except ImportError:
        return f"{PROVIDERS[prov]['package']} 패키지가 없어요. install.bat 을 다시 실행해 주세요."
    except Exception as e:
        return friendly_error(prov, e)


def _ollama_running() -> bool:
    try:
        urllib.request.urlopen(OLLAMA_URL, timeout=1)
        return True
    except Exception:
        return False


# ------------------------------------------------------------------- worker
class AiWorker(QThread):
    """Streams one answer. `history`: [{'role': 'user'|'assistant', 'content': str, 'raw': ...}]"""
    chunk = pyqtSignal(str)
    done = pyqtSignal(str, object)   # full text, provider-specific raw content (Claude blocks)
    failed = pyqtSignal(str)

    def __init__(self, model, history, parent=None):
        super().__init__(parent)
        self.model, self.history = model, history
        self.provider = provider_of(model)
        self._stop = False
        self._text = ""

    def stop(self):
        self._stop = True
        proc = getattr(self, "_proc", None)
        if proc is not None and proc.poll() is None:
            proc.kill()

    def _emit(self, t):
        if t:
            self._text += t
            self.chunk.emit(t)

    def run(self):
        try:
            raw = getattr(self, f"_run_{self.provider}")()
            if not self._stop:
                self.done.emit(self._text, raw)
        except Exception as e:
            if not self._stop:
                self.failed.emit(friendly_error(self.provider, e))

    # --- Claude -------------------------------------------------------------
    def _run_claude(self):
        import anthropic
        client = anthropic.Anthropic(api_key=get_key("claude"))
        messages = [{"role": m["role"], "content": m.get("raw") or m["content"]} for m in self.history]
        kw = dict(model=self.model, max_tokens=16000, system=SYSTEM, messages=messages,
                  cache_control={"type": "ephemeral"})   # follow-up questions reuse the cached code
        if self.model != "claude-haiku-4-5":
            kw["output_config"] = {"effort": "medium"}
            # if a safety classifier declines, retry on Anthropic's recommended fallback model
            kw["betas"] = ["server-side-fallback-2026-07-01"]
            kw["fallbacks"] = "default"
        with client.beta.messages.stream(**kw) as stream:
            for event in stream:
                if self._stop:
                    return None
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    self._emit(event.delta.text)
            final = stream.get_final_message()
        if final.stop_reason == "refusal":
            raise RuntimeError("이 요청에는 답할 수 없다는 응답을 받았어요. 질문을 바꿔 보세요.")
        if final.stop_reason == "max_tokens":
            self._emit("\n\n*(답변이 길어 잘렸어요. '이어서 설명해 줘'라고 질문해 보세요.)*")
        return final.content          # keep blocks as-is for the next turn

    # --- Claude Code (the user's own subscription, no API key) ----------------------
    def _run_claudecode(self):
        import tempfile
        exe = find_claude()
        if not exe:
            raise RuntimeError(claude_code_status()[1])
        empty = os.path.join(tempfile.gettempdir(), "PyQtStudyHelper_claude")      # no project files to read
        os.makedirs(empty, exist_ok=True)
        # answer only: no tools, no MCP, no settings/CLAUDE.md, nothing saved
        args = [exe, "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                "--tools", "", "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence",
                "--disable-slash-commands", "--system-prompt", SYSTEM]
        past = self.history[:-1]
        text = self.history[-1]["content"]
        if past:        # -p is stateless: replay the conversation as text
            text = ("[이전 대화]\n" + "\n\n".join(
                f"{'학생' if m['role'] == 'user' else '튜터'}: {m['content']}" for m in past)
                + f"\n\n[새 질문]\n{text}")
        self._proc = subprocess.Popen(args, cwd=empty, env=_clean_env(), stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=_NO_WINDOW)
        self._proc.stdin.write(text.encode("utf-8"))
        self._proc.stdin.close()
        for raw in self._proc.stdout:
            if self._stop:
                return None
            try:
                m = json.loads(raw.decode("utf-8"))
            except ValueError:
                continue
            if m.get("type") == "stream_event":
                ev = m.get("event") or {}
                d = ev.get("delta") or {}
                if ev.get("type") == "content_block_delta" and d.get("type") == "text_delta":
                    self._emit(d.get("text", ""))
            elif m.get("type") == "result":
                result = m.get("result") or ""
                if "not logged in" in result.lower():
                    raise RuntimeError("Claude Code에 로그인돼 있지 않아요. 설정에서 [로그인 창 열기]를 눌러 주세요.")
                if m.get("is_error"):
                    raise RuntimeError(f"Claude Code 오류: {result[:300]}")
                if not self._text and result:
                    self._emit(result)
                return None
        if not self._stop:
            err = self._proc.stderr.read().decode("utf-8", "replace").strip()
            raise RuntimeError(err[:300] or f"Claude Code가 종료됐어요 (코드 {self._proc.wait()})")
        return None

    # --- OpenAI (Responses API) ---------------------------------------------------
    def _run_openai(self):
        from openai import OpenAI
        client = OpenAI(api_key=get_key("openai"))
        inp = [{"role": m["role"], "content": m["content"]} for m in self.history]
        with client.responses.stream(model=self.model, instructions=SYSTEM, input=inp) as stream:
            for event in stream:
                if self._stop:
                    return None
                if event.type == "response.output_text.delta":
                    self._emit(event.delta)
        return None

    # --- Gemini ------------------------------------------------------------------
    def _run_gemini(self):
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=get_key("gemini"))
        contents = [types.Content(role="model" if m["role"] == "assistant" else "user",
                                  parts=[types.Part(text=m["content"])]) for m in self.history]
        cfg = types.GenerateContentConfig(
            system_instruction=SYSTEM,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        for ch in client.models.generate_content_stream(model=self.model, contents=contents, config=cfg):
            if self._stop:
                return None
            self._emit(ch.text or "")
        return None

    # --- Ollama (local, OpenAI-compatible endpoint) --------------------------------
    def _run_ollama(self):
        from openai import OpenAI
        client = OpenAI(base_url=f"{OLLAMA_URL}/v1", api_key="ollama", timeout=600)
        msgs = [{"role": "system", "content": SYSTEM}] + \
               [{"role": m["role"], "content": m["content"]} for m in self.history]
        for ch in client.chat.completions.create(model=self.model[7:], messages=msgs, stream=True):
            if self._stop:
                return None
            if ch.choices and ch.choices[0].delta.content:
                self._emit(ch.choices[0].delta.content)
        return None
