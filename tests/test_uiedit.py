"""미리보기 간단 편집: add / delete / reorder widgets in the .ui — the result still loads in Designer's way."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMenu, QMessageBox, QWidget   # noqa: E402

from studyhelper import uiedit, uihistory                          # noqa: E402
from studyhelper.addwidgetdialog import AddWidgetDialog             # noqa: E402
from studyhelper.preview import load_for_preview                    # noqa: E402
from studyhelper.ui_model import UiModel                            # noqa: E402
from tests.test_helpers_ui import MAIN, UI                          # noqa: E402
from tests.test_tabs import WindowCase                              # noqa: E402

app = QApplication.instance() or QApplication([])

BOX = """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>MainWindow</class>
 <widget class="QMainWindow" name="MainWindow">
  <property name="geometry">
   <rect><x>0</x><y>0</y><width>400</width><height>300</height></rect>
  </property>
  <widget class="QWidget" name="centralwidget">
   <layout class="QVBoxLayout" name="verticalLayout">
    <item>
     <widget class="QPushButton" name="btnOk">
      <property name="text">
       <string>확인</string>
      </property>
     </widget>
    </item>
    <item>
     <layout class="QHBoxLayout" name="row1">
      <item>
       <widget class="QLabel" name="lblA">
        <property name="text">
         <string>A</string>
        </property>
        <property name="buddy">
         <cstring>edtA</cstring>
        </property>
       </widget>
      </item>
      <item>
       <widget class="QLineEdit" name="edtA"/>
      </item>
     </layout>
    </item>
    <item>
     <widget class="QGroupBox" name="grpGrid">
      <layout class="QGridLayout" name="gridLayout">
       <item row="0" column="0">
        <widget class="QCheckBox" name="chkA"/>
       </item>
      </layout>
     </widget>
    </item>
    <item>
     <spacer name="verticalSpacer">
      <property name="orientation">
       <enum>Qt::Vertical</enum>
      </property>
     </spacer>
    </item>
   </layout>
  </widget>
  <widget class="QMenuBar" name="menubar"/>
  <widget class="QStatusBar" name="statusbar"/>
 </widget>
 <tabstops>
  <tabstop>btnOk</tabstop>
  <tabstop>edtA</tabstop>
 </tabstops>
 <resources/>
 <connections>
  <connection>
   <sender>btnOk</sender>
   <signal>clicked()</signal>
   <receiver>MainWindow</receiver>
   <slot>close()</slot>
  </connection>
 </connections>
</ui>
"""

FREE = """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>Dialog</class>
 <widget class="QDialog" name="Dialog">
  <property name="geometry">
   <rect><x>0</x><y>0</y><width>300</width><height>120</height></rect>
  </property>
  <widget class="QPushButton" name="btnA">
   <property name="geometry">
    <rect><x>20</x><y>20</y><width>100</width><height>28</height></rect>
   </property>
  </widget>
  <widget class="QLabel" name="lblB">
   <property name="geometry">
    <rect><x>20</x><y>60</y><width>120</width><height>24</height></rect>
   </property>
  </widget>
  <widget class="QGroupBox" name="grpFree">
   <property name="geometry">
    <rect><x>160</x><y>10</y><width>120</width><height>100</height></rect>
   </property>
  </widget>
 </widget>
 <resources/>
 <connections/>
