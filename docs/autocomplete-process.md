# 자동완성 기능 개발 기록

> 이 문서는 AI(와 사람)가 이 기능이 **왜 이렇게 만들어졌는지** 읽고 이어서 작업할 수 있도록 남긴 기록이다.
> 날짜: 2026-10-01. 작업 환경: Windows 10, Python 3.14.7, PyQt5 5.15.11 (Qt 5.15.2), jedi 0.20.0 / parso 0.8.7.

## 1. 한 줄 요약

`Main.py` 편집기(`CodeEditor`)에 **자동완성**을 추가했다. 코드를 치면 후보 팝업이 뜨고 **Tab**으로 완성된다.
`self.` 뒤에는 `.ui`의 위젯 이름, `self.위젯.` 뒤에는 그 위젯 클래스의 메서드·시그널, 그 밖에는 `jedi`가 PyQt5 클래스·변수·키워드를 준다.

## 2. 사용자 요구와 결정 (사용자가 직접 정한 것)

| 항목 | 결정 | 근거 |
|---|---|---|
| 기능 필요성 | 편집기에 자동완성이 없어서 넣기로 함 | `editor.py`는 `QPlainTextEdit` + 줄 번호 + 하이라이트 + hover뿐이었음 |
| 후보 범위 | 키워드·현재 파일 단어 / `self.` 뒤 `.ui` 위젯 이름 / `self.위젯.` 뒤 메서드·시그널 / PyQt5 클래스·모듈 이름 **전부** | 사용자가 4개 모두 선택, "VS Code 정도 수준으로는 어렵겠지?"라고 물음 |
| VS Code 수준 | **완전 동일은 불가, 가깝게**: 후보 목록·종류 표시까지. 자동 import·깊은 타입 추론·시그니처 팝업은 제외 | 아래 4장 참고 |
| 수락 키 | **Tab만** 수락. Enter는 수락하지 않고 팝업만 닫고 줄바꿈 | 사용자: "탭을 누르면 자동완성되도록". 단어를 다 친 뒤 Enter가 줄바꿈이 안 되는 불편을 피함 |
| 새 의존성 | `jedi` 설치 승인 | 설계 안내 때 "jedi 설치도 승인에 포함"이라고 밝히고 승인받음 |
| 진행 방식 | bounded(기존 편집기에 기능 추가) → 채팅에서 짧은 설계 → 승인 → TDD | `superpowers:brainstorming`, `superpowers:test-driven-development` |

## 3. 설계

**방식**: `jedi`가 일반 파이썬 완성을 맡고, `.ui` 정보로 만든 후보를 그 앞에 붙인다.

| 입력 | 후보 | 출처 |
|---|---|---|
| `de`, `imp` | 키워드, 현재 파일의 변수·함수 | jedi (없으면 자체 키워드 + 파일 단어) |
| `QtWi`, `QPu`, `Qt.Al` | PyQt5 모듈·클래스·상수 | jedi (PyQt5 `.pyi` 스텁) |
| `self.pu` | `.ui` 위젯 이름 (`위젯` 표시) | `.ui` 모델 (`node.name`) |
| `self.pushButton.` | 그 위젯 클래스의 시그널·메서드 | `.ui` 모델 (`node.cls`) + PyQt5 클래스 `dir()` |

`self.위젯.`을 jedi에 맡기지 않은 이유: `uic.loadUi()`로 불러오는 코드는 위젯의 타입이 런타임에야 정해져 jedi가 모른다.
시그널과 메서드는 `isinstance(attr, QtCore.pyqtSignal)`로 구분한다 (시그널을 먼저 보여 줌).

**동작 규칙**
- 식별자를 **2글자 이상** 치거나 `.`을 치면 150ms 뒤에 요청한다. `Ctrl+Space`는 글자 수와 상관없이 즉시 요청한다.
- 주석과 문자열 안에서는 후보를 내지 않는다.
- 이미 완전히 친 단어와 같은 후보는 목록에서 뺀다 (Tab이 아무 일도 안 하는 팝업을 막기 위해).
- ↑↓ 선택(끝에서 반대쪽으로 돌아감), Esc 닫기, 방향키·클릭·포커스 아웃·그 밖의 키는 팝업을 닫는다.
- 수락은 `beginEditBlock`/`endEditBlock`으로 감싸 **Ctrl+Z 한 번**에 되돌아간다.
- `jedi`가 없으면 에러 없이 키워드·파일 단어·`.ui` 후보만 나온다 (`Completer(use_jedi=...)`, `has_jedi`).

## 4. 실측 결과와 그에 따른 설계 변경

