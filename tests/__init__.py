"""Tests never touch the student's real 학습 기록 (%APPDATA%/PyQtStudyHelper/learning.json)."""
import atexit
import os
import shutil
import tempfile

if "PYQTSTUDY_LOG_DIR" not in os.environ:
    _log_dir = tempfile.mkdtemp(prefix="pyqtstudy-log-")
    os.environ["PYQTSTUDY_LOG_DIR"] = _log_dir
    atexit.register(shutil.rmtree, _log_dir, True)
