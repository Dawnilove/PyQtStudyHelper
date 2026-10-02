"""Several Main.py files open at once: tabs keep unsaved edits when switching and ask when closing."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QObject, QSettings, pyqtSignal      # noqa: E402
from PyQt5.QtTest import QTest                                      # noqa: E402
from PyQt5.QtWidgets import QApplication, QMessageBox               # noqa: E402

import studyhelper.mainwindow as mw                                 # noqa: E402


class _NoWorker(QObject):
    ready = pyqtSignal(int, list, int)

    def __init__(self, completer):
        super().__init__()

    def request(self, *args):
        pass


class TabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        ini = str(self.root / "s.ini")
        for target, new in (
                (mock.patch.object(mw, "QSettings", lambda *a, **k: QSettings(ini, QSettings.IniFormat)), None),
                (mock.patch("studyhelper.editor._CompletionWorker", _NoWorker), None)):
            target.start()
            self.addCleanup(target.stop)
        rec = mock.patch.dict(os.environ, {"PYQTSTUDY_RECOVERY_DIR": str(self.root / "rec")})
        rec.start()
        self.addCleanup(rec.stop)
        self.a = self.make("a.py", "print('A')\n")
        self.b = self.make("b.py", "print('B')\n")
        self.w = mw.MainWindow()
        self.addCleanup(self.destroy)

    def destroy(self):
        w = self.w
        for _ in range(100):
            if not w.scanner.busy:
                break
            QTest.qWait(20)
        w._stash.clear()
        w.editor.document().setModified(False)
        w.close()
        w.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def make(self, name, text):
        p = self.root / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def names(self):
        return [self.w.file_tabs.tabText(i) for i in range(self.w.file_tabs.count())]

    def test_each_opened_file_gets_a_tab_once(self):
        self.w.open_path(self.a)
        self.w.open_path(self.b)
        self.w.open_path(self.a)
        self.assertEqual(self.names(), ["a.py", "b.py"])
        self.assertEqual(self.w.file_tabs.currentIndex(), 0)

    def test_switching_keeps_unsaved_edits_without_asking(self):
        self.w.open_path(self.a)
        self.w.editor.setPlainText("changed\n")
        self.w.editor.document().setModified(True)
        with mock.patch.object(QMessageBox, "question", side_effect=AssertionError("must not ask")):
            self.w.open_path(self.b)
            self.assertEqual(self.names(), ["● a.py", "b.py"])
            self.w.file_tabs.setCurrentIndex(0)                 # click the first tab
        self.assertEqual(self.w.py_path.name, "a.py")
        self.assertEqual(self.w.editor.toPlainText(), "changed\n")
        self.assertTrue(self.w.editor.document().isModified())
        self.assertEqual(Path(self.a).read_text(encoding="utf-8"), "print('A')\n")     # disk untouched

    def test_closing_a_dirty_background_tab_can_save_it(self):
        self.w.open_path(self.a)
        self.w.editor.setPlainText("saved me\n")
        self.w.editor.document().setModified(True)
        self.w.open_path(self.b)
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Save):
            self.w.close_tab(0)
        self.assertEqual(Path(self.a).read_text(encoding="utf-8").strip(), "saved me")
        self.assertEqual(self.names(), ["b.py"])
        self.assertEqual(self.w.py_path.name, "b.py")

    def test_cancel_keeps_the_tab(self):
        self.w.open_path(self.a)
        self.w.editor.setPlainText("keep\n")
        self.w.editor.document().setModified(True)
        self.w.open_path(self.b)
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Cancel):
            self.w.close_tab(0)
        self.assertEqual(self.names(), ["● a.py", "b.py"])

    def test_closing_the_shown_tab_shows_its_neighbour(self):
        self.w.open_path(self.a)
        self.w.open_path(self.b)
        self.w.close_tab(1)
        self.assertEqual(self.w.py_path.name, "a.py")
        self.w.close_tab(0)
        self.assertEqual(self.w.stack.currentIndex(), 0)
        self.assertFalse(self.w.file_tabs.isVisible())

    def test_quitting_asks_about_background_tabs_too(self):
        self.w.open_path(self.a)
        self.w.editor.setPlainText("x\n")
        self.w.editor.document().setModified(True)
        self.w.open_path(self.b)
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Cancel) as q:
            self.assertFalse(self.w._confirm_all())
            self.assertEqual(q.call_count, 1)
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Discard):
            self.assertTrue(self.w._confirm_all())


if __name__ == "__main__":
    unittest.main()


class ThemeTests(TabTests):
    """Dark theme: switches colours everywhere, is remembered, and the .ui preview stays light."""

    def test_toggle_changes_colours_and_is_remembered(self):
        from studyhelper import theme
        self.addCleanup(theme.apply, QApplication.instance(), False)
        self.w.open_path(self.a)
        light_kw = self.w.editor.highlighter.KW.foreground().color().name()
        self.w.a_dark.setChecked(True)
        self.w.toggle_dark()
        self.assertTrue(theme.dark)
        self.assertNotEqual(self.w.editor.highlighter.KW.foreground().color().name(), light_kw)
        self.assertEqual(self.w.settings.value("view/dark"), True)
        self.assertEqual(self.w.preview.palette().color(self.w.preview.palette().Window).name(), "#efefef")
        self.w.a_dark.setChecked(False)
        self.w.toggle_dark()
        self.assertFalse(theme.dark)
        self.assertEqual(self.w.editor.highlighter.KW.foreground().color().name(), light_kw)