설계 단계에서는 "느리면 스레드로"라고 위험으로만 적었는데, 확인해 보니 **처음부터 스레드가 필요**했다.

| 측정 (이 PC) | 시간 |
|---|---|
| jedi 첫 호출 (PyQt5 스텁 파싱) | 2.4초 ~ 5초 |
| `jedi.preload_module(QtWidgets, QtCore, QtGui)` | 약 1.4초 |
| 그 뒤 첫 로컬 변수 멤버 완성 | 약 1.3초 |
| 이후 호출 | 40 ~ 290ms |

→ jedi 호출은 **백그라운드 스레드 하나**(`_CompletionWorker`)에서 하고, 앱이 편집기를 만들 때 `warmup()`으로 미리 데운다.
최신 요청만 처리하고(이전 요청은 버림), 결과는 시그널로 UI 스레드에 돌려준다.
요청 번호(`_req_id`)와 요청 당시 커서 위치(`_asked_at`)가 현재와 다르면 늦게 온 결과를 버린다.

**Tab이 글자를 망가뜨리는 문제를 막은 방법**: 팝업이 `pu` 기준으로 떠 있는데 사용자가 빠르게 `sh`를 더 치고 Tab을 누르면, 새 답이 오기 전이라 `sh`(2글자)가 후보로 덮어써져 `self.puspushButton`이 될 수 있다.
→ 글자를 칠 때마다 이미 떠 있는 목록을 **그 자리에서 좁히고**(`narrow`) `_prefix_len`도 같이 갱신한다. 일치하는 게 없으면 팝업을 닫는다. (테스트 `test_tab_right_after_fast_typing_does_not_corrupt_the_text`)

## 5. 파일 지도

| 파일 | 역할 |
|---|---|
| `studyhelper/completer.py` (신규) | 후보 만들기. Qt 이벤트 루프 없이 테스트 가능한 순수 로직. `Completer.complete(source, line, col, force)` → `(items, prefix_len)`, 줄·열은 0부터 |
| `studyhelper/editor.py` | `_CompletionWorker`(스레드), `_CompletionPopup`/`_KindDelegate`(목록 창), `CodeEditor`의 키 처리·수락. `set_widgets({이름: 클래스})` 추가 |
| `studyhelper/mainwindow.py` | `set_names(...)` 3곳을 `set_widgets(...)`로 교체 (`.ui`의 `node.name → node.cls` 전달) |
| `tests/test_completer.py` | 후보 로직 27개 (`.ui` 후보, 키워드·단어, 주석·문자열, jedi) |
| `tests/test_editor_autocomplete.py` | 편집기 동작 18개 (오프스크린 Qt에서 실제 키 입력) |
| `requirements.txt`, `README.md` | `jedi>=0.19` 추가, 기능 설명 |

## 6. 테스트

```bash
python -m unittest discover -s tests -t .
```

- 결과: **45개 통과** (후보 로직 27 + 편집기 동작 18), 약 7초.
- `pytest`는 이 PC에 없어서 표준 `unittest`를 썼다.
- 실제 앱 창 확인(오프스크린 `MainWindow`에 임시 `.ui` + `Main.py`를 열고 입력): `self.pu` → Tab → `self.pushButton`, 이어서 `.cl` → Tab → `self.pushButton.clicked` 확인.
  이 확인에서는 앱 설정을 임시 ini로 돌렸다고 생각했지만 **그 방법은 효과가 없었다** (7장 7번). 그래서 확인 중 실제 앱 설정(레지스트리)이 바뀌었을 수 있다.
  나중에 점검해서 임시 경로가 섞인 값을 원래대로 되돌렸다 (10장).
- TDD 순서: 테스트 먼저 작성 → 실패 확인(모듈/메서드 없음) → 구현 → 통과. 테스트 작성 중 틀린 부분 2곳(불필요한 `setUp()` 재호출, Backspace 횟수)은 실행 전에 고쳤다.

## 7. 함정 (다음 사람이 같은 데서 막히지 않도록)

