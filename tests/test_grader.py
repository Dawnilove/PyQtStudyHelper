"""Code assignments: every task's .ui loads, a correct solution passes, typical mistakes fail with a useful message.

The grader runs in its own process, exactly like in the app.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from studyhelper import tasks

GRADER = Path(__file__).resolve().parent.parent / "studyhelper" / "grader.py"

SOLUTIONS = {
    "greet": '''
        self.btnGreet.clicked.connect(self.greet)

    def greet(self):
        self.lblResult.setText(f"안녕하세요, {self.edtName.text()}님!")
''',
    "counter": '''
        self.count = 0
        self.btnPlus.clicked.connect(self.plus)
        self.btnMinus.clicked.connect(self.minus)
        self.btnReset.clicked.connect(self.reset)

    def show_count(self):
        self.lblCount.setText(str(self.count))

    def plus(self):
        self.count += 1
        self.show_count()

    def minus(self):
        self.count -= 1
        self.show_count()

    def reset(self):
        self.count = 0
        self.show_count()
''',
    "add": '''
        self.btnAdd.clicked.connect(self.add)

    def add(self):
        try:
            s = int(self.edtA.text()) + int(self.edtB.text())
        except ValueError:
            self.lblResult.setText("숫자를 넣어 주세요")
            return
        self.lblResult.setText(str(s))
''',
    "agree": '''
        self.chkAgree.toggled.connect(self.btnNext.setEnabled)
''',
    "todo": '''
        self.btnAdd.clicked.connect(self.add)
        self.btnDelete.clicked.connect(self.delete)

    def add(self):
        text = self.edtItem.text().strip()
        if not text:
            return
        self.lstItems.addItem(text)
        self.edtItem.clear()

    def delete(self):
        row = self.lstItems.currentRow()
        if row >= 0:
            self.lstItems.takeItem(row)
''',
    "combo": '''
        self.cmbFruit.currentTextChanged.connect(lambda t: self.lblSelected.setText(f"고른 과일: {t}"))
''',
    "slider": '''
        self.sldVolume.valueChanged.connect(self.on_volume)

    def on_volume(self, value):
        self.lblValue.setText(str(value))
        self.prgVolume.setValue(value)
''',
    "hello_box": '''
        self.btnHello.clicked.connect(self.hello)

    def hello(self):
        QMessageBox.information(self, "인사", f"{self.edtName.text()}님 반가워요!")
''',
}
MARK = "        # TODO: 여기에서 시그널을 연결하세요\n"


def make(folder: Path, task, body=None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "task.ui").write_text(tasks.ui_xml(task), encoding="utf-8")
    src = tasks.starter_main(task)
    if body is not None:
        src = src.replace(MARK, body.lstrip("\n"))
    main = folder / "Main.py"
    main.write_text(src, encoding="utf-8")
    return main


def grade(task_id, main) -> dict:
    p = subprocess.run([sys.executable, str(GRADER), task_id, str(main)], capture_output=True, timeout=60,
                       encoding="utf-8", errors="replace")
    line = next(l for l in p.stdout.splitlines() if l.startswith("@@GRADE@@"))
    return json.loads(line[len("@@GRADE@@"):])


class Grader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_every_task_has_a_solution_here(self):
        self.assertEqual(set(SOLUTIONS), set(tasks.BY_ID))

    def test_correct_solutions_pass(self):
        for t in tasks.TASKS:
            with self.subTest(task=t.id):
                r = grade(t.id, make(self.root / t.id, t, SOLUTIONS[t.id]))
                self.assertIsNone(r["fatal"])
                failed = [x for x in r["results"] if not x["ok"]]
                self.assertEqual(failed, [])
                self.assertEqual(r["passed"], r["total"])

    def test_the_starter_file_loads_but_does_not_pass(self):
        t = tasks.BY_ID["greet"]
        r = grade(t.id, make(self.root / "s", t))
        self.assertIsNone(r["fatal"])
        self.assertEqual(r["passed"], 0)
        self.assertIn("'민수'", r["results"][0]["detail"])

    def test_hardcoded_name_fails_the_second_check(self):
        t = tasks.BY_ID["greet"]
        body = SOLUTIONS["greet"].replace('f"안녕하세요, {self.edtName.text()}님!"', '"안녕하세요, 민수님!"')
        r = grade(t.id, make(self.root / "h", t, body))
        self.assertEqual([x["ok"] for x in r["results"]], [True, False])

    def test_string_join_instead_of_sum_and_crash_on_letters(self):
        t = tasks.BY_ID["add"]
        body = '''
        self.btnAdd.clicked.connect(self.add)

    def add(self):
        self.lblResult.setText(str(int(self.edtA.text()) + int(self.edtB.text())))
'''
        r = grade(t.id, make(self.root / "a", t, body))
        oks = [x["ok"] for x in r["results"]]
        self.assertEqual(oks, [True, True, False])
        self.assertIn("ValueError", r["results"][2]["detail"])
        self.assertIn("줄:", r["results"][2]["detail"])                 # points at the student's line

    def test_connect_with_parentheses_is_explained(self):
        t = tasks.BY_ID["greet"]
        body = SOLUTIONS["greet"].replace("connect(self.greet)", "connect(self.greet())")
        r = grade(t.id, make(self.root / "c", t, body))
        self.assertIn("connect(self.함수)", r["fatal"])

    def test_missing_message_box(self):
        t = tasks.BY_ID["hello_box"]
        body = SOLUTIONS["hello_box"].replace('QMessageBox.information(self, "인사", f"{self.edtName.text()}님 반가워요!")',
                                              'print("hi")')
        r = grade(t.id, make(self.root / "m", t, body))
        self.assertFalse(r["results"][0]["ok"])
        self.assertIn("알림 창이 뜨지 않았어요", r["results"][0]["detail"])

    def test_syntax_error_is_fatal_with_message(self):
        t = tasks.BY_ID["greet"]
        r = grade(t.id, make(self.root / "x", t, "        self.btnGreet.clicked.connect(\n"))
        self.assertIn("Main.py를 불러오지 못했어요", r["fatal"])

    def test_ui_files_are_valid_designer_xml(self):
        import xml.etree.ElementTree as ET
        for t in tasks.TASKS:
            root = ET.fromstring(tasks.ui_xml(t))
            names = {w.get("name") for w in root.iter("widget")}
            for n in tasks.widget_names(t):
                self.assertIn(n.split(" ")[0], names)


if __name__ == "__main__":
    unittest.main()
