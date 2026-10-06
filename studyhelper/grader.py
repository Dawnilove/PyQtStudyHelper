"""코드 과제 채점기. Runs in its OWN process (never inside the helper):

    python grader.py <task id> <path/to/Main.py>

Imports the student's Main.py (its `if __name__ == "__main__":` part does not run), makes the window,
plays the task's steps (type text, click, choose …) on an offscreen screen and prints one JSON line:
{"results": [{"ok", "label", "detail"}], "fatal": "...", "passed": n, "total": n}
Message boxes and dialogs are recorded instead of shown, so nothing waits for a click.
"""
import importlib.util
import json
import re
import os
import sys
import traceback
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt5.QtWidgets import (QAbstractButton, QAbstractSlider, QAbstractSpinBox, QApplication,  # noqa: E402
                             QComboBox, QDialog, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit,
                             QProgressBar, QTextEdit, QWidget)

from studyhelper.tasks import BY_ID                                                          # noqa: E402

MSGBOXES: list[str] = []         # texts of message boxes the student's code opened
ERRORS: list[str] = []           # exceptions raised inside the student's slots
MAIN: list = []                  # [resolved path of the Main.py being graded]


def _record_box(*args, **kwargs):
    texts = [a for a in args if isinstance(a, str)]
    MSGBOXES.append(" ".join(texts))
    return QMessageBox.Ok


def _patch_dialogs():
    for name in ("information", "warning", "critical", "about"):
        setattr(QMessageBox, name, staticmethod(_record_box))
    QMessageBox.question = staticmethod(lambda *a, **k: (_record_box(*a), QMessageBox.Yes)[1])

    def box_exec(self, *a):
        MSGBOXES.append(f"{self.windowTitle()} {self.text()} {self.informativeText()}")
        return QMessageBox.Ok
    QMessageBox.exec_ = box_exec
    QMessageBox.exec = box_exec
    QDialog.exec_ = lambda self, *a: 0
    QDialog.exec = lambda self, *a: 0


def _student_frame(tb, main_path) -> str:
    """'12줄: self.lblResult.setText(name)' — the student's line where it went wrong."""
    for fs in reversed(traceback.extract_tb(tb)):
        if Path(fs.filename).resolve() == main_path:
            return f"{fs.lineno}줄: {(fs.line or '').strip()}"
    return ""


def _excepthook(main_path):
    def hook(t, e, tb):
        where = _student_frame(tb, main_path)
        ERRORS.append(f"{t.__name__}: {e}" + (f"  ({where})" if where else ""))
    return hook


def find_window(module):
    """The window class the student wrote (a QWidget subclass defined in Main.py)."""
    found = [c for c in vars(module).values()
             if isinstance(c, type) and issubclass(c, QWidget) and c.__module__ == module.__name__]
    found.sort(key=lambda c: (issubclass(c, QDialog), not hasattr(c, "setupUi")))
    errors = []
    for cls in found:
        try:
            return cls(), None
        except TypeError as e:
            where = _student_frame(e.__traceback__, MAIN[0]) if MAIN else ""
            if where and re.search(r"\.connect\(\s*self\.\w+\([^()]*\)\s*\)", where):
                return None, (f"{cls.__name__}() 를 만드는 중 에러 ({where}) → connect(self.함수()) 처럼 괄호를 "
                              "붙이면 지금 바로 실행돼요. connect(self.함수) 로 이름만 넘기세요.")
            if where:
                return None, f"{cls.__name__}() 를 만드는 중 에러: {type(e).__name__}: {e}  ({where})"
            errors.append(f"{cls.__name__}: {e}")       # needs arguments: try the next class
        except Exception as e:
            where = _student_frame(e.__traceback__, MAIN[0]) if MAIN else ""
            return None, (f"{cls.__name__}() 를 만드는 중 에러: {type(e).__name__}: {e}"
                          + (f"  ({where})" if where else ""))
    if not found:
        return None, "Main.py에서 창 클래스(QMainWindow / QWidget 을 상속한 class)를 찾지 못했어요."
    return None, "창 클래스를 만들 수 없어요: " + "; ".join(errors)


def _get(w, attr):
    if attr == "text":
        return w.toPlainText() if isinstance(w, (QTextEdit, QPlainTextEdit)) else w.text()
    if attr == "value":
        return w.value()
    if attr == "enabled":
        return w.isEnabled()
    if attr == "checked":
        return w.isChecked()
    if attr == "count":
        return w.count()
    if attr == "item0":
        it = w.item(0)
        return it.text() if it is not None else None
    if attr == "visible":
        return w.isVisibleTo(w.window())
    raise ValueError(attr)


