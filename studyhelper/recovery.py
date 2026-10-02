"""저장하지 않은 코드의 임시 백업. If the app or PC dies before saving, the next open offers to restore."""
import hashlib
import os
from pathlib import Path


def _dir() -> Path:
    d = os.environ.get("PYQTSTUDY_RECOVERY_DIR")
    base = Path(d) if d else Path(os.environ.get("APPDATA") or Path.home()) / "PyQtStudyHelper" / "recovery"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _file(path) -> Path:
    key = hashlib.sha1(os.path.normcase(os.path.abspath(str(path))).encode("utf-8")).hexdigest()[:16]
    return _dir() / f"{key}.bak"


def save(path, text: str) -> None:
    try:
        _file(path).write_text(text, encoding="utf-8", newline="")
    except OSError:
        pass


def clear(path) -> None:
    try:
        _file(path).unlink()
    except OSError:
        pass


def load(path, current_text: str):
    """Backup text if there is one that differs from what's on disk, else None."""
    try:
        f = _file(path)
        if not f.exists():
            return None
        text = f.read_text(encoding="utf-8")
    except OSError:
        return None
    if text.replace("\r\n", "\n") == current_text.replace("\r\n", "\n"):
        clear(path)
        return None
    return text