1. **`QTest.keyClicks(widget, "\n")`는 이 환경에서 프로세스를 죽인다.** 종료 코드 `0xC0000409`, 메시지 없음. 순정 `QPlainTextEdit`에서도 재현되므로 구현 버그가 아니다 (PyQt5 5.15.11 + Python 3.14). 줄바꿈은 `QTest.keyClick(w, Qt.Key_Return)`로 보낸다.
2. **PyQt5는 슬롯·이벤트 핸들러 안의 처리 안 된 파이썬 예외에서 프로세스를 중단**시킨다. 이때 `0xC0000409`가 나온다. `keyPressEvent` 안 코드를 고칠 때 예외가 새지 않게 한다.
3. **저장소 파일은 CRLF**다 (`core.autocrlf=true`, `git ls-files --eol`에서 `i/crlf w/crlf`). Git Bash의 `sed -i`로 고치면 CR이 사라져 diff가 파일 전체로 부풀었다 (`mainwindow.py` 3줄 수정이 2,204줄 변경으로 보임).
   복구: `sed -i 's/$/\r/' 파일`. 고친 뒤 `git diff --stat`으로 의도한 줄만 바뀌었는지 확인한다. 편집은 Edit 도구를 쓰면 줄바꿈이 유지된다.
4. 이 PC는 `QT_QPA_PLATFORM_PLUGIN_PATH`가 낡은 값일 수 있어 `run.py`가 보정한다. 테스트는 `QT_QPA_PLATFORM=offscreen`으로 돌린다.
5. `jedi`는 스레드에 안전하지 않다고 보고 **스레드 하나**에서만 호출한다. 호출을 병렬화하지 말 것.
6. 지금은 `.py` 파일 경로를 jedi에 넘기지 않아 `from gui import Ui_MainWindow` 같은 이웃 파일 import는 해석하지 못한다 (아래 8장).
7. **`QSettings.setDefaultFormat(...)`과 `QSettings.setPath(...)`로는 이 앱의 설정을 격리할 수 없다.** 앱이 `QSettings("PyQtStudyHelper", "PyQtStudyHelper")`처럼 조직·앱 이름으로 만들면 Windows에서는 기본 형식(레지스트리)이 쓰이기 때문이다.
   실제 `MainWindow`를 띄워 파일을 열거나 폴더를 저장하는 확인 스크립트는 `HKCU\Software\PyQtStudyHelper`의 `recent`, `lastFile`, `lastDir`, `studyFolders`를 **진짜로 바꾼다**.
   격리하려면 `MainWindow`를 만들기 전에 클래스를 바꿔 끼운다:
   ```python
   import studyhelper.mainwindow as M
   M.QSettings = lambda *a, **k: QSettings(r"임시경로\isolated.ini", QSettings.IniFormat)
   ```
   이렇게 한 뒤 실제 설정의 키 개수와 해시가 전후로 같은지 비교해서 확인했다.

## 8. 남은 일 (이번 커밋에 없음)

- **시그니처 팝업**(함수 괄호 안 인자 안내): 일부러 제외.
- **`self.위젯.시그널.` 뒤** (`.connect`, `.emit`): 후보가 안 나온다. `loadUi` 방식 코드는 jedi가 타입을 모른다. 시그널 객체용 후보(`connect`, `disconnect`, `emit`)를 `.ui` 후보 쪽에 추가하면 된다.
- **이웃 파일 해석**: `jedi.Script(source, path=...)`와 `jedi.Project`를 쓰면 `gui.py`의 `Ui_*` 클래스를 해석할 수 있다.
- 큰 파일에서 느리면 `toPlainText()` 전달 방식을 줄이는 것도 고려.

### 같은 날 추가로 요청받은 기능

학습 폴더 등록과 파일 열기 시작 위치는 자동완성과 별개의 작업이라 따로 설계 확인을 받고 구현했다. 10장 참고.

## 9. 작업 환경 메모 (참고)

- 저장소는 처음에 `D:\git_down\Vibecoding`에 클론했다가, 사용자가 `C:\git_down\pyQt`에 직접 클론하길 원해 그쪽에 다시 클론했다. D 쪽 클론은 삭제했다.
  `D:\git_down` 빈 폴더는 도구가 삭제를 막아 남아 있다.
- `git`에 커밋 작성자(`user.name`, `user.email`)가 설정돼 있지 않았다. 이 저장소의 기존 커밋 작성자는 `Dawnilove`다.
- 저장소에 `.gitignore`가 없어 `__pycache__/`가 추적 안 된 파일로 잡힌다. 커밋할 때 파일을 하나씩 지정해서 올렸다.

## 10. 학습 폴더 등록 + 파일 열기 시작 위치 (같은 날 후속 작업)

> 자동완성 PR(`feature/autocomplete`) 위에서 이어서 작업했다. 이 장의 변경은 커밋 `b241cf3`(코드)·`8fedad3`(문서)로 PR #1에 담겨 `Dawnilove/Vibecoding`의 `main`에 병합됐다(병합 커밋 `4c1bd2d`).

### 요구와 결정