</ui>
"""


def order(model, layout):
    return [c.name for c in model.nodes[layout].children]


class Edit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.box = Path(self.tmp.name) / "box.ui"
        self.box.write_text(BOX, encoding="utf-8")
        self.free = Path(self.tmp.name) / "free.ui"
        self.free.write_text(FREE, encoding="utf-8")

    def loads(self, path, name=None):
        """The edited .ui still parses and builds real widgets."""
        m = UiModel(path)
        w = load_for_preview(path)
        self.addCleanup(w.deleteLater)
        if name:
            self.assertIsNotNone(w.findChild(QWidget, name))
        return m

    # ---------------------------------------------------------------- add
    def test_places_follow_the_layout_direction(self):
        self.assertEqual(uiedit.insert_places(self.box, "btnOk"),
                         ([("after", "btnOk 아래에"), ("before", "btnOk 위에")], None))
        self.assertEqual([k for k, _ in uiedit.insert_places(self.box, "edtA")[0]], ["after", "before"])
        self.assertIn("오른쪽", uiedit.insert_places(self.box, "edtA")[0][0][1])
        self.assertEqual(uiedit.insert_places(self.box, "MainWindow")[0], [("inside", "centralwidget 안 맨 아래에")])
        self.assertEqual(uiedit.insert_places(self.box, "row1")[0], [("inside", "row1 안 맨 끝에")])
        places, err = uiedit.insert_places(self.box, "chkA")                # in a grid: Designer only
        self.assertEqual(places, [])
        self.assertIn("Designer", err)
        self.assertEqual([k for k, _ in uiedit.insert_places(self.box, "grpGrid")[0]], ["after", "before"])

    def test_add_after_and_before_in_box_layouts(self):
        self.assertIsNone(uiedit.add_widget(self.box, "btnOk", "after", "QLabel", "lblNew", "안녕"))
        self.assertIsNone(uiedit.add_widget(self.box, "edtA", "before", "QPushButton", "btnNew", "눌러"))
        m = self.loads(self.box, "lblNew")
        self.assertEqual(order(m, "verticalLayout"), ["btnOk", "lblNew", "row1", "grpGrid"])
        self.assertEqual(order(m, "row1"), ["lblA", "btnNew", "edtA"])
        self.assertEqual(dict(m.nodes["lblNew"].props)["text"], "안녕")
        text = self.box.read_text(encoding="utf-8")
        self.assertIn('\n    <item>\n     <widget class="QLabel" name="lblNew">\n      <property name="text">', text)

    def test_inside_goes_before_a_trailing_spacer(self):
        self.assertIsNone(uiedit.add_widget(self.box, "MainWindow", "inside", "QLineEdit", "edtNew", "이름"))
        m = self.loads(self.box, "edtNew")
        self.assertEqual(order(m, "verticalLayout"), ["btnOk", "row1", "grpGrid", "edtNew"])
        items = [c for c in m.nodes["verticalLayout"].elem if c.tag == "item"]
        self.assertIsNotNone(items[-1].find("spacer"))                    # the spacer is still last
        self.assertEqual(dict(m.nodes["edtNew"].props)["placeholderText"], "이름")

    def test_items_slider_and_progress(self):
        uiedit.add_widget(self.box, "btnOk", "after", "QComboBox", "cmbFruit", "사과, 바나나,, 포도 ")
        uiedit.add_widget(self.box, "btnOk", "after", "QSlider", "sldNew")
        uiedit.add_widget(self.box, "btnOk", "after", "QProgressBar", "prgNew")
        self.loads(self.box)
        w = load_for_preview(self.box)
        self.addCleanup(w.deleteLater)
        cmb = w.findChild(QWidget, "cmbFruit")
        self.assertEqual([cmb.itemText(i) for i in range(cmb.count())], ["사과", "바나나", "포도"])
        self.assertEqual(w.findChild(QWidget, "prgNew").value(), 0)

    def test_grid_and_bad_names_are_refused(self):
        before = self.box.read_text(encoding="utf-8")
        self.assertIn("Designer", uiedit.add_widget(self.box, "chkA", "after", "QLabel", "lblX"))
        self.assertIn("이미 있는", uiedit.add_widget(self.box, "btnOk", "after", "QLabel", "edtA"))
        self.assertIn("이미 있는", uiedit.add_widget(self.box, "btnOk", "after", "QLabel", "verticalSpacer"))
        self.assertIn("이름 규칙", uiedit.add_widget(self.box, "btnOk", "after", "QLabel", "1abc"))
        self.assertIn("이름 규칙", uiedit.add_widget(self.box, "btnOk", "after", "QLabel", "class"))
        self.assertIn("이름 규칙", uiedit.add_widget(self.box, "btnOk", "after", "QLabel", "라벨"))
        self.assertIn("추가할 수 없어요", uiedit.add_widget(self.box, "btnOk", "after", "QWebView", "web"))
        self.assertIn("넣을 수 없어요", uiedit.add_widget(self.box, "btnOk", "inside", "QLabel", "lblX"))
        self.assertEqual(self.box.read_text(encoding="utf-8"), before)

    def test_add_without_a_layout_uses_free_space_and_grows_the_window(self):
        self.assertEqual([k for k, _ in uiedit.insert_places(self.free, "btnA")[0]], ["after"])
        self.assertIsNone(uiedit.add_widget(self.free, "btnA", "after", "QPushButton", "btnNew", "새 버튼"))
        m = self.loads(self.free, "btnNew")
        rect = dict(m.nodes["btnNew"].props)["geometry"]
        self.assertEqual(rect, "x=20, y=120, width=100, height=28")         # below everything, not over lblB
        self.assertEqual(dict(m.nodes["Dialog"].props)["geometry"], "x=0, y=0, width=300, height=160")
        self.assertIsNone(uiedit.add_widget(self.free, "grpFree", "inside", "QCheckBox", "chkIn", "켜기"))
        m = self.loads(self.free, "chkIn")
        self.assertIs(m.nodes["chkIn"].parent, m.nodes["grpFree"])
        self.assertEqual(dict(m.nodes["chkIn"].props)["geometry"], "x=20, y=20, width=140, height=24")

    def test_line_endings_and_header_survive(self):
        self.box.write_bytes(BOX.replace("\n", "\r\n").encode("utf-8"))
        uiedit.add_widget(self.box, "btnOk", "after", "QLabel", "lblNew")
        uiedit.move_widget(self.box, "lblNew", 1)
        uiedit.delete_widget(self.box, "lblNew")
        raw = self.box.read_bytes()
        self.assertTrue(raw.startswith(b'<?xml version="1.0" encoding="UTF-8"?>\r\n'))
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
        self.assertEqual(raw.decode("utf-8").replace("\r\n", "\n").replace(" />", "/>"),
                         BOX.replace(" />", "/>"))                          # add + move + delete = unchanged

    def test_names(self):
        taken = {"btnNew", "btnNew2"}
        self.assertEqual(uiedit.suggest_name("QPushButton", taken), "btnNew3")
        self.assertEqual(uiedit.suggest_name("QLabel", taken), "lblNew")
        self.assertIsNone(uiedit.name_problem("lblTitle", taken))
        self.assertIsNotNone(uiedit.name_problem("", taken))
        self.assertIn("verticalSpacer", uiedit.taken_names(self.box))

    def test_stretch_factors_stay_with_their_widgets(self):
        from PyQt5.QtWidgets import QLayout
        self.box.write_text(BOX.replace('name="verticalLayout">', 'name="verticalLayout" stretch="0,0,1,0">'),
                            encoding="utf-8")

        def factors():
            w = load_for_preview(self.box)
            self.addCleanup(w.deleteLater)
            lay = w.findChild(QLayout, "verticalLayout")
            out = {}
            for i in range(lay.count()):
                it = lay.itemAt(i)
                name = it.widget().objectName() if it.widget() else (it.layout().objectName() if it.layout() else "sp")
                out[name] = lay.stretch(i)
            return out
        self.assertEqual(factors()["grpGrid"], 1)
        uiedit.add_widget(self.box, "btnOk", "before", "QLabel", "lblTop")
        self.assertEqual(factors(), {"lblTop": 0, "btnOk": 0, "row1": 0, "grpGrid": 1, "sp": 0})
        uiedit.move_widget(self.box, "grpGrid", -1)
        self.assertEqual(factors(), {"lblTop": 0, "btnOk": 0, "grpGrid": 1, "row1": 0, "sp": 0})
        uiedit.delete_widget(self.box, "lblTop")
        self.assertEqual(factors(), {"btnOk": 0, "grpGrid": 1, "row1": 0, "sp": 0})
        self.assertIn('stretch="0,1,0,0"', self.box.read_text(encoding="utf-8"))
        uiedit.delete_widget(self.box, "grpGrid")
        self.assertNotIn("stretch=", self.box.read_text(encoding="utf-8"))  # all 0: Designer leaves it out

    def test_containers_grow_so_the_new_widget_is_visible(self):
        uiedit.add_widget(self.free, "grpFree", "inside", "QPushButton", "btn1", "1")
        uiedit.add_widget(self.free, "grpFree", "inside", "QPushButton", "btn2", "2")
        uiedit.add_widget(self.free, "grpFree", "inside", "QPushButton", "btn3", "3")
        w = load_for_preview(self.free)
        self.addCleanup(w.deleteLater)
        w.show()
        for name in ("btn1", "btn2", "btn3"):
            b = w.findChild(QWidget, name)
            self.assertFalse(b.visibleRegion().isEmpty(), name)
        grp = w.findChild(QWidget, "grpFree")
        self.assertTrue(w.rect().contains(grp.geometry()))
        # a container in a layout asks the layout for room instead
        self.box.write_text(BOX.replace('<widget class="QGroupBox" name="grpGrid">\n      <layout class="QGridLayout" '
                                        'name="gridLayout">\n       <item row="0" column="0">\n        <widget '
                                        'class="QCheckBox" name="chkA"/>\n       </item>\n      </layout>\n     </widget>',
                                        '<widget class="QGroupBox" name="grpGrid"/>'), encoding="utf-8")
        uiedit.add_widget(self.box, "grpGrid", "inside", "QListWidget", "lstIn")
        self.assertIn("minimumSize", dict(UiModel(self.box).nodes["grpGrid"].props))

    # ---------------------------------------------------------------- delete
    def test_delete_removes_the_widget_and_every_reference(self):
        err, gone = uiedit.delete_widget(self.box, "edtA")
        self.assertIsNone(err)
        self.assertEqual(gone, ["edtA"])
        text = self.box.read_text(encoding="utf-8")
        self.assertNotIn("edtA", text)                                       # tab stop + QLabel buddy too
        self.assertIn("<tabstop>btnOk</tabstop>", text)
        err, gone = uiedit.delete_widget(self.box, "btnOk")
        self.assertIsNone(err)
        text = self.box.read_text(encoding="utf-8")
        self.assertNotIn("<connection>", text)
        self.assertNotIn("<tabstops>", text)                                 # empty: removed
        err, gone = uiedit.delete_widget(self.box, "grpGrid")
        self.assertEqual(gone, ["grpGrid", "gridLayout", "chkA"])
        m = self.loads(self.box)
        self.assertEqual(order(m, "verticalLayout"), ["row1"])

    def test_delete_refuses_window_central_and_layouts(self):
        before = self.box.read_text(encoding="utf-8")
        for name, want in (("MainWindow", "최상위"), ("centralwidget", "가운데 칸"), ("row1", "Designer"),
                           ("nothing", "찾지 못했어요")):
            with self.subTest(name=name):
                self.assertIn(want, uiedit.delete_widget(self.box, name)[0])
        self.assertEqual(self.box.read_text(encoding="utf-8"), before)
        m = UiModel(self.box)
        self.assertIsNone(uiedit.why_not_delete(m, "statusbar"))
        self.assertIn("가운데 칸", uiedit.why_not_delete(m, "centralwidget"))
        self.assertIsNone(uiedit.why_not_delete(m, "chkA"))

    def test_delete_last_free_widget(self):
        uiedit.delete_widget(self.free, "grpFree")
        m = self.loads(self.free)
        self.assertEqual([c.name for c in m.top.children], ["btnA", "lblB"])
        self.assertIn("  </widget>\n </widget>", self.free.read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- move
    def test_move_in_box_layouts(self):
        m = UiModel(self.box)
        self.assertEqual(uiedit.move_info(m, "btnOk"), (False, True, False))
        self.assertEqual(uiedit.move_info(m, "edtA"), (True, False, True))
        self.assertEqual(uiedit.move_info(m, "grpGrid"), (True, True, False))   # the spacer counts as a place
        self.assertIsNone(uiedit.move_info(m, "chkA"))
        self.assertIsNone(uiedit.move_info(m, "MainWindow"))
        self.assertIsNone(uiedit.move_widget(self.box, "btnOk", 1))
        self.assertIsNone(uiedit.move_widget(self.box, "edtA", -1))
        m = self.loads(self.box)
        self.assertEqual(order(m, "verticalLayout"), ["row1", "btnOk", "grpGrid"])
        self.assertEqual(order(m, "row1"), ["edtA", "lblA"])
        self.assertIn("맨 앞", uiedit.move_widget(self.box, "row1", -1))
        self.assertIn("Designer", uiedit.move_widget(self.box, "chkA", 1))
        self.assertIn("Designer", uiedit.move_widget(self.free, "btnA", 1))
        uiedit.move_widget(self.box, "btnOk", -1)
        uiedit.move_widget(self.box, "edtA", 1)
        self.assertEqual(self.box.read_text(encoding="utf-8").replace(" />", "/>"), BOX.replace(" />", "/>"))


class Dialog(unittest.TestCase):
    def test_name_is_suggested_until_the_student_types_one(self):
        dlg = AddWidgetDialog({"btnNew", "lblNew"}, [("after", "btnOk 아래에"), ("before", "btnOk 위에")])
        self.addCleanup(dlg.deleteLater)
        ok = dlg.buttons.button(dlg.buttons.Ok)
        self.assertEqual(dlg.name.text(), "btnNew2")
        self.assertEqual(dlg.text.text(), "버튼")
        dlg.cls.setCurrentIndex(dlg.cls.findData("QSpinBox"))
        self.assertEqual(dlg.name.text(), "spnNew")
        self.assertTrue(dlg.text.isHidden())
        dlg.name.setText("lblNew")
        self.assertFalse(ok.isEnabled())
        self.assertIn("이미 있는", dlg.info.text())
        dlg.name.clear()
        dlg.name.textEdited.emit("x")                                      # typed by the student
        dlg.name.setText("spnAge")
        dlg.cls.setCurrentIndex(dlg.cls.findData("QComboBox"))
        self.assertEqual(dlg.name.text(), "spnAge")                         # kept
        self.assertIn("self.spnAge", dlg.info.text())
        dlg.places.button(1).setChecked(True)
        self.assertEqual(dlg.values(), ("QComboBox", "spnAge", "사과, 바나나, 포도", "before"))
        self.assertTrue(ok.isEnabled())


class InWindow(WindowCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(uihistory.clear)
        self.ui = self.root / "gui.ui"
        self.ui.write_text(UI, encoding="utf-8")
        self.w.open_path(self.make("Main.py", MAIN + "        self.edtName.setText('x')\n"))

    def test_add_selects_the_new_widget_and_can_be_undone(self):
        self.w.select("btnOk", "tree")
        with mock.patch.object(AddWidgetDialog, "exec_", return_value=1), \
                mock.patch.object(AddWidgetDialog, "values", return_value=("QLabel", "lblHello", "안녕", "after")):
            self.w.add_widget_dialog()
        self.assertIn("lblHello", self.w.model.nodes)
        self.assertEqual(self.w.sel, "lblHello")
        self.assertIsNotNone(self.w.preview.find("lblHello"))
        self.assertIn("lblHello", self.w._items)
        self.assertIn("lblHello 추가", self.w.a_undo_ui.text())
        self.w.undo_ui()
        self.assertEqual(self.ui.read_text(encoding="utf-8"), UI)
        self.assertNotIn("lblHello", self.w.model.nodes)

    def test_nothing_selected_adds_to_the_window(self):
        self.w.sel = None
        seen = {}

        def fake_exec(dlg):
            seen["places"] = [dlg.places.button(i).text() for i in range(len(dlg._keys))]
            return 0
        with mock.patch.object(AddWidgetDialog, "exec_", fake_exec):
            self.w.add_widget_dialog()
        self.assertEqual(seen["places"], ["centralwidget 안 맨 아래에"])

    def test_delete_asks_mentions_the_code_and_can_be_undone(self):
        asked = {}

        def answer(parent, title, text, *a):
            asked["text"] = text
            return QMessageBox.Yes
        with mock.patch.object(QMessageBox, "question", answer):
            self.w.delete_selected("edtName")
        self.assertIn("1곳에서 쓰고 있어요", asked["text"])
        self.assertNotIn("edtName", self.w.model.nodes)
        self.assertEqual(self.w.sel, "centralwidget")
        self.w.undo_ui()
        self.assertIn("edtName", self.w.model.nodes)
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            self.w.delete_selected("edtName")
        self.assertIn("edtName", self.w.model.nodes)

    def test_move_and_errors_do_not_change_the_file(self):
        self.w.move_selected(1, "btnOk")
        self.assertEqual([c.name for c in self.w.model.nodes["verticalLayout"].children], ["edtName", "btnOk"])
        self.assertEqual(self.w.sel, "btnOk")
        before = self.ui.read_text(encoding="utf-8")
        with mock.patch.object(QMessageBox, "information") as info:
            self.w.move_selected(1, "btnOk")                                # already last
            info.assert_called_once()
        self.assertEqual(self.ui.read_text(encoding="utf-8"), before)
        self.assertEqual(uihistory.last_label(self.ui), "btnOk 옮기기")          # the failed try left no step
        # the file couldn't even be read for the snapshot: the older step must survive the failure
        with mock.patch.object(uihistory, "snapshot", return_value=False), \
                mock.patch.object(QMessageBox, "information"):
            self.assertFalse(self.w._apply_ui_edit("x", lambda: "읽지 못했어요"))
        self.assertEqual(uihistory.last_label(self.ui), "btnOk 옮기기")

    def test_widget_menu_has_edit_entries(self):
        shown = {}

        def fake_exec(menu, *a):
            shown[menu.title()] = [(a.text(), a.isEnabled()) for a in menu.actions() if a.text()]
        with mock.patch.object(QMenu, "exec_", fake_exec):
            self.w._widget_menu("btnOk", self.w.mapToGlobal(self.w.rect().center()))
            items = dict(shown[""])
            shown.clear()
            self.w._widget_menu("centralwidget", self.w.mapToGlobal(self.w.rect().center()))
            central = dict(shown[""])
        self.assertTrue(items["위젯 추가…"])
        self.assertFalse(items["위로 옮기기"])
        self.assertTrue(items["아래로 옮기기"])
        self.assertTrue(items["위젯 삭제…"])
        self.assertIn("위젯 추가…", central)
        self.assertNotIn("위젯 삭제…", central)
        self.assertNotIn("위로 옮기기", central)


if __name__ == "__main__":
    unittest.main()
