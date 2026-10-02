"""AiPanel: code blocks in an answer can be copied with one button."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication                              # noqa: E402

from studyhelper.explainpanel import AiPanel                          # noqa: E402

app = QApplication.instance() or QApplication([])


class CodeCopy(unittest.TestCase):
    def setUp(self):
        self.p = AiPanel()
        self.addCleanup(self.p.deleteLater)

    def test_no_code_no_button(self):
        self.p.transcript = "just words"
        self.p._render()
        self.assertTrue(self.p.b_code.isHidden())
        self.assertEqual(self.p.code_blocks(), [])

    def test_blocks_are_found_and_the_single_one_is_copied(self):
        self.p.transcript = "설명\n\n```python\nself.btn.setText('a')\n```\n"
        self.p._render()
        self.assertFalse(self.p.b_code.isHidden())
        self.assertEqual(self.p.code_blocks(), ["self.btn.setText('a')"])
        self.p._copy_code()
        self.assertEqual(QApplication.clipboard().text(), "self.btn.setText('a')")

    def test_several_blocks_in_order(self):
        self.p.transcript = "```\none\n```\ntext\n```py\ntwo\nthree\n```\n"
        self.assertEqual(self.p.code_blocks(), ["one", "two\nthree"])

    def test_copying_our_own_code_is_not_imported_as_an_answer(self):
        self.p.transcript = "```\nx = 1\n```"
        before = self.p.transcript
        self.p._copy_code()
        QApplication.processEvents()
        self.assertEqual(self.p.transcript, before)


if __name__ == "__main__":
    unittest.main()
