"""Several Main.py files open at once: tabs keep unsaved edits when switching and ask when closing."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QObject, QProcess, QSettings, pyqtSignal      # noqa: E402
from PyQt5.QtTest import QTest                                      # noqa: E402
from PyQt5.QtWidgets import QApplication, QMessageBox               # noqa: E402

import studyhelper.mainwindow as mw                                 # noqa: E402


class _NoWorker(QObject):
    ready = pyqtSignal(int, list, int)

    def __init__(self, completer):
        super().__init__()

    def request(self, *args):
        pass


class WindowCase(unittest.TestCase):
    """A MainWindow with two small files a.py / b.py; settings and backups in a temp folder."""
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

    def destroy(self, w=None):
        w = w or self.w
        for _ in range(100):
            if not w.scanner.busy:
                break
            QTest.qWait(20)
        w._stash.clear()
        w.editor.document().setModified(False)
        w.close()
        w.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def second_window(self):
        """Another window on the same settings (like starting the app again)."""
        w2 = mw.MainWindow()
        self.addCleanup(self.destroy, w2)
        return w2

    def make(self, name, text):
        p = self.root / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def names(self):
        return [self.w.file_tabs.tabText(i) for i in range(self.w.file_tabs.count())]

class TabTests(WindowCase):
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

    def test_the_x_button_closes_its_own_tab(self):
        from PyQt5.QtWidgets import QTabBar
        self.w.open_path(self.a)
        self.w.open_path(self.b)
        self.w.file_tabs.tabButton(0, QTabBar.RightSide).click()
        self.assertEqual(self.names(), ["b.py"])
        self.assertEqual(self.w.py_path.name, "b.py")

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



class ThemeTests(WindowCase):
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

    def test_rich_text_colours_follow_the_theme(self):
        from studyhelper import theme
        self.addCleanup(theme.apply, QApplication.instance(), False)
        lab = theme.ThemedLabel("<span style='color:#888'>안내</span> <span style='background:#ffd666;color:#5c3c00'>칩</span>")
        self.assertIn("color:#888", lab.text())
        theme.apply(QApplication.instance(), True)
        lab.retheme()
        self.assertIn("color:#9aa0a8", lab.text())                 # muted grey made lighter
        self.assertIn("color:#5c3c00", lab.text())                 # chip text keeps its own light background
        self.assertEqual(theme.fg("#c0392b"), "#ff8787")
        theme.apply(QApplication.instance(), False)
        lab.retheme()
        self.assertIn("color:#888", lab.text())
        self.assertEqual(theme.fg("#c0392b"), "#c0392b")


class SessionTests(WindowCase):
    """The tabs open at closing time come back next start."""

    def test_tabs_come_back(self):
        self.w.open_path(self.a)
        self.w.open_path(self.b)
        self.w.open_path(self.a)                      # a.py was the one shown
        self.w.close()
        w2 = self.second_window()
        self.assertTrue(w2.restore_session())
        self.assertEqual([w2.file_tabs.tabText(i) for i in range(w2.file_tabs.count())], ["a.py", "b.py"])
        self.assertEqual(w2.py_path.name, "a.py")

    def test_missing_files_are_skipped_and_nothing_means_start_screen(self):
        # a file deleted while the app was closed (not deleted under a running window's file watcher)
        gone = str(self.root / "gone.py")
        self.w.settings.setValue("session/tabs", [gone])
        self.w.settings.setValue("session/current", gone)
        w2 = self.second_window()
        self.assertFalse(w2.restore_session())
        self.assertEqual(w2.stack.currentIndex(), 0)


class RunInputTests(WindowCase):
    """input() in the student's program gets what is typed in the 입력 box."""

    def wait_done(self, ms=15000):
        waited = 0
        while self.w.proc and self.w.proc.state() != QProcess.NotRunning and waited < ms:
            QTest.qWait(50)
            waited += 50

    def test_typed_line_reaches_input(self):
        f = self.make("ask.py", "name = input('이름? ')\nprint('안녕', name)\n")
        self.w.open_path(f)
        self.assertFalse(self.w.stdin_edit.isEnabled())
        self.w.run()
        self.assertTrue(self.w.stdin_edit.isEnabled())
        self.w.stdin_edit.setText("민수")
        self.w.send_input()
        self.wait_done()
        out = self.w.output.toPlainText()
        self.assertIn("안녕 민수", out)
        self.assertIn("[종료 코드 0]", out)
        self.assertFalse(self.w.stdin_edit.isEnabled())

    def test_clear_button_empties_the_output(self):
        self.w.open_path(self.a)
        self.w.run()
        self.wait_done()
        self.assertIn("A", self.w.output.toPlainText())
        self.w.b_clear_out.click()
        self.assertEqual(self.w.output.toPlainText(), "")


class SaveConversationTests(WindowCase):
    def test_conversation_is_saved_as_markdown(self):
        panel = self.w.ai_panel
        self.assertTrue(panel.b_save.isHidden())
        panel.transcript = "## 🧑 질문\n\n**🤖 AI**\n\n답이에요.\n"
        panel._render()
        self.assertFalse(panel.b_save.isHidden())
        out = self.root / "talk.md"
        self.assertEqual(panel.save_conversation(str(out)), str(out))
        self.assertIn("답이에요.", out.read_text(encoding="utf-8"))

    def test_default_folder_is_the_open_files_folder(self):
        self.w.open_path(self.a)
        self.assertEqual(self.w.ai_panel.save_dir, str(Path(self.a).parent))


class VanishedFileTests(WindowCase):
    """The open Main.py is deleted / renamed outside while the app runs: no crash, code kept, Ctrl+S recreates it."""

    def test_open_file_disappears(self):
        self.w.open_path(self.a)
        os.remove(self.a)
        self.w.run_check()                                   # used to raise FileNotFoundError -> Qt abort
        for _ in range(10):                                  # the watcher's retries, without waiting 3 s
            self.w._on_file_changed(self.a)
            self.w._reload_pending()
        self.assertTrue(self.w.editor.document().isModified())
        self.assertEqual(self.w.editor.toPlainText(), "print('A')\n")
        self.assertTrue(self.w.save_py())
        self.assertEqual(Path(self.a).read_text(encoding="utf-8").strip(), "print('A')")

    def test_opening_a_missing_file_says_so(self):
        with mock.patch.object(QMessageBox, "warning") as warn:
            self.assertFalse(self.w.open_path(str(self.root / "nope.py")))
        warn.assert_called_once()
        self.assertEqual(self.w.stack.currentIndex(), 0)


if __name__ == "__main__":
    unittest.main()