| 항목 | 결정 |
|---|---|
| 학습 폴더 등록 | **파일 열기 창 왼쪽 바로가기**로 보여 준다 (사용자 선택). 시작 화면 목록 방식은 채택하지 않음 |
| 파일 열기 시작 폴더 | 열린 파일의 폴더 → 마지막에 연 폴더 → 첫 학습 폴더 → 내 문서(없으면 홈) |
| 창 모양 | Qt 자체 파일 창으로 바뀐다. 윈도우 탐색기 모양의 기본 창은 왼쪽 바로가기를 추가할 수 없다. 설계 때 알리고 승인받음 |

"이전에 열었던 폴더에서 시작"은 **이미 구현돼 있었다** (`open_path`가 `lastDir`를 저장하고 `open_dialog`가 읽음). 이번에는 그 폴더가 지워졌거나 옮겨졌을 때 다음 순위로 넘어가는 처리만 더했다.
사용자가 안 된다고 느낀 원인은 재현하지 못했다. 처음 설치 직후라 저장된 값이 없었거나, 폴더 안쪽에서 시작해서 옆 폴더로 옮기기 불편했던 것으로 추정한다.

### 구현

- `studyhelper/studyfolders.py` (신규): 순수 함수(`start_dir`, `load_folders`, `save_folders`, `add_folder`, `remove_folder`, `existing_folders`, `sidebar_paths`)와 `make_file_dialog`/`pick_file`, 관리 창 `StudyFoldersDialog`.
- `studyhelper/mainwindow.py`: 파일 메뉴에 "학습 폴더 관리…", `_pick_file()` 하나로 **열기**와 **도전 모드 .ui 고르기** 두 창을 같은 방식으로 연다.
- 저장 위치: `QSettings`의 `studyFolders` (문자열 목록). 없어진 폴더는 저장은 유지하고(관리 창에서 "폴더를 찾을 수 없어요"로 표시해 지울 수 있게) 바로가기·시작 위치에서는 건너뛴다.
- 바로가기 순서: 학습 폴더(있는 것만) → 홈·바탕화면·문서·다운로드 → 드라이브(C:, D: …). 중복은 경로를 정규화해서 제거한다 (`normcase` + `normpath`).
- `QSettings`가 목록 1개를 문자열로 돌려주는 PyQt 함정은 방어 코드와 테스트를 넣었다. 이 PC(PyQt5 5.15.11, Python 3.14)에서는 레지스트리·ini 모두 목록으로 정상 왕복해서 함정이 **나타나지는 않았다**.

### 테스트

- `tests/test_studyfolders.py` 25개 (시작 폴더 우선순위, 저장·읽기, 목록 편집, 바로가기, 파일 창·관리 창).
- 전체: `python -m unittest discover -s tests -t .` → **70개 통과** (자동완성 45 + 학습 폴더 25).
- 실제 `MainWindow`를 오프스크린으로 띄워 확인 (설정은 7장 7번 방식으로 격리): 메뉴에 항목이 보이고, 저장하면 목록이 남고, 파일도 마지막 폴더도 없으면 첫 학습 폴더에서 시작하고, 마지막 폴더가 지워지면 첫 학습 폴더로 넘어가고, 파일 창 바로가기 맨 앞 두 칸이 학습 폴더였다.
- **눈으로 못 본 것**: Qt 자체 파일 창이 실제 화면에 어떻게 보이는지(오프스크린이라 그려진 모습은 확인 못 함). 사람이 한 번 열어 봐야 한다.

### 사고 기록: 확인 작업이 실제 앱 설정을 바꿈

위 확인 스크립트를 처음 돌렸을 때 설정 격리가 안 돼서(7장 7번) `HKCU\Software\PyQtStudyHelper`가 바뀌었다.
바뀐 것: `studyFolders`(원래 없던 값)가 생기고, `lastDir`·`lastFile`이 임시 폴더로 바뀌고, `recent` 맨 앞에 임시 파일이 들어갔다.
조치: Qt(`QSettings`)로 직접 되돌렸다 — 임시 경로가 섞인 `recent` 항목을 지우고, `lastFile`은 `recent`의 첫 항목으로, `lastDir`은 그 파일의 폴더로 복원, `studyFolders`는 삭제. 되돌린 값은 확인 직전에 관찰한 `lastDir`(`...\1. Standard Dialog\ex4_1_04`)와 일치한다.
한계: 원래 `lastFile`은 직접 관찰하지 못하고 `recent` 첫 항목으로 추정한 값이다. 앱을 열었을 때 마지막 파일이 예전과 다르면 이 때문일 수 있다.

