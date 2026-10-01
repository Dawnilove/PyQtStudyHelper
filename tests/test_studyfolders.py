"""Study folders: where the open dialog starts, what its left-hand shortcuts show, how they are stored."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings                                  # noqa: E402
from PyQt5.QtWidgets import QApplication, QFileDialog               # noqa: E402

from studyhelper import studyfolders as sf                          # noqa: E402


class TempDirs(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def mkdir(self, name) -> str:
        p = self.root / name
        p.mkdir(parents=True, exist_ok=True)
        return str(p)

    def missing(self, name) -> str:
        return str(self.root / name)              # never created


class StartDir(TempDirs):
    def test_open_file_folder_comes_first(self):
        cur, last, study = self.mkdir("cur"), self.mkdir("last"), self.mkdir("study")
        self.assertEqual(sf.start_dir(cur, last, [study]), cur)

    def test_last_opened_folder_when_no_file_is_open(self):
        last, study = self.mkdir("last"), self.mkdir("study")
        self.assertEqual(sf.start_dir("", last, [study]), last)

    def test_missing_current_folder_falls_back_to_last(self):
        last = self.mkdir("last")
        self.assertEqual(sf.start_dir(self.missing("gone"), last, []), last)

    def test_missing_last_folder_falls_back_to_first_study_folder(self):
        study = self.mkdir("study")
        self.assertEqual(sf.start_dir("", self.missing("gone"), [self.missing("old"), study]), study)

    def test_nothing_usable_still_gives_a_real_folder(self):
        result = sf.start_dir("", "", [self.missing("a")])
        self.assertTrue(Path(result).is_dir(), result)

    def test_none_or_odd_values_do_not_crash(self):
        result = sf.start_dir("", None, [])
        self.assertTrue(Path(result).is_dir(), result)


class Storage(TempDirs):
    def settings(self):
        return QSettings(str(self.root / "s.ini"), QSettings.IniFormat)

    def test_nothing_saved_gives_an_empty_list(self):
        self.assertEqual(sf.load_folders(self.settings()), [])

    def test_save_then_load_keeps_the_order(self):
        s, folders = self.settings(), [self.mkdir("b"), self.mkdir("a"), self.mkdir("c")]
        sf.save_folders(s, folders)
        self.assertEqual(sf.load_folders(self.settings()), folders)

    def test_a_single_folder_comes_back_as_a_list_not_a_string(self):
        s, one = self.settings(), self.mkdir("only")
        sf.save_folders(s, [one])
        s.sync()
        self.assertEqual(sf.load_folders(self.settings()), [one])

    def test_saving_an_empty_list_clears_it(self):
        s = self.settings()
        sf.save_folders(s, [self.mkdir("x")])
        sf.save_folders(s, [])
        s.sync()
        self.assertEqual(sf.load_folders(self.settings()), [])

    def test_folders_that_no_longer_exist_are_kept_in_storage_but_filtered_for_use(self):
        s, alive, gone = self.settings(), self.mkdir("alive"), self.missing("gone")
        sf.save_folders(s, [gone, alive])
        loaded = sf.load_folders(s)
        self.assertEqual(loaded, [gone, alive])
        self.assertEqual(sf.existing_folders(loaded), [alive])


class EditingTheList(TempDirs):
    def test_add_puts_the_new_folder_last(self):
        a, b = self.mkdir("a"), self.mkdir("b")
        self.assertEqual(sf.add_folder([a], b), [a, b])

    def test_adding_the_same_folder_twice_keeps_one(self):
        a = self.mkdir("a")
        self.assertEqual(sf.add_folder([a], a), [a])

    def test_same_folder_written_differently_counts_as_the_same(self):
        a = self.mkdir("a")
        again = a.replace("\\", "/").upper() if os.name == "nt" else a + "/"
        self.assertEqual(sf.add_folder([a], again), [a])

    def test_empty_path_is_ignored(self):
        a = self.mkdir("a")
        self.assertEqual(sf.add_folder([a], ""), [a])

    def test_remove_takes_the_folder_out(self):
        a, b = self.mkdir("a"), self.mkdir("b")
        self.assertEqual(sf.remove_folder([a, b], a), [b])

    def test_remove_of_an_unknown_folder_changes_nothing(self):
        a = self.mkdir("a")
        self.assertEqual(sf.remove_folder([a], self.missing("zzz")), [a])


class Sidebar(TempDirs):
    def test_study_folders_come_first_and_missing_ones_are_left_out(self):
        a, b = self.mkdir("a"), self.mkdir("b")
        paths = sf.sidebar_paths([a, self.missing("gone"), b])
        self.assertEqual(paths[:2], [a, b])
        self.assertNotIn(self.missing("gone"), paths)

    def test_no_folder_is_listed_twice(self):
        a = self.mkdir("a")
        paths = sf.sidebar_paths([a, a])
        keys = [os.path.normcase(os.path.normpath(p)) for p in paths]
        self.assertEqual(len(keys), len(set(keys)))

    def test_usual_places_are_still_there_after_the_study_folders(self):
        paths = sf.sidebar_paths([self.mkdir("a")])
        self.assertGreater(len(paths), 1)        # home / drives etc. follow the study folder


class Dialogs(TempDirs):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_file_dialog_starts_where_asked_and_is_not_the_native_one(self):
        start = self.mkdir("start")
        dlg = sf.make_file_dialog(None, "열기", start, "Python (*.py)", [])
        self.addCleanup(dlg.deleteLater)
        self.assertTrue(dlg.testOption(QFileDialog.DontUseNativeDialog))
        self.assertEqual(Path(dlg.directory().path()), Path(start))

    def test_file_dialog_shows_the_study_folders_on_the_left(self):
        a, b = self.mkdir("a"), self.mkdir("b")
        dlg = sf.make_file_dialog(None, "열기", a, "Python (*.py)", [a, b])
        self.addCleanup(dlg.deleteLater)
        first_two = [Path(u.toLocalFile()) for u in dlg.sidebarUrls()[:2]]
        self.assertEqual(first_two, [Path(a), Path(b)])

    def test_manage_dialog_lists_adds_and_removes(self):
        a, b = self.mkdir("a"), self.mkdir("b")
        dlg = sf.StudyFoldersDialog([a])
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg.folders(), [a])
        dlg.add_path(b)
        self.assertEqual(dlg.folders(), [a, b])
        dlg.view.setCurrentRow(0)
        dlg.remove_selected()
        self.assertEqual(dlg.folders(), [b])
        self.assertEqual(dlg.view.count(), 1)

    def test_manage_dialog_marks_a_folder_that_vanished(self):
        gone = self.missing("gone")
        dlg = sf.StudyFoldersDialog([gone])
        self.addCleanup(dlg.deleteLater)
        self.assertIn("찾을 수 없", dlg.view.item(0).text())
        self.assertEqual(dlg.folders(), [gone])            # still removable, so still listed

    def test_remove_with_nothing_selected_does_nothing(self):
        a = self.mkdir("a")
        dlg = sf.StudyFoldersDialog([a])
        self.addCleanup(dlg.deleteLater)
        dlg.view.setCurrentRow(-1)
        dlg.remove_selected()
        self.assertEqual(dlg.folders(), [a])


if __name__ == "__main__":
    unittest.main()