def _set(w, value):
    if isinstance(w, (QTextEdit, QPlainTextEdit)):
        w.setPlainText(value)
    elif isinstance(w, QLineEdit):
        w.setText(value)
    elif isinstance(w, (QAbstractSpinBox, QAbstractSlider, QProgressBar)):
        w.setValue(value)
    elif isinstance(w, QComboBox):
        w.setCurrentIndex(value)
    elif isinstance(w, QListWidget):
        w.setCurrentRow(value)
    elif isinstance(w, QAbstractButton):
        w.setChecked(value)
    else:
        raise TypeError(type(w).__name__)


def _show(v) -> str:
    if isinstance(v, bool):
        return "켜짐" if v else "꺼짐"
    return f"'{v}'" if isinstance(v, str) else str(v)


def grade(task_id: str, main_path: str) -> dict:
    task = BY_ID[task_id]
    main = Path(main_path).resolve()
    MAIN[:] = [main]
    os.chdir(main.parent)                       # loadUiType("task.ui") etc. are relative to Main.py
    sys.path.insert(0, str(main.parent))
    app = QApplication.instance() or QApplication([])
    _patch_dialogs()
    sys.excepthook = _excepthook(main)
    out = {"results": [], "fatal": None}
    try:
        spec = importlib.util.spec_from_file_location("student_main", main)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except SystemExit:
        out["fatal"] = ("Main.py를 불러올 때 프로그램이 끝나 버렸어요. sys.exit(...) 를 "
                        "if __name__ == \"__main__\": 아래에 두세요.")
        return out
    except Exception as e:
        where = _student_frame(e.__traceback__, main)
        msg = f"{type(e).__name__}: {e}" + (f"  ({where})" if where else "")
        if "QApplication" in str(e):
            msg += "  → QApplication(...) 은 if __name__ == \"__main__\": 아래에서 만들어요."
        out["fatal"] = "Main.py를 불러오지 못했어요: " + msg
        return out
    win, err = find_window(module)
    if win is None:
        out["fatal"] = err
        return out
    win.show()
    app.processEvents()

    def widget(name):
        w = getattr(win, name, None)
        if not isinstance(w, QWidget):
            w = win.findChild(QWidget, name)
        if w is None:
            raise LookupError(f"{name} 위젯을 찾지 못했어요. task.ui의 이름을 바꿨나요?")
        return w

    def add(ok, label, detail=""):
        out["results"].append({"ok": bool(ok), "label": label, "detail": detail})

    seen_errors = 0
    for step in task.steps:
        kind = step[0]
        try:
            if kind == "set":
                _set(widget(step[1]), step[2])
            elif kind == "click":
                widget(step[1]).click()
            elif kind == "expect":
                _, name, attr, op, want, label = step
                got = _get(widget(name), attr)
                if op == "eq":
                    ok = got == want
                    detail = "" if ok else f"{name}: {_show(want)} 이어야 하는데 지금은 {_show(got)} 이에요."
                elif op == "contains":
                    ok = isinstance(got, str) and str(want) in got
                    detail = "" if ok else f"{name}에 {_show(want)} 가 들어 있어야 하는데 지금은 {_show(got)} 이에요."
                else:
                    raise ValueError(op)
                add(ok, label, detail)
            elif kind == "msgbox":
                _, want, label = step
                hit = next((t for t in reversed(MSGBOXES) if want in t), None)
                add(hit is not None, label, "" if hit else
                    (f"알림 창 내용에 '{want}' 가 없어요: '{MSGBOXES[-1].strip()}'" if MSGBOXES
                     else "알림 창이 뜨지 않았어요."))
                MSGBOXES.clear()
            elif kind == "no_error":
                new = ERRORS[seen_errors:]
                add(not new, step[1], ("에러가 났어요: " + new[0]) if new else "")
                seen_errors = len(ERRORS)
            app.processEvents()
        except LookupError as e:
            add(False, f"{step[1]} 준비", str(e))
            break
        except Exception as e:
            where = _student_frame(e.__traceback__, main)
            add(False, "채점 중 에러", f"{type(e).__name__}: {e}" + (f"  ({where})" if where else ""))
            break
        # an exception inside the student's slot while doing this step
        if kind in ("set", "click") and len(ERRORS) > seen_errors and not any(s[0] == "no_error" for s in task.steps):
            add(False, "실행 중 에러", ERRORS[seen_errors])
            seen_errors = len(ERRORS)
    if ERRORS[seen_errors:]:
        add(False, "실행 중 에러", ERRORS[seen_errors])
    out["passed"] = sum(r["ok"] for r in out["results"])
    out["total"] = len(out["results"])
    return out


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in BY_ID:
        print(json.dumps({"fatal": "사용법: grader.py <과제 id> <Main.py>", "results": []}))
        return
    try:
        result = grade(sys.argv[1], sys.argv[2])
    except BaseException as e:                  # never leave the helper without an answer
        result = {"fatal": f"채점기 에러: {type(e).__name__}: {e}", "results": []}
    sys.stdout.write("@@GRADE@@" + json.dumps(result, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    os._exit(0)                                 # skip Qt teardown of the student's window


if __name__ == "__main__":
    main()
