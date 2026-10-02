"""CodeEditor autocomplete behaviour: typing opens the popup, Tab accepts (offscreen Qt)."""
import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt                                    # noqa: E402
from PyQt5.QtTest import QTest                                 # noqa: E402
from PyQt5.QtWidgets import QApplication                       # noqa: E402

from studyhelper.editor import CodeEditor                      # noqa: E402

WIDGETS = {"pushButton": "QPushButton", "pushButton2": "QPushButton", "label": "QLabel"}


def wait_until(cond, timeout=20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        QTest.qWait(30)
    return cond()


class EditorAutocomplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.ed = CodeEditor()                      # one editor: its jedi warm-up is slow, do it once
        cls.ed.resize(600, 300)
        cls.ed.show()

    def setUp(self):
        self.ed.setPlainText("")
        self.ed.set_widgets(WIDGETS)
        self.ed.hide_completion()

    def type(self, text):
        QTest.keyClicks(self.ed, text)

    def key(self, key, mod=Qt.NoModifier):
        QTest.keyClick(self.ed, key, mod)

    def open_popup(self, text):
        self.type(text)
        self.assertTrue(wait_until(self.ed.completion_visible), f"no popup after typing {text!r}")

    def test_typing_opens_a_popup_with_the_matching_widgets(self):
        self.open_popup("self.pu")
        self.assertEqual(self.ed.completion_names(), ["pushButton", "pushButton2"])

    def test_tab_accepts_the_selected_candidate(self):
        self.open_popup("self.pu")
        self.key(Qt.Key_Tab)
        self.assertEqual(self.ed.toPlainText(), "self.pushButton")
        self.assertFalse(self.ed.completion_visible())

    def test_tab_completes_a_qt_signal_after_a_widget(self):
        self.open_popup("self.pushButton.cl")
        self.key(Qt.Key_Tab)
        self.assertEqual(self.ed.toPlainText(), "self.pushButton.clicked")

    def test_down_then_tab_picks_the_next_candidate(self):
        self.open_popup("self.pu")
        self.key(Qt.Key_Down)
        self.key(Qt.Key_Tab)
        self.assertEqual(self.ed.toPlainText(), "self.pushButton2")

    def test_up_wraps_to_the_last_candidate(self):
        self.open_popup("self.pu")
        self.key(Qt.Key_Up)
        self.key(Qt.Key_Tab)
        self.assertEqual(self.ed.toPlainText(), "self.pushButton2")

    def test_tab_only_replaces_the_typed_prefix(self):
        self.type("x = 1")
        self.key(Qt.Key_Return)                     # not "\n" in keyClicks: that aborts PyQt5 5.15 on Python 3.14
        self.type("print(self.la")
        self.assertTrue(wait_until(self.ed.completion_visible))
        self.key(Qt.Key_Tab)
        self.assertEqual(self.ed.toPlainText(), "x = 1\nprint(self.label")

    def test_tab_without_a_popup_still_inserts_a_tab(self):
        self.type("x")
        self.key(Qt.Key_Tab)
        self.assertEqual(self.ed.toPlainText(), "x\t")

    def test_enter_does_not_accept_it_just_closes_the_popup(self):
        self.open_popup("self.pu")
        self.key(Qt.Key_Return)
        self.assertEqual(self.ed.toPlainText(), "self.pu\n")
        self.assertFalse(self.ed.completion_visible())

    def test_escape_closes_the_popup_and_keeps_the_text(self):
        self.open_popup("self.pu")
        self.key(Qt.Key_Escape)
        self.assertFalse(self.ed.completion_visible())
        self.assertEqual(self.ed.toPlainText(), "self.pu")

    def test_typing_more_letters_narrows_the_popup_at_once(self):
        self.open_popup("self.pu")
        self.type("shButton")                       # no wait: the list must already match what is typed
        self.assertEqual(self.ed.completion_names(), ["pushButton2"])    # "pushButton" itself is complete
        self.key(Qt.Key_Tab)
        self.assertEqual(self.ed.toPlainText(), "self.pushButton2")

    def test_tab_right_after_fast_typing_does_not_corrupt_the_text(self):
        self.open_popup("self.pu")
        self.type("sh")
        self.key(Qt.Key_Tab)                        # the popup was opened for "pu"; the text is now "push"
        self.assertEqual(self.ed.toPlainText(), "self.pushButton")

    def test_popup_closes_when_nothing_matches_any_more(self):
        self.open_popup("self.pu")
        self.type("zz")
        self.assertFalse(self.ed.completion_visible())

    def test_popup_closes_when_the_word_is_finished(self):
        self.open_popup("self.pu")
        self.type(" ")
        self.assertFalse(self.ed.completion_visible())

    def test_no_popup_inside_a_comment(self):
        self.type("# self.pu")
        QTest.qWait(600)
        self.assertFalse(self.ed.completion_visible())

    def test_ctrl_space_opens_the_popup_for_a_short_prefix(self):
        self.type("i")
        QTest.qWait(400)
        self.assertFalse(self.ed.completion_visible())     # one letter: not automatic
        self.key(Qt.Key_Space, Qt.ControlModifier)
        self.assertTrue(wait_until(self.ed.completion_visible))
        self.assertEqual(self.ed.toPlainText(), "i")        # Ctrl+Space must not type a space

    def test_accepting_is_one_undo_step(self):
        self.open_popup("self.pu")
        self.key(Qt.Key_Tab)
        self.ed.undo()
        self.assertEqual(self.ed.toPlainText(), "self.pu")

    def test_moving_the_cursor_with_an_arrow_key_closes_the_popup(self):
        self.open_popup("self.pu")
        self.key(Qt.Key_Left)
        self.assertFalse(self.ed.completion_visible())

    def test_backspace_refreshes_the_popup(self):
        self.open_popup("self.pus")
        for _ in range(3):
            self.key(Qt.Key_Backspace)              # back to "self." -> the list widens again
        self.assertEqual(self.ed.toPlainText(), "self.")
        self.assertTrue(wait_until(lambda: "label" in self.ed.completion_names()))


if __name__ == "__main__":
    unittest.main()
