import os
import tempfile
import unittest
from pathlib import Path

from studyhelper import recovery


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["PYQTSTUDY_RECOVERY_DIR"] = str(Path(self.tmp.name) / "rec")
        self.addCleanup(os.environ.pop, "PYQTSTUDY_RECOVERY_DIR", None)
        self.f = Path(self.tmp.name) / "Main.py"

    def test_roundtrip(self):
        recovery.save(self.f, "print(1)\nprint(2)")
        self.assertEqual(recovery.load(self.f, "print(1)"), "print(1)\nprint(2)")

    def test_same_as_disk_is_not_offered(self):
        recovery.save(self.f, "a\r\nb")
        self.assertIsNone(recovery.load(self.f, "a\nb"))
        self.assertIsNone(recovery.load(self.f, "x"))         # and it was cleaned up

    def test_clear_and_missing(self):
        self.assertIsNone(recovery.load(self.f, ""))
        recovery.save(self.f, "z")
        recovery.clear(self.f)
        self.assertIsNone(recovery.load(self.f, ""))

    def test_each_file_has_its_own_backup(self):
        g = Path(self.tmp.name) / "Other.py"
        recovery.save(self.f, "one")
        recovery.save(g, "two")
        self.assertEqual(recovery.load(g, ""), "two")
        self.assertEqual(recovery.load(self.f, ""), "one")


if __name__ == "__main__":
    unittest.main()
