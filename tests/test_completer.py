"""Candidate logic for the Main.py editor's autocomplete (no Qt event loop needed)."""
import unittest

from studyhelper.completer import Completer

WIDGETS = {"pushButton": "QPushButton", "label": "QLabel", "verticalLayout": "QVBoxLayout",
           "weird": "NoSuchQtClass"}


def at_end(src: str):
    """(line, col) of the end of `src`, both 0-based — i.e. the cursor sits after the last typed char."""
    lines = src.split("\n")
    return len(lines) - 1, len(lines[-1])


class UiCandidates(unittest.TestCase):
    def setUp(self):
        self.c = Completer(use_jedi=False)
        self.c.set_widgets(WIDGETS)

    def run_complete(self, src, force=False):
        line, col = at_end(src)
        return self.c.complete(src, line, col, force=force)

    def test_self_prefix_lists_matching_ui_widget_names(self):
        items, prefix_len = self.run_complete("class A:\n    def f(self):\n        self.pu")
        names = [i.name for i in items]
        self.assertIn("pushButton", names)
        self.assertNotIn("label", names)
        self.assertEqual(prefix_len, 2)

    def test_ui_widget_names_are_tagged_as_widget(self):
        items, _ = self.run_complete("self.pu")
        self.assertEqual([(i.name, i.kind) for i in items if i.name == "pushButton"],
                         [("pushButton", "위젯")])

    def test_after_widget_dot_lists_qt_methods(self):
        items, prefix_len = self.run_complete("self.pushButton.setT")
        by_name = {i.name: i.kind for i in items}
        self.assertEqual(by_name.get("setText"), "메서드")
        self.assertEqual(prefix_len, 4)

    def test_after_widget_dot_lists_signals(self):
        items, _ = self.run_complete("self.pushButton.cl")
        by_name = {i.name: i.kind for i in items}
        self.assertEqual(by_name.get("clicked"), "시그널")

    def test_widget_dot_with_empty_prefix_still_completes(self):
        items, prefix_len = self.run_complete("self.pushButton.")
        self.assertIn("clicked", [i.name for i in items])
        self.assertEqual(prefix_len, 0)

    def test_members_come_from_the_widgets_own_class(self):
        items, _ = self.run_complete("self.label.setP")
        names = [i.name for i in items]
        self.assertIn("setPixmap", names)            # QLabel only
        items, _ = self.run_complete("self.pushButton.setP")
        self.assertNotIn("setPixmap", [i.name for i in items])

    def test_private_names_are_hidden(self):
        items, _ = self.run_complete("self.pushButton.")
        self.assertFalse([i.name for i in items if i.name.startswith("_")])

    def test_layout_names_complete_too(self):
        items, _ = self.run_complete("self.verti")
        self.assertIn("verticalLayout", [i.name for i in items])

    def test_unknown_qt_class_gives_no_members_and_no_crash(self):
        items, _ = self.run_complete("self.weird.set")
        self.assertEqual(items, [])

    def test_unknown_attribute_gives_no_members(self):
        items, _ = self.run_complete("self.nope.set")
        self.assertEqual(items, [])

    def test_names_update_when_ui_changes(self):
        self.c.set_widgets({"lineEdit": "QLineEdit"})
        items, _ = self.run_complete("self.pu")
        self.assertEqual(items, [])
        items, _ = self.run_complete("self.li")
        self.assertIn("lineEdit", [i.name for i in items])


class PlainCandidates(unittest.TestCase):
    """Keyword and same-file words (what is left when jedi is not installed)."""

    def setUp(self):
        self.c = Completer(use_jedi=False)

    def run_complete(self, src, force=False):
        line, col = at_end(src)
        return self.c.complete(src, line, col, force=force)

    def test_keyword_is_offered(self):
        items, prefix_len = self.run_complete("imp")
        self.assertEqual([(i.name, i.kind) for i in items if i.name == "import"],
                         [("import", "키워드")])
        self.assertEqual(prefix_len, 3)

    def test_word_already_in_file_is_offered(self):
        items, _ = self.run_complete("counter_total = 1\ncounter_t")
        self.assertIn("counter_total", [i.name for i in items])

    def test_the_word_being_typed_is_not_offered_to_itself(self):
        items, _ = self.run_complete("zzz_unique")
        self.assertEqual([i.name for i in items], [])

    def test_one_letter_prefix_is_not_auto_offered(self):
        items, prefix_len = self.run_complete("i")
        self.assertEqual((items, prefix_len), ([], 0))

    def test_one_letter_prefix_is_offered_when_forced(self):
        items, _ = self.run_complete("i", force=True)
        self.assertIn("import", [i.name for i in items])

    def test_no_popup_inside_a_comment(self):
        self.assertEqual(self.run_complete("# self.pu")[0], [])
        self.assertEqual(self.run_complete("x = 1  # imp")[0], [])

    def test_no_popup_inside_a_string(self):
        self.assertEqual(self.run_complete("print('imp")[0], [])
        self.assertEqual(self.run_complete('print("imp')[0], [])

    def test_hash_inside_a_closed_string_is_not_a_comment(self):
        items, _ = self.run_complete("s = '#'; imp")
        self.assertIn("import", [i.name for i in items])


class JediCandidates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import jedi  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("jedi not installed")
        cls.c = Completer(use_jedi=True)
        cls.c.set_widgets(WIDGETS)

    def run_complete(self, src, force=False):
        line, col = at_end(src)
        return self.c.complete(src, line, col, force=force)

    def test_pyqt_module_member(self):
        items, _ = self.run_complete("from PyQt5 import QtWidgets\nQtWidgets.QPushB")
        self.assertEqual([(i.name, i.kind) for i in items], [("QPushButton", "클래스")])

    def test_pyqt_import_name(self):
        items, _ = self.run_complete("from PyQt5.QtWidgets import QPu")
        self.assertIn("QPushButton", [i.name for i in items])

    def test_qt_enum_constant(self):
        items, _ = self.run_complete("from PyQt5 import QtCore\nQtCore.Qt.AlignC")
        self.assertIn("AlignCenter", [i.name for i in items])

    def test_member_of_a_local_variable(self):
        src = "from PyQt5 import QtWidgets\nx = QtWidgets.QLabel()\nx.setT"
        items, _ = self.run_complete(src)
        self.assertIn("setText", [i.name for i in items])

    def test_local_name_from_same_file(self):
        items, _ = self.run_complete("total_count = 1\ntotal_c")
        self.assertIn("total_count", [i.name for i in items])

    def test_ui_widget_names_are_listed_before_jedi_results(self):
        src = "from PyQt5 import QtWidgets\nclass A(QtWidgets.QMainWindow):\n    def f(self):\n        self.p"
        items, _ = self.run_complete(src)
        self.assertEqual(items[0].name, "pushButton")
        self.assertEqual(items[0].kind, "위젯")

    def test_widget_members_do_not_need_jedi_to_infer_the_type(self):
        src = "from PyQt5 import uic\nclass A:\n    def f(self):\n        self.pushButton.cl"
        items, _ = self.run_complete(src)
        self.assertIn(("clicked", "시그널"), [(i.name, i.kind) for i in items])

    def test_syntax_error_in_file_does_not_crash(self):
        items, _ = self.run_complete("def (:\n  import o")
        self.assertIsInstance(items, list)


if __name__ == "__main__":
    unittest.main()
