"""코드 과제 창, 학습 기록, 학습 기록 보기 — and how the main window wires them together."""
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QProcess, QSettings                        # noqa: E402
from PyQt5.QtTest import QTest                                      # noqa: E402
from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton  # noqa: E402

from studyhelper import helpmenu, learnlog, learnview, tasks, taskwindow   # noqa: E402
from studyhelper.runner import error_kind                           # noqa: E402
from tests.test_grader import MARK, SOLUTIONS                       # noqa: E402
from tests.test_helpers_ui import MAIN, UI                          # noqa: E402
from tests.test_tabs import WindowCase                              # noqa: E402

app = QApplication.instance() or QApplication([])


class LogCase(unittest.TestCase):
    """The learning log lives in a temp folder."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = mock.patch.dict(os.environ, {"PYQTSTUDY_LOG_DIR": str(self.root / "log")})
        env.start()
        self.addCleanup(env.stop)
        learnlog.reset_cache()
        self.addCleanup(learnlog.reset_cache)


class LearnLog(LogCase):
    def test_notes_are_saved_and_read_back(self):
        learnlog.note_open(self.root / "Main.py")
        learnlog.note_open(self.root / "Main.py")                  # the same file counts once
        learnlog.note_run()
        learnlog.note_run()
        learnlog.note_widget("QPushButton")
        learnlog.note_widget("QPushButton")
        learnlog.note_widget("")
        learnlog.note_error("AttributeError")
        learnlog.note_task("greet")
        learnlog.note_challenge("ex1/gui.ui")
        learnlog.reset_cache()                                      # read back from the file
        d = learnlog.load()
        self.assertEqual(len(d["files"]), 1)
        self.assertEqual(d["runs"], 2)
        self.assertEqual(d["widgets"], {"QPushButton": {"count": 2, "first": date.today().isoformat()}})
        self.assertEqual(d["errors"]["AttributeError"]["count"], 1)
        self.assertIn("greet", learnlog.solved_tasks())
        self.assertIn("ex1/gui.ui", d["challenges"])
        self.assertEqual(d["days"], [date.today().isoformat()])

    def test_a_broken_file_never_raises(self):
        f = learnlog.path()
        f.parent.mkdir(parents=True)
        for junk in ("not json", "[1, 2]", '{"runs": "x", "widgets": {"QLabel": 3}, "days": 5, "tasks": {"a": 1}}'):
            with self.subTest(junk=junk):
                f.write_text(junk, encoding="utf-8")
                learnlog.reset_cache()
                learnlog.note_run()
                learnlog.note_widget("QLabel")
                learnlog.note_open("x.py")
                self.assertIsInstance(learnlog.load()["days"], list)
                self.assertIsInstance(learnlog.solved_tasks(), dict)
                self.assertIn("기록", learnview.summary_html(learnlog.load()))

    def test_clear(self):
        learnlog.note_run()
        self.assertTrue(learnlog.path().exists())
        learnlog.clear()
        self.assertFalse(learnlog.path().exists())
        self.assertEqual(learnlog.load()["runs"], 0)

    def test_error_kind(self):
        self.assertEqual(error_kind("AttributeError: 'X' object has no attribute 'y'"), "AttributeError")
        self.assertEqual(error_kind("PyQt5.uic.exceptions.NoSuchWidgetError: Unknown Qt widget: X"),
                         "NoSuchWidgetError")


class LearnView(LogCase):
    DATA = {"days": ["2026-10-04", "2026-10-05", "2026-10-06"], "runs": 7, "files": ["a", "b"],
            "widgets": {"QPushButton": {"count": 5, "first": "2026-10-04"},
                        "QLabel": {"count": 1, "first": "2026-10-05"}},
            "errors": {"AttributeError": {"count": 3, "last": "2026-10-06 10:00"}},
            "tasks": {"greet": "2026-10-06 11:00"}, "challenges": {"ex1/gui.ui": "2026-10-05 09:00"}}

    def test_streak(self):
        today = date(2026, 10, 6)
        self.assertEqual(learnview.streak(self.DATA["days"], today), 3)
        self.assertEqual(learnview.streak(["2026-10-05"], today), 1)          # not yet today: yesterday counts
        self.assertEqual(learnview.streak(["2026-10-03", "2026-10-06"], today), 1)
        self.assertEqual(learnview.streak([], today), 0)

    def test_summary_shows_numbers_meanings_and_suggestions(self):
        h = learnview.summary_html(self.DATA, today=date(2026, 10, 6))
        for want in ("3일", "3일 연속", "7번", "2개", f"1/{len(tasks.TASKS)}", "objectName 오타", "ex1/gui.ui",
                     "✓ 1. 인사하기"):
            self.assertIn(want, h)
        later = h.split("다음에 만나 볼 위젯")[1]
        self.assertIn("QLineEdit", later)
        self.assertNotIn("QPushButton", later)                     # already seen

    def test_empty_log(self):
        h = learnview.summary_html(learnlog.load())
        self.assertIn("아직 기록이 없어요", h)
        self.assertIn(str(learnlog.path()), h)

    def test_dialog_clear_and_open_tasks(self):
        learnlog.note_run()
        dlg = learnview.LearnLogDialog()
        self.addCleanup(dlg.deleteLater)
        self.assertIn("1번", dlg.view.toPlainText())
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            dlg.clear()
        self.assertTrue(learnlog.path().exists())
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            dlg.clear()
        self.assertFalse(learnlog.path().exists())
        self.assertIn("아직 기록이 없어요", dlg.view.toPlainText())
        got = []
        dlg.tasksRequested.connect(lambda: got.append(1))
        next(b for b in dlg.findChildren(QPushButton) if b.text() == "코드 과제 열기").click()
        self.assertEqual(got, [1])


class TaskWin(LogCase):
    def setUp(self):
        super().setUp()
        self.settings = QSettings(str(self.root / "s.ini"), QSettings.IniFormat)
        self.settings.setValue("tasks/folder", str(self.root / "과제"))
        self.win = taskwindow.TaskWindow(self.settings)
        self.addCleanup(self.close)

    def close(self):
        self.win.close()
        self.win.deleteLater()

    def test_create_task_files_keeps_my_main(self):
        t = tasks.BY_ID["greet"]
        main = taskwindow.create_task_files(self.root / "f", t)
        main.write_text("# mine", encoding="utf-8")
        taskwindow.create_task_files(self.root / "f", t)
        self.assertEqual(main.read_text(encoding="utf-8"), "# mine")
        self.assertTrue((self.root / "f" / "task.ui").exists())

    def test_parse_result(self):
        out = 'noise\n@@GRADE@@{"results": [], "fatal": null, "passed": 0, "total": 0}\n'
        self.assertEqual(taskwindow.parse_result(out)["total"], 0)
        self.assertIn("읽지 못했어요", taskwindow.parse_result("@@GRADE@@{broken")["fatal"])
        self.assertIn("읽지 못했어요", taskwindow.parse_result("")["fatal"])

    def test_first_unsolved_task_is_selected(self):
        learnlog.note_task("greet")
        w = taskwindow.TaskWindow(self.settings)
        self.addCleanup(w.deleteLater)
        self.assertEqual(w.list.currentRow(), 1)
        self.assertTrue(w.list.item(0).text().startswith("✓"))

    def test_start_makes_files_and_asks_to_open(self):
        got = []
        self.win.openRequested.connect(got.append)
        self.win.list.setCurrentRow(1)                              # 숫자 세기
        self.assertEqual(self.win.b_start.text(), "과제 시작")
        self.assertFalse(self.win.b_grade.isEnabled())
        self.win.start()
        main = self.root / "과제" / "02_counter" / "Main.py"
        self.assertEqual(got, [str(main)])
        self.assertTrue((main.parent / "task.ui").exists())
        self.assertIn("이어서 하기", self.win.b_start.text())
        self.assertTrue(self.win.b_grade.isEnabled())

    def test_hints_one_by_one(self):
        self.win.list.setCurrentRow(0)
        t = tasks.TASKS[0]
        for _ in range(len(t.hints) + 2):
            self.win.more_hint()
        self.assertFalse(self.win.b_hint.isEnabled())
        self.assertIn(f"{len(t.hints)}/{len(t.hints)}", self.win.b_hint.text())

    def test_full_pass_is_remembered(self):
        self.win.list.setCurrentRow(0)
        ok = {"ok": True, "label": "a", "detail": ""}
        self.win.show_result("greet", {"results": [ok, ok], "fatal": None, "passed": 2, "total": 2})
        self.assertIn("통과", self.win.status.text())
        self.assertIn("greet", learnlog.solved_tasks())
        self.assertTrue(self.win.list.item(0).text().startswith("✓"))

    def test_partial_and_fatal_results(self):
        r = {"results": [{"ok": True, "label": "a", "detail": ""}, {"ok": False, "label": "b", "detail": "왜"}],
             "fatal": None, "passed": 1, "total": 2}
        self.win.show_result("greet", r)
        self.assertIn("1/2 통과", self.win.status.text())
        self.assertIn("→ 왜", self.win.results.item(1).text())
        self.assertNotIn("greet", learnlog.solved_tasks())
        self.win.show_result("greet", {"fatal": "문법 오류", "results": []})
        self.assertIn("문법 오류", self.win.status.text())

    def test_on_saved_grades_only_this_tasks_main(self):
        self.win.list.setCurrentRow(0)
        self.win.start()
        self.win.show()
        main = str(self.win.main_of(tasks.TASKS[0]))
        with mock.patch.object(self.win, "grade") as g:
            self.win.on_saved(str(self.root / "other.py"))
            g.assert_not_called()
            self.win.on_saved(main)
            g.assert_called_once()
            self.win.auto.setChecked(False)
            self.win.on_saved(main)
            g.assert_called_once()

    def test_saving_while_grading_does_not_grade_twice(self):
        self.win.list.setCurrentRow(0)
        self.win.start()
        self.win.show()
        main = str(self.win.main_of(tasks.TASKS[0]))
        starts = []
        self.win.saveRequested.connect(self.win.on_saved)          # like the helper: saving reports back
        with mock.patch.object(QProcess, "start", lambda p, *a: starts.append(a)):
            self.win.on_saved(main)
        self.assertEqual(len(starts), 1)

    def test_switching_task_while_grading_drops_that_run(self):
        self.win.list.setCurrentRow(0)
        self.win.start()
        with mock.patch.object(QProcess, "start", lambda p, *a: None):
            self.win.grade()
        self.assertEqual(self.win._grading, "greet")
        self.win.list.setCurrentRow(1)
        self.assertIsNone(self.win._grading)
        self.assertIsNone(self.win._proc)
        self.assertEqual(self.win.status.text(), "")

    def test_grading_runs_the_real_grader(self):
        self.win.list.setCurrentRow(0)
        self.win.start()
        main = self.win.main_of(tasks.TASKS[0])
        main.write_text(main.read_text(encoding="utf-8").replace(MARK, SOLUTIONS["greet"].lstrip("\n")),
                        encoding="utf-8")
        self.win.grade()
        self.assertFalse(self.win.b_grade.isEnabled())
        for _ in range(600):
            if self.win._grading is None:
                break
            QTest.qWait(50)
        self.assertIn("통과", self.win.status.text())
        self.assertEqual(self.win.results.count(), 2)
        self.assertIn("greet", learnlog.solved_tasks())
        self.assertTrue(self.win.b_grade.isEnabled())


class InMainWindow(WindowCase):
    def setUp(self):
        super().setUp()
        self.w.settings.setValue("tasks/folder", str(self.root / "과제"))

    def start_task(self):
        self.w.open_tasks()
        tw = self.w.task_window
        tw.list.setCurrentRow(0)
        tw.start()
        return tw, tw.main_of(tasks.TASKS[0])

    def test_task_opens_in_the_helper_and_saving_grades_it(self):
        tw, main = self.start_task()
        self.assertEqual(self.w.py_path, main.resolve())
        self.assertEqual(self.w.ui_path.name, "task.ui")
        self.assertIn("btnGreet", self.w.model.nodes)
        with mock.patch.object(tw, "grade") as g:
            self.w.editor.setPlainText(self.w.editor.toPlainText() + "\n")
            self.w.editor.document().setModified(True)
            self.w.save_py()
            g.assert_called_once()

    def test_grading_saves_the_open_file_first(self):
        tw, main = self.start_task()
        self.w.editor.setPlainText(self.w.editor.toPlainText().replace(MARK, "        pass  # edited\n"))
        self.w.editor.document().setModified(True)
        with mock.patch.object(QProcess, "start", lambda p, *a: None):   # don't really grade here
            tw.grade()
        self.assertFalse(self.w.editor.document().isModified())
        self.assertIn("# edited", main.read_text(encoding="utf-8"))

    def test_window_notes_files_widgets_and_errors(self):
        (self.root / "gui.ui").write_text(UI, encoding="utf-8")
        main = self.make("Main.py", MAIN)
        self.w.open_path(main)
        self.assertEqual(len(learnlog.load()["files"]), 1)
        self.w.select("btnOk", "tree")
        self.w.select("edtName", "hover")                       # hovering in the code isn't "looking at" it
        self.assertEqual(set(learnlog.load()["widgets"]), {"QPushButton"})
        self.w._stderr = 'Traceback (most recent call last):\n  File "Main.py", line 1\nAttributeError: boom\n'
        self.w._on_finished(1, 0)
        self.assertEqual(learnlog.load()["errors"]["AttributeError"]["count"], 1)

    def test_menu_toolbar_welcome_and_log_window(self):
        keys = {k for _, _, k in helpmenu.menu_shortcuts(self.w.menuBar())}
        self.assertIn("Ctrl+Shift+T", keys)
        self.assertIn("Ctrl+Shift+L", keys)
        self.assertIn(self.w.a_tasks, self.w.toolbar.actions())
        self.assertEqual([b.text() for b in self.w._welcome_buttons], ["코드 과제 풀기", "화면 따라 만들기", "학습 기록"])
        with mock.patch.object(learnview.LearnLogDialog, "exec_", return_value=0) as ex:
            self.w.show_learnlog()
            ex.assert_called_once()


if __name__ == "__main__":
    unittest.main()