## 11. 학습 폴더의 Main 파일을 최근 파일 자리에 보여 주기 (같은 날 후속 작업)

> 이 장의 변경은 커밋 `ca34d3c`(코드)·`ded878e`(문서)이고, PR #1이 이미 병합된 뒤에 만들어져서 **후속 PR**로 보냈다.
> (PR #1에 푸시해도 병합이 끝난 PR에는 커밋이 반영되지 않는다는 점을 푸시한 뒤에야 확인했다.)

### 요구와 결정

요청: "학습폴더 내부에 있는 main파일들 위치를 최근파일 위치에 등록해줘".
이 PC의 학습 폴더(`Desktop\Python Study`)에는 `main.py`(대소문자 무관)가 **55개**인데 최근 파일은 최대 10개(`r[:10]`)라, 그대로 넣으면 직접 연 최근 파일이 전부 밀려난다.

| 항목 | 결정 |
|---|---|
| 보이는 방식 | **최근 파일 아래 '학습 폴더' 구역으로 따로** (사용자 선택). 합치기·한 번만 채우기는 채택하지 않음 |
| 저장 | 저장하는 `recent`에는 **넣지 않음**. 보여 주기만 한다 |
| 찾는 파일 | 이름이 `main.py`인 파일(대소문자 무관). `Main_sol.py`, `main_wnd.py`, `Main2.py` 등은 제외 (`locate.main_py_in`과 같은 기준) |
| 찾는 범위 | 하위 폴더 6단계까지, 폴더당 500개까지. `.`으로 시작하는 폴더와 `__pycache__`, `node_modules`, `venv`, `env`, `site-packages`는 건너뜀 |
| 다시 찾는 때 | 앱 시작, 학습 폴더 저장, 시작 화면으로 돌아올 때(30초에 한 번까지) |

### 구현

- `studyhelper/studyfolders.py`: `find_main_files()`(숫자를 자연 정렬, `lesson2`가 `lesson10`보다 앞), `main_label()`(학습 폴더 기준 상대 경로 `ex1 / Main.py`), `MainFilesScanner`(백그라운드 스레드, 최신 요청만 전달).
- `studyhelper/mainwindow.py`: `_fill_recent()`가 `_fill_study_sections()`를 불러 시작 화면 목록과 최근 파일 메뉴(학습 폴더별 하위 메뉴)에 구역을 붙인다. `_rescan_study(force=False)`가 찾기를 시작한다.
- 찾는 동안 구역 제목에 `(찾는 중…)`, 파일이 없으면 `(Main 파일이 없어요)`, 다 찾으면 `(55개)`처럼 표시한다. 구역 제목은 선택할 수 없다.
- 초기화 순서 주의: `_fill_recent()`와 `_on_page_changed(0)`이 `_build_ui()` 안에서 불리므로 `self.scanner`는 `_build_ui()` **전에** 만들어야 한다.

### 테스트

- `tests/test_studyfolders.py`: 찾기·라벨·스캐너 18개 추가 (파일 전체 43개).
- `tests/test_mainwindow_study.py` (신규): 실제 `MainWindow`를 오프스크린으로 띄우는 16개. 설정은 `QSettings` 클래스를 교체해 격리했다 (7장 7번).
- 전체: `python -m unittest discover -s tests -t .` → **104개 통과** (자동완성 45 + 학습 폴더 43 + 창 연결 16).
- 이 PC의 실제 학습 폴더를 읽기 전용으로 찾아 확인: **0.28초에 Main 파일 55개**, 시작 화면 목록 57줄(없음 표시 1 + 구역 제목 1 + 파일 55), 메뉴 하위 메뉴 항목 55개, `recent`에는 아무것도 저장되지 않음. 실제 앱 설정은 전후 키 개수·해시가 같았다.
- **눈으로 못 본 것**: 목록과 메뉴가 실제 화면에 어떻게 그려지는지. 특히 55개짜리 하위 메뉴가 화면에서 어떻게 스크롤되는지는 사람이 열어 봐야 한다.

### 겪은 함정

- 확인 스크립트의 `print`가 `cp949` 콘솔에서 `—`(긴 줄표) 때문에 `UnicodeEncodeError`로 멈췄다. `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`로 실행한다. 구역 제목에 `—`를 쓰므로 콘솔로 찍는 코드는 주의.
- 이번 확인 중 실제 설정의 `studyFolders`가 이미 있었다 (사용자가 앱에서 직접 `Desktop\Python Study`를 등록한 것). 확인 스크립트는 격리돼 있어 이 값을 건드리지 않았다.
