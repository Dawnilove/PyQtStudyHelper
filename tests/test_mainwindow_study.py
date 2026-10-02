"""MainWindow: Main files of the study folders appear under the recent files (offscreen, settings isolated)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings, Qt                              # noqa: E402
from PyQt5.QtTest import QTest                                      # noqa: E402
from PyQt5.QtWidgets import QApplication, QDialog                   # noqa: E402

import studyhelper.mainwindow as mw                                 # noqa: E402
from studyhelper import studyfolders as sf                          # noqa: E402


class StudySection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.ini = str(self.root / "settings.ini")
        # The app builds QSettings("PyQtStudyHelper", "PyQtStudyHelper") itself; setDefaultFormat does not
        # redirect that on Windows (it would write the real registry), so the class is swapped instead.
        patcher = mock.patch.object(mw, "QSettings", lambda *a, **k: QSettings(self.ini, QSettings.IniFormat))
        patcher.start()
        self.addCleanup(patcher.stop)

    # ---- helpers
    def lessons(self, study="Study", names=("l1", "l2", "l3")) -> str:
        folder = self.root / study
        for n in names:
            (folder / n).mkdir(parents=True, exist_ok=True)
            (folder / n / "Main.py").write_text("", encoding="utf-8")
        return str(folder)

    def seed(self, **values):
        s = QSettings(self.ini, QSettings.IniFormat)
        for k, v in values.items():
            s.setValue(k, v)
        s.sync()

    def window(self):
        w = mw.MainWindow()
        self.addCleanup(w.deleteLater)
        return w

    def wait_scan(self, w, timeout_ms=10000):
        waited = 0
        while w.scanner.busy and waited < timeout_ms:
            QTest.qWait(20)
            waited += 20
        self.assertFalse(w.scanner.busy, "study folder scan did not finish")

    def texts(self, w):
        return [w.recent_list.item(i).text() for i in range(w.recent_list.count())]

    # ---- start screen list
    def test_study_folder_gets_its_own_section_with_every_main_file(self):
        study = self.lessons()
        self.seed(studyFolders=[study])
        w = self.window()
        self.wait_scan(w)
        texts = self.texts(w)
        header = [t for t in texts if t.startswith("학습 폴더 — Study")]
        self.assertEqual(len(header), 1, texts)
        self.assertIn("(3개)", header[0])
        entries = [w.recent_list.item(i).data(Qt.UserRole) for i in range(w.recent_list.count())
                   if w.recent_list.item(i).data(Qt.UserRole)]
        self.assertEqual(entries, [str(Path(study) / n / "Main.py") for n in ("l1", "l2", "l3")])

    def test_entries_are_labelled_relative_to_the_study_folder(self):
        study = self.lessons(names=("lesson1",))
        self.seed(studyFolders=[study])
        w = self.window()
        self.wait_scan(w)
        self.assertIn("lesson1 / Main.py", self.texts(w))

    def test_header_is_not_selectable(self):
        self.seed(studyFolders=[self.lessons()])
        w = self.window()
        self.wait_scan(w)
        header = next(w.recent_list.item(i) for i in range(w.recent_list.count())
                      if w.recent_list.item(i).text().startswith("학습 폴더 —"))
        self.assertEqual(header.flags(), Qt.NoItemFlags)

    def test_real_recent_files_stay_first_and_are_not_touched(self):
        study = self.lessons(names=tuple(f"l{n}" for n in range(12)))      # more than the 10 that "recent" keeps
        mine = []
        for n in range(2):
            p = self.root / f"mine{n}.py"
            p.write_text("", encoding="utf-8")
            mine.append(str(p))
        self.seed(studyFolders=[study], recent=mine)
        w = self.window()
        self.wait_scan(w)
        first = [w.recent_list.item(i).data(Qt.UserRole) for i in range(2)]
        self.assertEqual(first, mine)
        self.assertEqual(w.settings.value("recent"), mine)                 # nothing was written into "recent"
        self.assertEqual(len([t for t in self.texts(w) if t.endswith("Main.py")]), 12)

    def test_without_study_folders_the_list_is_as_before(self):
        w = self.window()
        self.wait_scan(w)
        self.assertEqual(self.texts(w), ["(아직 없음)"])

    def test_a_folder_without_any_main_file_says_so(self):
        empty = self.root / "Empty"
        empty.mkdir()
        self.seed(studyFolders=[str(empty)])
        w = self.window()
        self.wait_scan(w)
        self.assertTrue(any("Main 파일이 없어요" in t for t in self.texts(w)), self.texts(w))

    def test_while_searching_the_list_says_so(self):
        self.seed(studyFolders=[self.lessons()])
        w = self.window()                          # nothing has processed events yet: the scan is still "running"
        self.assertTrue(w.scanner.busy)
        self.assertTrue(any("찾는 중" in t for t in self.texts(w)), self.texts(w))
        self.wait_scan(w)

    def test_section_disappears_when_the_folder_is_removed(self):
        self.seed(studyFolders=[self.lessons()])
        w = self.window()
        self.wait_scan(w)
        sf.save_folders(w.settings, [])
        w._fill_recent()
        self.assertEqual(self.texts(w), ["(아직 없음)"])

    def test_two_study_folders_make_two_sections(self):
        a, b = self.lessons("A", ("x",)), self.lessons("B", ("y", "z"))
        self.seed(studyFolders=[a, b])
        w = self.window()
        self.wait_scan(w)
        self.assertEqual(len([t for t in self.texts(w) if t.startswith("학습 폴더 —")]), 2)

    def test_activating_an_entry_opens_that_file(self):
        study = self.lessons(names=("l1",))
        self.seed(studyFolders=[study])
        w = self.window()
        self.wait_scan(w)
        item = next(w.recent_list.item(i) for i in range(w.recent_list.count())
                    if w.recent_list.item(i).data(Qt.UserRole))
        with mock.patch.object(w, "open_path") as opened:
            w.recent_list.itemActivated.emit(item)
        opened.assert_called_once_with(str(Path(study) / "l1" / "Main.py"))

    # ---- menu
    def study_menus(self, w):
        return [a.menu() for a in w.recent_menu.actions() if a.menu() is not None]

    def test_recent_menu_has_a_submenu_per_study_folder(self):
        study = self.lessons()
        self.seed(studyFolders=[study])
        w = self.window()
        self.wait_scan(w)
        menus = self.study_menus(w)
        self.assertEqual(len(menus), 1)
        self.assertTrue(menus[0].title().startswith("학습 폴더 — Study"))
        self.assertEqual([a.text() for a in menus[0].actions()],
                         ["l1 / Main.py", "l2 / Main.py", "l3 / Main.py"])
        self.assertTrue(w.recent_menu.isEnabled())

    def test_submenu_entry_opens_the_file(self):
        study = self.lessons(names=("l1",))
        self.seed(studyFolders=[study])
        w = self.window()
        self.wait_scan(w)
        with mock.patch.object(w, "open_path") as opened:
            self.study_menus(w)[0].actions()[0].trigger()
        opened.assert_called_once_with(str(Path(study) / "l1" / "Main.py"))

    def test_recent_menu_stays_disabled_with_nothing_to_show(self):
        w = self.window()
        self.wait_scan(w)
        self.assertFalse(w.recent_menu.isEnabled())

    # ---- when it searches again
    def test_saving_study_folders_searches_again(self):
        study = self.lessons()
        w = self.window()
        self.wait_scan(w)
        self.assertEqual(self.texts(w), ["(아직 없음)"])

        def fake_exec(dlg):
            dlg.add_path(study)
            return QDialog.Accepted
        with mock.patch.object(sf.StudyFoldersDialog, "exec_", fake_exec):
            w.manage_study_folders()
        self.wait_scan(w)
        self.assertTrue(any(t.startswith("학습 폴더 — Study") for t in self.texts(w)), self.texts(w))

    def test_going_back_to_the_start_screen_searches_again_but_not_more_than_every_30_seconds(self):
        w = self.window()
        self.wait_scan(w)
        with mock.patch.object(w.scanner, "scan") as scan:
            w._rescan_study()                      # just scanned at start-up: too soon
            scan.assert_not_called()
            w._rescan_study(force=True)
            scan.assert_called_once()

    def test_after_30_seconds_the_start_screen_searches_again(self):
        w = self.window()
        self.wait_scan(w)
        w._scan_at -= 31
        with mock.patch.object(w.scanner, "scan") as scan:
            w._rescan_study()
            scan.assert_called_once()


if __name__ == "__main__":
    unittest.main()
