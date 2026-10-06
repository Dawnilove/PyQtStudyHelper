""".ui 되돌리기. The helper writes .ui files itself (속성 표 값 고치기, objectName 바꾸기, 미리보기 편집);
before each write the old file is kept here so it can be put back. Kept in memory for this session."""
import os
from pathlib import Path

MAX_STEPS = 30
_stacks: dict[str, list[tuple[str, bytes]]] = {}     # normalized path -> [(what was done, old bytes)]


def _key(path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def snapshot(path, label: str) -> bool:
    """Remember the .ui as it is now, before `label` changes it. False if the file couldn't be read."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return False
    stack = _stacks.setdefault(_key(path), [])
    stack.append((label, data))
    del stack[:-MAX_STEPS]
    return True


def last_label(path) -> str | None:
    stack = _stacks.get(_key(path))
    return stack[-1][0] if stack else None


def undo(path) -> str | None:
    """Put the last remembered version back. Returns what was undone (None if nothing)."""
    stack = _stacks.get(_key(path))
    if not stack:
        return None
    label, data = stack.pop()
    Path(path).write_bytes(data)
    return label


def discard(path) -> None:
    """Forget the last snapshot (the change it was taken for didn't happen)."""
    stack = _stacks.get(_key(path))
    if stack:
        stack.pop()


def clear(path=None) -> None:
    if path is None:
        _stacks.clear()
    else:
        _stacks.pop(_key(path), None)
