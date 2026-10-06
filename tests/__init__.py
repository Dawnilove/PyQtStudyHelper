"""Tests never touch the student's real 학습 기록 (%APPDATA%/PyQtStudyHelper/learning.json)."""
import atexit
import os
import shutil
import tempfile

# GitHub's Windows runner hands out the 8.3 short name (C:\Users\RUNNER~1\...), but Qt and resolve() answer with the
# long one (runneradmin): compare equal paths as equal by making every temp folder start from the long form.
tempfile.tempdir = os.path.realpath(tempfile.gettempdir())

if "PYQTSTUDY_LOG_DIR" not in os.environ:
    _log_dir = tempfile.mkdtemp(prefix="pyqtstudy-log-")
    os.environ["PYQTSTUDY_LOG_DIR"] = _log_dir
    atexit.register(shutil.rmtree, _log_dir, True)
