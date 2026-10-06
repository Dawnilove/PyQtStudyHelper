"""학습 기록: 공부한 날, 실행 횟수, 살펴본 위젯 클래스, 만난 에러, 푼 과제·도전.

Kept only on this PC (%APPDATA%/PyQtStudyHelper/learning.json); nothing is sent anywhere.
Every function is safe to call often and never raises (a broken log must not break the app).
"""
import functools
import json
import os
from datetime import date, datetime
from pathlib import Path

_cache = None


def _file() -> Path:
    d = os.environ.get("PYQTSTUDY_LOG_DIR")
    base = Path(d) if d else Path(os.environ.get("APPDATA") or Path.home()) / "PyQtStudyHelper"
    return base / "learning.json"


def path() -> Path:
    """Where the log is kept (shown to the student)."""
    return _file()


def _empty() -> dict:
    return {"days": [], "runs": 0, "files": [], "widgets": {}, "errors": {}, "tasks": {}, "challenges": {}}


def load() -> dict:
    global _cache
    if _cache is None:
        _cache = _empty()
        try:
            data = json.loads(_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if isinstance(data, dict):                 # keep only the parts that have the expected shape
            for k, v in _empty().items():
                if isinstance(data.get(k), type(v)):
                    _cache[k] = data[k]
    return _cache


def _safe(fn):
    """A broken log (hand-edited file, full disk …) must never break the app."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            return None
    return wrapper


def _save():
    try:
        f = _file()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(load(), ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(f)
    except OSError:
        pass


def _today():
    d = load()
    t = date.today().isoformat()
    if t not in d["days"]:
        d["days"].append(t)


@_safe
def note_open(path):
    d = load()
    _today()
    p = os.path.normcase(os.path.abspath(str(path)))
    if p not in d["files"]:
        d["files"].append(p)
        del d["files"][:-500]
    _save()


@_safe
def note_run():
    d = load()
    _today()
    d["runs"] += 1
    _save()


@_safe
def note_widget(cls: str):
    """A widget of this class was looked at (clicked in the preview / tree)."""
    if not cls:
        return
    d = load()
    w = d["widgets"].setdefault(cls, {"count": 0, "first": date.today().isoformat()})
    w["count"] += 1
    _save()


@_safe
def note_error(kind: str):
    """The student's program ended with this error (e.g. 'AttributeError')."""
    if not kind:
        return
    d = load()
    e = d["errors"].setdefault(kind, {"count": 0, "last": ""})
    e["count"] += 1
    e["last"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _save()


@_safe
def note_task(task_id: str):
    d = load()
    _today()
    d["tasks"].setdefault(task_id, datetime.now().strftime("%Y-%m-%d %H:%M"))
    _save()


@_safe
def note_challenge(name: str):
    d = load()
    _today()
    d["challenges"].setdefault(name, datetime.now().strftime("%Y-%m-%d %H:%M"))
    _save()


def solved_tasks() -> dict:
    t = load()["tasks"]
    return {k: str(v) for k, v in t.items()}


def clear():
    global _cache
    _cache = _empty()
    try:
        _file().unlink()
    except OSError:
        pass


def reset_cache():
    """Forget what's in memory (tests, or another window changed the file)."""
    global _cache
    _cache = None
