"""PyQt 학습 도우미 실행: python run.py [Main.py | gui.ui | 폴더]"""
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from studyhelper.mainwindow import MainWindow


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    target = sys.argv[1] if len(sys.argv) > 1 else w.settings.value("lastFile", "")
    if not (target and w.open_path(target)):
        w.open_dialog()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
