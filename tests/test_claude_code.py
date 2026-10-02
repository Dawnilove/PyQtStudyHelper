"""ai.find_claude: finds the Claude Code in the folder layouts the Claude desktop app has used."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from studyhelper import ai                                          # noqa: E402


class FindClaude(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.roam = self.root / "Roaming"
        self.local = self.root / "Local"
        self.home = self.root / "home"
        for d in (self.roam, self.local, self.home):
            d.mkdir()
        env = {"APPDATA": str(self.roam), "LOCALAPPDATA": str(self.local), "USERPROFILE": str(self.home),
               "HOME": str(self.home)}
        p1 = mock.patch.dict(os.environ, env)
        p1.start()
        self.addCleanup(p1.stop)
        p2 = mock.patch("studyhelper.ai.shutil.which", lambda name: None)       # not on PATH
        p2.start()
        self.addCleanup(p2.stop)

    def exe(self, *parts) -> str:
        p = self.roam.joinpath("Claude", "claude-code", *parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"MZ")
        return str(p)

    def test_nothing_installed(self):
        self.assertIsNone(ai.find_claude())

    def test_old_layout_version_folder(self):
        want = self.exe("2.1.284", "claude.exe")
        self.assertEqual(ai.find_claude(), want)

    def test_new_layout_has_a_hash_folder_below_the_version(self):
        want = self.exe("2.1.286", "635c1867224a", "claude.exe")
        self.assertEqual(ai.find_claude(), want)

    def test_newest_version_wins_across_both_layouts(self):
        self.exe("2.1.284", "claude.exe")
        self.exe("2.1.285", "3f4bed3e44ad", "claude.exe")
        want = self.exe("2.1.286", "635c1867224a", "claude.exe")
        self.assertEqual(ai.find_claude(), want)

    def test_versions_compare_as_numbers(self):
        self.exe("2.1.9", "aaa", "claude.exe")
        want = self.exe("2.1.10", "bbb", "claude.exe")
        self.assertEqual(ai.find_claude(), want)

    def test_microsoft_store_install_location(self):
        pkg = self.local / "Packages" / "Claude_abc123" / "LocalCache" / "Roaming" / "Claude" / "claude-code"
        exe = pkg / "2.1.286" / "635c1867224a" / "claude.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"MZ")
        self.assertEqual(ai.find_claude(), str(exe))

    def test_folders_without_the_exe_are_ignored(self):
        (self.roam / "Claude" / "claude-code" / "2.1.287" / "deadbeef").mkdir(parents=True)     # still downloading
        want = self.exe("2.1.286", "635c1867224a", "claude.exe")
        self.assertEqual(ai.find_claude(), want)

    def test_the_standalone_install_is_found_too(self):
        exe = self.home / ".local" / "bin" / "claude.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"MZ")
        self.assertEqual(ai.find_claude(), str(exe))

    def test_status_says_what_to_do_when_missing(self):
        ok, msg = ai.claude_code_status()
        self.assertFalse(ok)
        self.assertIn("찾지 못했어요", msg)


if __name__ == "__main__":
    unittest.main()
