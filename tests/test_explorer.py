"""Left explorer: study folder tree, or the recent files when no study folder is registered."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QObject, QSettings, Qt, pyqtSignal   # noqa: E402
from PyQt5.QtTest import QTest                                      # noqa: E402
from PyQt5.QtWidgets import QApplication                            # noqa: E402

import studyhelper.mainwindow as mw                                 # noqa: E402
from studyhelper import explorer as ex                              # noqa: E402


class _NoWorker(QObject):
    """Stands in for editor._CompletionWorker: answers nothing, starts no thread."""
    ready = pyqtSignal(int, list, int)

    def __init__(self, completer):
        super().__init__()

    def request(self, *args):
        pass


def child_texts(item):
    return [item.child(i).text(0) for i in range(item.childCount())]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def tree(self):
        """study/ex1/{Main.py,gui.ui,gui.py,notes.txt}, study/ex2/Main.py, study/ex10/Main.py, junk folders."""
        study = self.root / "study"
        for name, files in {"ex1": ("Main.py", "gui.ui", "gui.py", "notes.txt"),
                            "ex2": ("Main.py",), "ex10": ("Main.py",),
                            "__pycache__": ("x.py",), ".git": ("y.py",), "venv": ("z.py",)}.items():
            (study / name).mkdir(parents=True, exist_ok=True)
            for f in files:
                (study / name / f).write_text("", encoding="utf-8")
        (study / "top.py").write_text("", encoding="utf-8")
        return str(study)


class ListDir(Base):
    def test_only_py_and_ui_and_junk_folders_are_hidden(self):
        study = self.tree()
        dirs, files, trunc = ex.list_dir(study)
        self.assertEqual(dirs, ["ex1", "ex2", "ex10"])            # natural order; no __pycache__, .git, venv
        self.assertEqual(files, ["top.py"])
        d, f, _ = ex.list_dir(os.path.join(study, "ex1"))
        self.assertEqual(f, ["gui.py", "gui.ui", "Main.py"])      # notes.txt is not shown
        self.assertFalse(trunc)

    def test_missing_folder_is_empty_not_an_error(self):
        self.assertEqual(ex.list_dir(str(self.root / "nope")), ([], [], False))

    def test_a_huge_folder_is_cut_off(self):
        big = self.root / "big"
        big.mkdir()
        for i in range(ex.MAX_ENTRIES + 20):
            (big / f"f{i}.py").write_text("", encoding="utf-8")
        _, files, trunc = ex.list_dir(str(big))
        self.assertEqual(len(files), ex.MAX_ENTRIES)
        self.assertTrue(trunc)


class Panel(Base):
    def panel(self, folders=(), recent=(), current=""):
        p = ex.ExplorerPanel()
        self.addCleanup(lambda: (p.deleteLater(), QApplication.sendPostedEvents(None, QEvent.DeferredDelete)))
        p.set_data(folders, recent, current)
        return p

    def test_without_study_folders_the_recent_files_are_listed(self):
        a, b = self.root / "a" / "Main.py", self.root / "b" / "Main.py"
        for f in (a, b):
            f.parent.mkdir()
            f.write_text("", encoding="utf-8")
        p = self.panel(recent=[str(a), str(b)])
        self.assertIn("최근 파일", p.title.text())
        self.assertEqual(p.top_texts(), ["a / Main.py", "b / Main.py"])
        self.assertIn("학습 폴더를 등록", p.hint.text())

    def test_without_anything_it_says_so(self):
        p = self.panel()
        self.assertEqual(p.top_texts(), ["(아직 연 파일이 없어요)"])
        self.assertFalse(p.tree.topLevelItem(0).flags() & Qt.ItemIsSelectable)

    def test_clicking_a_recent_file_opens_it(self):
        f = self.root / "a" / "Main.py"
        f.parent.mkdir()
        f.write_text("", encoding="utf-8")
        p = self.panel(recent=[str(f)])
        got = []
        p.openRequested.connect(got.append)
        p._on_clicked(p.tree.topLevelItem(0), 0)
        self.assertEqual(got, [str(f)])

    def test_study_folders_replace_the_recent_list(self):
        study = self.tree()
        p = self.panel(folders=[study], recent=[str(Path(study) / "ex1" / "Main.py")])
        self.assertIn("학습 폴더", p.title.text())
        self.assertEqual(p.top_texts(), ["study"])                 # the recent file is not listed

    def test_folders_load_when_expanded(self):
        study = self.tree()
        p = self.panel(folders=[study])
        root = p.tree.topLevelItem(0)
        self.assertEqual(root.child(0).data(0, ex.KIND_ROLE), "placeholder")   # nothing read yet
        root.setExpanded(True)
        self.assertEqual(child_texts(root), ["ex1", "ex2", "ex10", "top.py"])  # folders first
        ex1 = root.child(0)
        ex1.setExpanded(True)
        self.assertEqual(child_texts(ex1), ["gui.py", "gui.ui", "Main.py"])

    def test_clicking_a_file_opens_it_and_a_folder_toggles(self):
        study = self.tree()
        p = self.panel(folders=[study])
        got = []
        p.openRequested.connect(got.append)
        root = p.tree.topLevelItem(0)
        p._on_clicked(root, 0)
        self.assertTrue(root.isExpanded())
        p._on_clicked(root, 0)
        self.assertFalse(root.isExpanded())
        root.setExpanded(True)
        p._on_clicked(root.child(3), 0)                            # top.py
        self.assertEqual(got, [os.path.join(study, "top.py")])
        p._on_clicked(root.child(0), 0)                            # a folder: no file opened
        self.assertEqual(len(got), 1)

    def test_ui_files_open_too(self):
        study = self.tree()
        p = self.panel(folders=[study])
        got = []
        p.openRequested.connect(got.append)
        root = p.tree.topLevelItem(0)
        root.setExpanded(True)
        root.child(0).setExpanded(True)
        ui = next(root.child(0).child(i) for i in range(3) if root.child(0).child(i).text(0) == "gui.ui")
        p._on_clicked(ui, 0)
        self.assertEqual(got, [os.path.join(study, "ex1", "gui.ui")])

    def test_the_open_file_is_revealed_and_selected(self):
        study = self.tree()
        target = os.path.join(study, "ex2", "Main.py")
        p = self.panel(folders=[study], current=target)
        self.assertEqual(os.path.normcase(p.selected_path()), os.path.normcase(target))
        root = p.tree.topLevelItem(0)
        self.assertTrue(root.isExpanded())

    def test_changing_the_open_file_moves_the_highlight(self):
        study = self.tree()
        p = self.panel(folders=[study], current=os.path.join(study, "ex1", "Main.py"))
        p.set_current(os.path.join(study, "ex10", "Main.py"))
        self.assertEqual(os.path.normcase(p.selected_path()), os.path.normcase(os.path.join(study, "ex10", "Main.py")))

    def test_refresh_keeps_expanded_folders(self):
        study = self.tree()
        p = self.panel(folders=[study])
        root = p.tree.topLevelItem(0)
        root.setExpanded(True)
        root.child(0).setExpanded(True)
        (Path(study) / "ex1" / "extra.py").write_text("", encoding="utf-8")
        p.refresh()
        root = p.tree.topLevelItem(0)
        self.assertTrue(root.isExpanded() and root.child(0).isExpanded())
        self.assertIn("extra.py", child_texts(root.child(0)))

    def test_file_outside_the_study_folders_selects_nothing(self):
        study = self.tree()
        p = self.panel(folders=[study], current=str(self.root / "elsewhere.py"))
        self.assertEqual(p.selected_path(), "")


class InWindow(Base):
    def setUp(self):
        super().setUp()
        self.ini = str(self.root / "settings.ini")
        patcher = mock.patch.object(mw, "QSettings", lambda *a, **k: QSettings(self.ini, QSettings.IniFormat))
        patcher.start()
        self.addCleanup(patcher.stop)
        # every window's editor starts a jedi thread; several of them at once (and the ones the autocomplete
        # tests leave running) can crash the interpreter. This test is about the explorer, so no thread at all.
        warm = mock.patch("studyhelper.editor._CompletionWorker", _NoWorker)
        warm.start()
        self.addCleanup(warm.stop)

    def seed(self, **values):
        s = QSettings(self.ini, QSettings.IniFormat)
        for k, v in values.items():
            s.setValue(k, v)
        s.sync()

    def window(self):
        w = mw.MainWindow()
        # the window searches the study folders in a thread: let it finish before the window is deleted
        self.addCleanup(lambda: (self.wait_scan(w), self.destroy_now(w)))
        return w

    def destroy_now(self, widget):
        """Delete right here instead of 'later', so no half-dead window lingers into the next test."""
        widget.close()
        widget.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def lesson(self, name="ex1"):
        d = self.root / "study" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "Main.py").write_text("print('hi')\n", encoding="utf-8")
        return str(d / "Main.py")

    def wait_scan(self, w):
        waited = 0
        while w.scanner.busy and waited < 10000:
            QTest.qWait(20)
            waited += 20

    def test_hidden_on_the_start_screen_and_shown_in_the_workspace(self):
        f = self.lesson()
        w = self.window()
        w.show()
        self.assertFalse(w.explorer_dock.isVisible())
        w.open_path(f)
        self.assertTrue(w.explorer_dock.isVisible())
        w.stack.setCurrentIndex(0)
        self.assertFalse(w.explorer_dock.isVisible())

    def test_without_a_study_folder_it_lists_the_recent_files(self):
        f1, f2 = self.lesson("ex1"), self.lesson("ex2")
        w = self.window()
        w.open_path(f1)
        w.open_path(f2)
        self.assertIn("최근 파일", w.explorer.title.text())
        self.assertEqual(w.explorer.top_texts(), ["ex2 / Main.py", "ex1 / Main.py"])    # newest first

    def test_with_a_study_folder_it_shows_the_tree_and_the_open_file(self):
        f = self.lesson()
        self.lesson("ex2")
        self.seed(studyFolders=[str(self.root / "study")])
        w = self.window()
        self.wait_scan(w)
        w.open_path(f)
        self.assertIn("학습 폴더", w.explorer.title.text())
        self.assertEqual(w.explorer.top_texts(), ["study"])
        self.assertEqual(os.path.normcase(w.explorer.selected_path()), os.path.normcase(f))

    def test_clicking_a_file_in_the_explorer_opens_it(self):
        f1, f2 = self.lesson("ex1"), self.lesson("ex2")
        self.seed(studyFolders=[str(self.root / "study")])
        w = self.window()
        w.open_path(f1)
        root = w.explorer.tree.topLevelItem(0)
        ex2 = next(root.child(i) for i in range(root.childCount()) if root.child(i).text(0) == "ex2")
        ex2.setExpanded(True)
        w.explorer._on_clicked(ex2.child(0), 0)
        self.assertEqual(Path(w.py_path), Path(f2).resolve())
        self.assertEqual(os.path.normcase(w.explorer.selected_path()), os.path.normcase(f2))

    def test_ctrl_b_toggles_and_is_remembered(self):
        f = self.lesson()
        w = self.window()
        w.show()
        w.open_path(f)
        self.assertTrue(w.explorer_dock.isVisible())
        w.a_explorer.trigger()
        self.assertFalse(w.explorer_dock.isVisible())
        self.assertEqual(QSettings(self.ini, QSettings.IniFormat).value("view/explorer"), False)
        w2 = self.window()
        w2.show()
        w2.open_path(f)
        self.assertFalse(w2.explorer_dock.isVisible())
        w2.a_explorer.trigger()
        self.assertTrue(w2.explorer_dock.isVisible())

    def test_the_toggle_is_disabled_on_the_start_screen(self):
        w = self.window()
        self.assertFalse(w.a_explorer.isEnabled())
        w.open_path(self.lesson())
        self.assertTrue(w.a_explorer.isEnabled())

    def test_adding_a_study_folder_switches_the_list_from_recent_to_tree(self):
        f = self.lesson()
        w = self.window()
        w.open_path(f)
        self.assertIn("최근 파일", w.explorer.title.text())
        self.seed(studyFolders=[str(self.root / "study")])
        w._fill_recent()
        self.assertIn("학습 폴더", w.explorer.title.text())


if __name__ == "__main__":
    unittest.main()
