"""PyQt 학습 도우미 실행: python run.py [Main.py | gui.ui | 폴더]"""
import os
import sys
import traceback
from pathlib import Path

LOG = Path(__file__).with_name("error.log")


def fix_qt_plugin_path():
    """A stale QT_QPA_PLATFORM_PLUGIN_PATH (system env on this PC) stops Qt from starting."""
    import PyQt5
    base = Path(PyQt5.__file__).parent
    for cand in (base / "Qt5" / "plugins", base / "Qt" / "plugins"):
        if (cand / "platforms").is_dir():
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(cand / "platforms")
            return
    os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)


def excepthook(etype, value, tb):
    """pythonw has no console: log the error and show it instead of silently dying."""
    text = "".join(traceback.format_exception(etype, value, tb))
    try:
        LOG.write_text(text, encoding="utf-8")
    except OSError:
        pass
    from PyQt5.QtWidgets import QApplication, QMessageBox
    if QApplication.instance() is not None:
        QMessageBox.critical(None, "PyQt 학습 도우미 오류",
                             f"예상치 못한 오류가 났어요. (내용은 {LOG.name} 에 저장)\n\n{text[-1500:]}")


def main():
    fix_qt_plugin_path()
    sys.excepthook = excepthook

    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication
    from studyhelper.mainwindow import MainWindow

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("PyQt 학습 도우미")
    app.setStyle("Fusion")
    font = app.font()
    font.setFamily("Malgun Gothic")
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(STYLE)
    w = MainWindow()
    w.show()
    # with a file argument (dropped on the icon / launcher .bat) open it; otherwise the start screen
    if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
        w.open_path(sys.argv[1])
    sys.exit(app.exec_())


STYLE = """
QLabel#paneTitle { background: #eef2f8; color: #1f3a5f; border-bottom: 1px solid #d3dce9; padding: 1px 4px; }
QPushButton#bigButton { font-size: 12pt; padding: 10px 18px; background: #2f6fd0; color: white;
                        border: none; border-radius: 6px; }
QPushButton#bigButton:hover { background: #255db3; }
QWidget#welcome { background: #fafbfd; }
QToolBar { spacing: 4px; padding: 3px; border-bottom: 1px solid #d9dfe7; }
QToolButton { padding: 4px 8px; border: 1px solid transparent; border-radius: 4px; }
QToolButton:hover { background: #e6eefb; border-color: #c4d4ee; }
QToolButton:disabled { color: #aaa; }
QSplitter::handle { background: #e3e8ef; }
QSplitter::handle:hover { background: #9db8e6; }
QSplitter::handle:horizontal { width: 3px; }
QSplitter::handle:vertical { height: 3px; }
QLabel#explorerTitle { padding-left: 2px; }
QLabel#explorerHint { font-size: 9pt; }
QPushButton:flat { border: none; padding: 3px 5px; border-radius: 4px; }
QPushButton:flat:hover { background: #e6eefb; }
QTabWidget::pane { border: 1px solid #d3dce9; top: -1px; }
QTabBar::tab:selected { font-weight: bold; }
QTabBar::tab { padding: 5px 14px; }
QStatusBar QLabel { color: #555; padding: 0 6px; }
QWidget#tips { background: #fff8e1; border-bottom: 1px solid #f0dca0; }
QWidget#findBar { background: #f7f8fa; border-top: 1px solid #dde3ea; }
QLabel#legend { background: #f7f8fa; border-top: 1px solid #dde3ea; padding: 3px 6px; font-size: 9pt; }
"""


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()
