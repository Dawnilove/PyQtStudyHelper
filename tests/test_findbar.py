"""FindBar: find next/prev with wrap, count, replace one / all (one undo step)."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QPlainTextEdit              # noqa: E402

from studyhelper.findbar import FindBar                               # noqa: E402

app = QApplication.instance() or QApplication([])


class FindBarTests(unittest.TestCase):
    def setUp(self):
        self.ed = QPlainTextEdit()
        self.ed.setPlainText("self.a = 1\nself.b = Self\nprint(self)")
        self.fb = FindBar(self.ed)

    def test_find_wraps_and_counts(self):
        self.fb.find.setText("self")
        self.assertEqual(self.fb.count.text(), "4개")
        sel = [self.ed.textCursor().selectionStart()]
        for _ in range(4):
            self.fb._find(True)
            sel.append(self.ed.textCursor().selectionStart())
        self.assertEqual(len(set(sel)), 4)                  # visited all four ...
        self.assertEqual(sel[0], sel[4])                    # ... then wrapped back to the first

    def test_case_sensitive(self):
        self.fb.case.setChecked(True)
        self.fb.find.setText("self")
        self.assertEqual(self.fb.count.text(), "3개")
        self.fb.find.setText("Self")
        self.assertEqual(self.fb.count.text(), "1개")

    def test_not_found(self):
        self.fb.find.setText("zzz")
        self.assertEqual(self.fb.count.text(), "없음")

    def test_replace_all_is_one_undo(self):
        self.fb.find.setText("self")
        self.fb.repl.setText("me")
        before = self.ed.toPlainText()
        self.assertEqual(self.fb.replace_all(), 4)
        self.assertEqual(self.ed.toPlainText().count("me"), 4)
        self.ed.undo()
        self.assertEqual(self.ed.toPlainText(), before)

    def test_replace_one_moves_on(self):
        self.fb.find.setText("self")
        self.fb.repl.setText("X")
        self.fb.replace_one()          # selects first
        self.fb.replace_one()          # replaces it
        self.assertTrue(self.ed.toPlainText().startswith("X.a"))


if __name__ == "__main__":
    unittest.main()
