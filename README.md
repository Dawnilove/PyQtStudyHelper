# PyQt 학습 도우미

Qt Designer로 만든 `.ui`와 직접 짜는 `Main.py`를 **나란히 놓고 연결해서 보는** PyQt5 학습용 도구.

## 설치 (처음 한 번)

1. [Python 3.10 이상](https://www.python.org/downloads/) 설치 — 설치 화면에서 **Add python.exe to PATH** 체크
2. 이 폴더의 **`install.bat`** 더블클릭 → 필요한 패키지 설치 + 바탕화면 아이콘 생성
3. AI 해설은 **설치 직후 바로 무료로** 쓸 수 있음 (기본값: 웹 AI 방식, 키 필요 없음). API 키가 있으면 AI 메뉴 → AI 모델·키 설정에서 바꾸면 답이 앱 안에 바로 나옴
4. (선택) 내 노트: 보기 → 내 노트 폴더 연결 (Obsidian 볼트나 .md 노트 폴더)

## 다른 사람에게 주기

`install.bat` 하나만으로는 안 되고 **폴더 전체**가 필요함 (`run.py`, `studyhelper/`, `tools/`, `requirements.txt` 등).
배포용 zip 만들기 (git 기록·임시 파일 제외):

```bash
git archive --format=zip --prefix=PyQtStudyHelper/ -o ../PyQtStudyHelper.zip HEAD
```

받는 사람: zip 압축 풀기 → `PyQtStudyHelper\install.bat` 더블클릭 → 바탕화면 아이콘으로 실행.
API 키·노트 폴더는 각자 앱에서 설정 (zip에는 들어 있지 않음).

## 실행

- **바탕화면 `PyQt 학습 도우미` 아이콘** 더블클릭 (또는 `PyQt 학습 도우미 실행.bat`). 파이썬/.ui 파일을 아이콘 위에 끌어다 놓거나, 실행 중인 창에 끌어다 놓아도 열림.
- 명령줄: `python run.py "경로/Main.py"` (.ui 파일이나 폴더도 가능)
- 프로그램 자체 오류는 창으로 알려 주고 `error.log`에 남김.

## 화면

| 영역 | 하는 일 |
|---|---|
| 실시간 미리보기 | `uic.loadUi()`로 만든 실제 위젯. 클릭하면 그 위젯이 선택됨 (버튼 동작은 막힘) |
| 위젯 트리 | `.ui` 안의 위젯·레이아웃 계층. 레이아웃은 회색 기울임 |
| Main.py | 편집 가능 (Ctrl+S 저장). `.ui`에 있는 `self.이름`은 파랗게 표시, 마우스를 올리면 선택 |
| 선택한 위젯 | 클래스·위치 / 속성 표(흰 칸은 더블클릭해 수정 → `.ui`에 저장) / Main.py에서 쓰는 곳 / 시그널(→ 연결 코드 넣기) / 코드로 보기 / `.ui 원본` / 내 노트 |
| 해설 · 줄 해설 | 클릭한 줄이 **무엇을 하는지 / 왜 이렇게 썼는지 / 주의할 점** (오프라인, 실습에 자주 나오는 구문 위주) + 이 줄이 어느 함수 안에 있고 무엇이 실행시키는지 |
| 해설 · AI 해설 | 선택한 줄 설명(Ctrl+E), 파일 전체 리뷰, 이어서 질문하기 (Claude API, 내 API 키 필요) |
| 실행 결과 | ▶ 실행(F5) 출력과 에러, 에러 해설. `File "...", line N` 줄을 클릭하면 이동 |
| 검사 | 이름 검사 결과 목록 (클릭하면 이동) |

## 동작

- **.ui 자동 찾기**: 파이썬 파일을 열면 ① `from gui import ...`처럼 import한 모듈 → ② 코드 속 `'gui.ui'`, `f'{GUI_FILE_NAME}.ui'` 같은 문자열 → ③ 같은 폴더의 `.ui` 순서로 찾음. 후보가 여럿이면 툴바 드롭다운에서 바꿈. `.ui`를 열면 그걸 쓰는 `.py`(Main.py 우선)를 찾아 엶.
- **자동 갱신**: Designer에서 `.ui`를 저장하면 미리보기·트리·속성이 바로 다시 불러와짐 (선택 유지). Main.py가 밖에서 바뀌어도 다시 불러옴 (저장 안 한 편집이 있으면 건드리지 않음).
- **실행 안전장치**: ▶ 실행 시 Main.py가 `gui`를 import하는데 `gui.py`가 없거나 `gui.ui`보다 오래됐으면 먼저 다시 만들어 줌.
- **이름 검사기** (입력할 때마다): `.ui`에 없는 `self.이름`은 빨간 물결 밑줄 + 비슷한 이름 제안, 없는 슬롯 함수는 주황 밑줄, 문법 오류, pyuic 변환 파일과 import 모듈 불일치 경고. Main.py에서 안 쓰는 위젯은 트리에서 흐리게.
- **에러 해설**: 실행이 에러로 끝나면 AttributeError·ImportError·NameError·슬롯 인자 개수·타입 오류 등을 쉬운 말로 풀고, 에러 난 줄로 이동해 빨갛게 표시.
- **Designer에서 열기** (Ctrl+D): 현재 `.ui`를 Qt Designer로 엶 (`PyQt5Designer` 패키지의 designer.exe).
- **AI 해설 설정**: 메뉴 AI → AI 모델·키 설정. 모델을 고르고 그 회사 키를 붙여넣고 [연결 테스트] → [저장]. 키는 회사별로 Windows 자격 증명 관리자에 저장되고 파일·저장소에는 남지 않음 (환경변수 `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`가 있으면 우선).
  | 회사 | 모델 | 비용 |
  |---|---|---|
  | 웹 AI (기본) | ChatGPT 웹 / Gemini 웹 / Claude 웹 | **무료, 키 필요 없음** — 질문을 복사해 웹 창을 열어 주고, 웹에서 답의 복사 버튼을 누르면 답이 앱으로 들어옴 |
  | Google | Gemini 3.8 Flash (기본), 3.5 Flash-Lite / 3.1 Pro | Flash 계열 **무료 티어** (사용량 제한, 입력이 Google 제품 개선에 쓰일 수 있음) / Pro 유료 |
  | 내 PC | Ollama 모델 (예: `qwen3:8b`) | **완전 무료**, 인터넷 불필요, PC 성능 필요 |
  | Anthropic | Claude Opus 5.5 / Sonnet 5.5 / Haiku 4.5 | 유료 |
  | OpenAI | GPT-6 Astra / GPT-6.1 Sol / GPT-6 Luna | 유료 |
  목록에 없는 새 모델은 모델 칸에 이름을 직접 입력하면 됨.
- **시그널 도우미**: 시그널 탭에서 시그널을 더블클릭 → 슬롯 이름을 정하고 미리 본 뒤 [Main.py에 넣기]. `__init__`의 connect 줄 모음 끝에 연결 줄, 클래스 끝에 인자까지 맞춘 함수 틀이 들어감 (초록 표시, Ctrl+Z 한 번에 되돌리기). 이미 연결돼 있으면 그 줄로 이동. `on_위젯_시그널` 이름은 setupUi가 자동 연결해 두 번 실행되므로 피하도록 안내·검사.
- **.ui 값 고치기**: text·title·숫자·true/false 같은 단순 속성은 속성 표에서 바로 고치면 `.ui`에 저장 (바뀐 줄만 바뀌고 줄바꿈·형식 유지). 복잡한 속성은 Designer에서.
- **내 노트 연결**: 보기 → 내 노트 폴더 연결로 **직접 연결한** 폴더에서, 위젯 클래스가 나오는 노트 섹션을 찾아 보여 줌. 더블클릭하면 Obsidian 볼트는 Obsidian에서 그 제목으로, 일반 폴더는 기본 앱으로 열림. 줄 해설에도 관련 노트 링크.
- **objectName 바꾸기** (F2, 위젯 트리 우클릭): `.ui`의 이름과 모든 참조(시그널/슬롯 편집기, 탭 순서, 버튼 그룹, 메뉴 액션)와 Main.py의 `self.이름`을 한꺼번에 바꿈. 최상위 창이면 `Ui_클래스` 이름과 import 줄까지. 미리보기 후 적용, Main.py는 Ctrl+Z로 되돌리기.
- **도전 모드** (Ctrl+T): 목표 화면 `.ui`(예제·정답)를 고르면 왼쪽에 목표 화면, 오른쪽에 체크리스트. [빈 .ui 만들어서 시작] → Designer에서 만들고 저장할 때마다 위젯 종류·개수, 레이아웃, 글자, (보너스) objectName을 자동 채점.
- **색 범례**: 코드 아래에 색 표시 뜻이 늘 보임 (보기 → 색 범례 보기로 끄기).
- **편의 기능**: 시작 화면과 최근 파일, 메뉴·단축키(F1 사용법), Ctrl+휠로 코드 글자 크기, 보기 → 화면 배치 초기화, 현재 줄 강조.

## 단계 계획

1. ✅ 미리보기, 속성 패널(코드로 보기), Main.py 연동, `.ui` 자동 감지, 실행
2. ✅ 이름 검사기, 에러 해설과 줄 이동, 바로 실행 아이콘
3. ✅ 줄 해설(오프라인) + AI 해설·코드 리뷰, 사용 편의 개선
4. ✅ 시그널 도우미, `.ui` 값 고치기, 내 노트 연결, 색 범례
5. ✅ objectName 바꾸기, 도전 모드, AI 여러 회사(Gemini 무료·Ollama 무료·Claude·GPT), 배포용 설치(install.bat)

## 구조

```
run.py                     진입점 (Qt 플러그인 경로 보정, 오류 창)
install.bat                처음 설치 (패키지 + 바탕화면 아이콘)
PyQt 학습 도우미 실행.bat                  더블클릭 실행
tools/make_shortcut.py     바탕화면 아이콘 만들기
studyhelper/
  mainwindow.py            화면 조립, 파일 감시, 실행
  preview.py               미리보기 + 빨간 강조 오버레이
  editor.py                Main.py 편집기 (줄 번호, 하이라이트, hover)
  props.py                 속성 패널
  ui_model.py              .ui XML → 위젯 트리
  locate.py                .py ↔ .ui 찾기
  codeview.py              pyuic 생성 코드 + 줄 해설
  checker.py               이름 검사기
  errors.py                traceback → 쉬운 해설
  explain.py               줄 해설 규칙 (무엇/왜/주의)
  ai.py                    AI 호출 (Claude·GPT·Gemini·Ollama), 키 저장
  explainpanel.py          줄 해설·AI 해설 패널, 설정 대화상자
  codegen.py, signaldialog.py  시그널 연결 코드 만들기
  notes.py                 Obsidian 강의노트 검색·열기
  renamedialog.py          objectName 바꾸기
  challenge.py             도전 모드
```
