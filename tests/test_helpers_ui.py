""".ui undo, widget examples, help menu (shortcuts, error log, versions), settings window, line → AI link."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QUrl                                       # noqa: E402
from PyQt5.QtWidgets import QApplication                            # noqa: E402

from studyhelper import examples, helpmenu, uihistory              # noqa: E402
from studyhelper.explainpanel import AI_LINK, LineExplainView      # noqa: E402
from studyhelper.settingsdialog import SettingsDialog              # noqa: E402
from tests.test_tabs import WindowCase                             # noqa: E402

app = QApplication.instance() or QApplication([])

UI = """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>MainWindow</class>
 <widget class="QMainWindow" name="MainWindow">
  <widget class="QWidget" name="centralwidget">
   <layout class="QVBoxLayout" name="verticalLayout">
    <item><widget class="QPushButton" name="btnOk"><property name="text"><string>확인</string></property></widget></item>
    <item><widget class="QLineEdit" name="edtName"/></item>
   </layout>
  </widget>
 </widget>
</ui>
"""
MAIN = """import sys
from PyQt5.QtWidgets import *
from PyQt5 import uic

form_class = uic.loadUiType("gui.ui")[0]


class Form(QMainWindow, form_class):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
"""


class UiHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(uihistory.clear)
        self.f = Path(self.tmp.name) / "gui.ui"
        self.f.write_text("v1", encoding="utf-8")

    def test_undo_puts_back_the_previous_versions_in_order(self):
        uihistory.snapshot(self.f, "첫 수정")
        self.f.write_text("v2", encoding="utf-8")
        uihistory.snapshot(self.f, "둘째 수정")
        self.f.write_text("v3", encoding="utf-8")
        self.assertEqual(uihistory.last_label(self.f), "둘째 수정")
        self.assertEqual(uihistory.undo(self.f), "둘째 수정")
        self.assertEqual(self.f.read_text(encoding="utf-8"), "v2")
        self.assertEqual(uihistory.undo(self.f), "첫 수정")
        self.assertEqual(self.f.read_text(encoding="utf-8"), "v1")
        self.assertIsNone(uihistory.undo(self.f))

    def test_discard_and_limit(self):
        uihistory.snapshot(self.f, "x")
        uihistory.discard(self.f)
        self.assertIsNone(uihistory.last_label(self.f))
        for i in range(uihistory.MAX_STEPS + 5):
            uihistory.snapshot(self.f, str(i))
        n = 0
        while uihistory.undo(self.f):
            n += 1
        self.assertEqual(n, uihistory.MAX_STEPS)


class Examples(unittest.TestCase):
    def test_closest_class_in_the_hierarchy(self):
        titles = [t for t, _ in examples.examples_for("QCheckBox", "chkAgree")]
        self.assertIn("체크됐는지 확인", titles)                        # from QAbstractButton
        code = dict(examples.examples_for("QCheckBox", "chkAgree"))["체크됐는지 확인"]
        self.assertIn("self.chkAgree.isChecked()", code)

    def test_specific_class_wins_and_general_ones_follow(self):
        titles = [t for t, _ in examples.examples_for("QPushButton", "btnOk")]
        self.assertEqual(titles[0], "눌렀을 때 함수 실행")
        self.assertIn("보이기 / 숨기기", titles)
        self.assertNotIn("보이기 / 숨기기", [t for t, _ in examples.examples_for("QMainWindow", "MainWindow", True)])

    def test_braces_in_code_survive(self):
        code = dict(examples.examples_for("QLabel", "lblCount"))["숫자 보여주기 (str로 바꿔서)"]
        self.assertIn("f'{count}개'", code)

    def test_every_example_is_valid_python(self):
        import ast
        for cls in examples.EXAMPLES:
            for title, code in examples.examples_for(cls, "w"):
                ast.parse(code.replace("\n    ", "\n    ") if not code.startswith("def") else code)

    def test_doc_url(self):
        self.assertEqual(examples.doc_url("QPushButton"), "https://doc.qt.io/qt-5/qpushbutton.html")
        self.assertIsNone(examples.doc_url("MyWidget"))


class HelpMenu(unittest.TestCase):
    def test_versions_compare_as_numbers(self):
        self.assertTrue(helpmenu.is_newer("1.10.0", "1.9.9"))
        self.assertFalse(helpmenu.is_newer("1.5.0", "1.5.0"))
        self.assertFalse(helpmenu.is_newer("junk", "1.0"))
        self.assertEqual(helpmenu.parse_version('"""x"""\n__version__ = "2.0.1"\n'), (2, 0, 1))

    def test_error_log_dialog_shows_copies_and_clears(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "error.log"
            dlg = helpmenu.ErrorLogDialog(None, log)
            self.assertIn("아직 오류 기록이 없어요", dlg.text.toPlainText())
            self.assertIn("Python", dlg.text.toPlainText())
            log.write_text("Traceback: boom", encoding="utf-8")
            dlg.refresh()
            dlg.copy_all()
            self.assertIn("boom", QApplication.clipboard().text())
            dlg.clear_log()
            self.assertFalse(log.exists())
            dlg.deleteLater()

    def test_update_checker_reports_only_newer(self):
        got = []
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "v.py"
            f.write_text('__version__ = "99.0.0"', encoding="utf-8")
            c = helpmenu.UpdateChecker(None, QUrl.fromLocalFile(str(f)).toString())
            c.newer.connect(got.append)
            c.run()                                  # synchronously, no thread
            f.write_text('__version__ = "0.0.1"', encoding="utf-8")
            c.run()
        self.assertEqual(got, ["99.0.0"])


class SettingsWindow(unittest.TestCase):
    def test_values_round_trip(self):
        v = {"dark": True, "zoom": 3, "legend": False, "explorer": True, "tips": False,
             "restore": False, "update": True, "backup": 60}
        dlg = SettingsDialog(v, {"테스트": lambda: None})
        self.assertEqual(dlg.values(), v)
        dlg.deleteLater()


class LineToAi(unittest.TestCase):
    def test_line_explanation_ends_with_the_ai_link(self):
        view = LineExplainView()
        view.show_line(["x = compute_something()"], 0)
        self.assertIn(AI_LINK, view.toHtml())
        view.deleteLater()


class InWindow(WindowCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(uihistory.clear)
        self.ui = self.root / "gui.ui"
        self.ui.write_text(UI, encoding="utf-8")
        self.main = self.make("Main.py", MAIN)
        self.w.open_path(self.main)

    def test_property_edit_can_be_undone(self):
        self.assertFalse(self.w.a_undo_ui.isEnabled())
        self.w.edit_property("btnOk", "text", "저장")
        self.assertIn("저장", self.ui.read_text(encoding="utf-8"))
        self.w.load_ui(self.w.ui_path)
        self.assertTrue(self.w.a_undo_ui.isEnabled())
        self.assertIn("btnOk.text", self.w.a_undo_ui.text())
        self.w.undo_ui()
        self.assertEqual(self.ui.read_text(encoding="utf-8"), UI)
        self.assertFalse(self.w.a_undo_ui.isEnabled())

    def test_widget_menu_offers_common_signals_first(self):
        from PyQt5.QtWidgets import QMenu
        shown = {}

        def fake_exec(menu, *a):
            shown["items"] = [a.text() for a in menu.actions()]
            sub = next(a.menu() for a in menu.actions() if a.menu())
            shown["signals"] = [a.text() for a in sub.actions()]
            return None
        with mock.patch.object(QMenu, "exec_", fake_exec):
            self.w._widget_menu("btnOk", self.w.mapToGlobal(self.w.rect().center()))
        self.assertIn("시그널 연결 코드 넣기", shown["items"])
        self.assertIn("예제 코드 보기", shown["items"])
        self.assertTrue(any(t.startswith("Qt 문서 열기") for t in shown["items"]))
        self.assertEqual(shown["signals"][0], "clicked()")
        self.assertIn("다른 시그널", shown["signals"])

    def test_settings_apply(self):
        from studyhelper import theme
        self.addCleanup(theme.apply, QApplication.instance(), False)
        v = {"dark": True, "zoom": 2, "legend": False, "explorer": False, "tips": False,
             "restore": False, "update": False, "backup": 0}
        self.w.apply_settings(v)
        self.assertTrue(theme.dark)
        self.assertEqual(self.w.editor.font().pointSize(), 12)
        self.assertTrue(self.w.legend.isHidden())
        self.assertFalse(self.w._backup_timer.isActive())
        self.assertFalse(self.w.restore_session())             # restoring is switched off
        self.assertTrue(self.w._tips_hidden())

    def test_shortcut_list_has_menu_keys(self):
        rows = helpmenu.menu_shortcuts(self.w.menuBar())
        keys = {k for _, _, k in rows}
        for want in ("F5", "Ctrl+F", "Ctrl+Alt+Z", "Ctrl+,", "Ctrl+/"):
            self.assertIn(want, keys)


if __name__ == "__main__":
    unittest.main()
