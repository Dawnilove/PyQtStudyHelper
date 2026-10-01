"""Find the user's own Obsidian lecture notes about a Qt class and open them in Obsidian."""
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

_cache: dict[Path, tuple[float, str]] = {}


@dataclass
class Hit:
    path: Path
    heading: str        # nearest heading ('' = top of note)
    count: int
    in_heading: bool    # the term itself appears in a heading


def find_vault(start) -> Path | None:
    """The Obsidian vault containing `start` (folder with .obsidian)."""
    p = Path(start).resolve()
    for d in [p] + list(p.parents):
        if (d / ".obsidian").is_dir():
            return d
    return None


def _text(path: Path) -> str:
    mt = path.stat().st_mtime
    c = _cache.get(path)
    if c is None or c[0] != mt:
        c = (mt, path.read_text(encoding="utf-8", errors="replace"))
        _cache[path] = c
    return c[1]


def _note_files(vault: Path) -> list[Path]:
    """PyQt note folders first (e.g. 'PyQT 강의 노트'), skipping hidden folders."""
    files = [p for p in vault.rglob("*.md")
             if not any(part.startswith(".") for part in p.relative_to(vault).parts)]
    return sorted(files, key=lambda p: ("pyq" not in str(p.relative_to(vault)).lower(), str(p)))


def search(vault: Path, term: str, limit: int = 8) -> list[Hit]:
    if not vault or not term:
        return []
    rx = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])")
    hits = []
    for f in _note_files(vault):
        try:
            text = _text(f)
        except OSError:
            continue
        n = len(rx.findall(text))
        if not n:
            continue
        heading, in_heading = "", False
        current = ""
        for line in text.splitlines():
            m = re.match(r"^#{1,4}\s+(.*)", line)
            if m:
                current = m.group(1).strip()
                if rx.search(current):
                    heading, in_heading = current, True
                    break
            elif rx.search(line) and not heading:
                heading = current
        hits.append(Hit(f, heading, n, in_heading))
    pyq = lambda h: "pyq" in str(h.path.relative_to(vault)).lower()
    hits.sort(key=lambda h: (not pyq(h), not h.in_heading, -h.count))
    return hits[:limit]


def label(vault: Path, hit: Hit) -> str:
    name = hit.path.stem
    return f"{name} › {hit.heading}" if hit.heading else name


def obsidian_url(vault: Path, hit: Hit) -> str:
    """obsidian:// link when the folder is an Obsidian vault, else a plain file link."""
    if not (vault / ".obsidian").is_dir():
        return hit.path.resolve().as_uri()
    rel = hit.path.relative_to(vault).with_suffix("").as_posix()
    target = f"{rel}#{hit.heading}" if hit.heading else rel
    return f"obsidian://open?vault={quote(vault.name)}&file={quote(target)}"
