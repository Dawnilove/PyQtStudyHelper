"""Build dist/PyQtStudyHelper-Setup-<version>.exe  (one file: embedded Python + packages + the app).

Needs: Inno Setup 6 (ISCC.exe), internet for the first run (embeddable Python + pip packages).
Run from the project folder:  python tools/build_installer.py
"""
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
STAGE = BUILD / "stage"                       # exactly what gets installed into {app}
PY_VERSION = "3.12.10"                        # the embeddable Python must match the pip wheels' cp312
PY_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
ISCC_CANDIDATES = (
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
)
APP_FILES = ("run.py", "LICENSE", "README.md", "requirements.txt")


def version() -> str:
    text = (ROOT / "studyhelper" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)


def step(msg):
    print(f"\n== {msg}", flush=True)


def fetch_python() -> Path:
    BUILD.mkdir(exist_ok=True)
    zip_path = BUILD / f"python-{PY_VERSION}-embed-amd64.zip"
    if not zip_path.exists():
        step(f"Downloading {PY_URL}")
        urllib.request.urlretrieve(PY_URL, zip_path)
    return zip_path


def make_stage(zip_path: Path):
    step("Collecting Python + packages + app into build/stage")
    if STAGE.exists():
        shutil.rmtree(STAGE)
    py = STAGE / "python"
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(py)
    # python312._pth: add site-packages (and "import site"); the app folder is the script's own folder
    pth = next(py.glob("python*._pth"))
    pth.write_text("\n".join([pth.stem.replace("._pth", "") + ".zip", ".", r"Lib\site-packages",
                              "import site"]) + "\n", encoding="utf-8")
    site = py / "Lib" / "site-packages"
    site.mkdir(parents=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-warn-script-location", "--only-binary=:all:",
                    "--target", str(site), "-r", str(ROOT / "requirements.txt"), "PyQt5Designer"], check=True)
    for f in APP_FILES:
        shutil.copy2(ROOT / f, STAGE / f)
    shutil.copytree(ROOT / "studyhelper", STAGE / "studyhelper", ignore=shutil.ignore_patterns("__pycache__"))
    for cache in STAGE.rglob("__pycache__"):          # pip's caches only bloat the installer
        shutil.rmtree(cache, ignore_errors=True)


def make_icon():
    """A simple app icon drawn with Qt (the project ships no image files)."""
    step("Drawing build/app.ico")
    from PyQt5.QtCore import QRectF, Qt
    from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPainterPath
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    img = QImage(256, 256, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(8, 8, 240, 240), 52, 52)
    p.fillPath(path, QColor("#3b6fd4"))
    p.setPen(QColor("white"))
    f = QFont("Segoe UI", 100)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(0, 0, 256, 256), Qt.AlignCenter, "Py")
    p.end()
    ico = BUILD / "app.ico"
    img.save(str(ico), "ICO")
    del app
    return ico


def compile_installer(ico: Path) -> Path:
    iscc = next((c for c in ISCC_CANDIDATES if c.exists()), None) or shutil.which("ISCC")
    if not iscc:
        sys.exit("Inno Setup 6 (ISCC.exe) was not found. Install it from https://jrsoftware.org/isinfo.php")
    step("Compiling the installer with Inno Setup")
    (ROOT / "dist").mkdir(exist_ok=True)
    subprocess.run([str(iscc), f"/DAppVersion={version()}", f"/DStageDir={STAGE}", f"/DIconFile={ico}",
                    f"/DOutDir={ROOT / 'dist'}", str(ROOT / "installer" / "PyQtStudyHelper.iss")], check=True)
    return ROOT / "dist" / f"PyQtStudyHelper-Setup-{version()}.exe"


def main():
    sys.stdout.reconfigure(errors="replace")
    make_stage(fetch_python())
    out = compile_installer(make_icon())
    print(f"\nDone: {out}  ({out.stat().st_size / 1_048_576:.0f} MB)")


if __name__ == "__main__":
    main()
