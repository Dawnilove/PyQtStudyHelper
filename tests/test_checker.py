"""Name checker: the classic beginner mistakes are caught before running."""
import unittest

from studyhelper.checker import check

UI = {"MainWindow", "centralwidget", "btnOk", "lblMsg", "edtName"}

GOOD = '''import sys
from PyQt5.QtWidgets import *
from PyQt5 import uic

form_class = uic.loadUiType("gui.ui")[0]


class Form(QMainWindow, form_class):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.btnOk.clicked.connect(self.ok)
        self.edtName.returnPressed.connect(lambda: self.say("hi"))

    def ok(self):
        self.lblMsg.setText(self.edtName.text())

    def say(self, text):
        self.lblMsg.setText(text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Form()
    w.show()
    sys.exit(app.exec_())
'''


def msgs(src, names=UI):
    return [(x.line + 1, x.level, x.msg) for x in check(src, names, ("QMainWindow",))]


class Checker(unittest.TestCase):
    def test_correct_code_has_no_issues(self):
        self.assertEqual(msgs(GOOD), [])

    def test_typo_in_widget_name(self):
        out = msgs(GOOD.replace("self.lblMsg.setText(self.edtName", "self.lblMgs.setText(self.edtName"))
        self.assertEqual(len(out), 1)
        self.assertIn("lblMsg", out[0][2])

    def test_missing_slot(self):
        out = msgs(GOOD.replace("connect(self.ok)", "connect(self.okk)"))
        self.assertTrue(any("슬롯 함수 'okk'" in m for _, _, m in out))

    def test_calling_the_slot_in_connect(self):
        out = msgs(GOOD.replace("connect(self.ok)", "connect(self.ok())"))
        self.assertEqual([(ln, lv) for ln, lv, _ in out], [(12, "error")])
        self.assertIn("connect(self.ok)", out[0][2])

    def test_calling_with_an_argument_suggests_lambda(self):
        out = msgs(GOOD.replace("connect(self.ok)", "connect(self.say('x'))"))
        self.assertIn("lambda: self.say('x')", out[0][2])

    def test_missing_setupui(self):
        out = msgs(GOOD.replace("        self.setupUi(self)\n", ""))
        self.assertTrue(any(ln == 8 and "setupUi" in m for ln, _, m in out))

    def test_widget_used_before_setupui(self):
        src = GOOD.replace("        self.setupUi(self)\n        self.btnOk.clicked.connect(self.ok)\n",
                           "        self.btnOk.clicked.connect(self.ok)\n        self.setupUi(self)\n")
        out = msgs(src)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], 11)
        self.assertIn("setupUi() 보다 먼저", out[0][2])

    def test_missing_super_init(self):
        out = msgs(GOOD.replace("        super().__init__()\n", ""))
        self.assertTrue(any("super().__init__()" in m for _, _, m in out))

    def test_old_style_parent_init_is_fine(self):
        self.assertEqual(msgs(GOOD.replace("super().__init__()", "QMainWindow.__init__(self)")), [])

    def test_missing_self(self):
        out = msgs(GOOD.replace("self.btnOk.clicked", "btnOk.clicked"))
        self.assertEqual(len(out), 1)
        self.assertIn("self.btnOk", out[0][2])

    def test_a_local_variable_with_a_widget_name_is_fine(self):
        src = GOOD.replace("    def ok(self):\n", "    def ok(self):\n        lblMsg = self.lblMsg\n        lblMsg.clear()\n")
        self.assertEqual(msgs(src), [])

    def test_composition_style_is_not_flagged(self):
        src = '''from PyQt5.QtWidgets import *
from gui import Ui_MainWindow


class Win(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.btnOk.clicked.connect(self.close)
'''
        self.assertEqual(msgs(src, UI | {"ui"}), [])

    def test_comments_and_strings_are_ignored(self):
        src = GOOD.replace("        self.setupUi(self)\n",
                           "        self.setupUi(self)\n        # btnOk.clicked.connect(self.ok())\n"
                           "        print('connect(self.ok())')\n")
        self.assertEqual(msgs(src), [])

    def test_syntax_error(self):
        out = msgs(GOOD.replace("def ok(self):", "def ok(self)"))
        self.assertTrue(out and out[0][2].startswith("문법 오류"))


if __name__ == "__main__":
    unittest.main()
