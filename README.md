# PyQt 학습 도우미

**Qt Designer로 만든 `.ui`와 직접 짠 `Main.py`를 나란히 놓고, 서로 연결해서 보며 PyQt5를 익히는 학습 도구**입니다.

> `self.btnSave`가 화면의 어느 버튼인지, 이 줄은 왜 이렇게 쓰는지, 에러는 왜 났는지 — PyQt를 처음 배울 때 막히는 곳을 눈으로 보고 바로 고쳐 보면서 풀어 갑니다.

![PyQt 학습 도우미 화면](docs/screenshot.png)

## 이런 걸 해 줍니다

### 코드와 화면을 연결해서 보기
- **실시간 미리보기**: `.ui`를 실제 위젯으로 띄웁니다. Designer에서 저장하면 바로 다시 불러옵니다.
- **마우스를 올리면 연결**: 코드의 파란 `self.위젯이름`에 마우스를 올리면 미리보기의 그 위젯이 빨갛게 표시되고, 클래스·레이아웃 위치·`.ui` 원본 XML이 나옵니다. 미리보기에서 위젯을 클릭하면 그 위젯을 쓰는 코드 줄이 표시됩니다.
- **`.ui` 자동 찾기**: 파이썬 파일을 열면 맞는 `.ui`를 알아서 찾습니다. 한 `Main.py`가 `.ui`를 여러 개 쓰면(`class dlgForm(QDialog, Ui_Dialog)` 등) 커서가 있는 클래스에 맞춰 미리보기가 바뀝니다.

### 설명해 주기
- **줄 해설**: 줄을 클릭하면 **무엇을 하는지 / 왜 이렇게 쓰는지 / 주의할 점**이 나옵니다 (인터넷 없이 동작).
- **에러 해설**: 실행(F5)이 에러로 끝나면 원인을 쉬운 말로 풀고, 에러 난 줄로 이동해 표시합니다.
- **AI 해설·코드 리뷰**: 선택한 줄 설명(Ctrl+E), 파일 전체 리뷰, 이어서 질문하기. [무료로 켜는 방법](#ai-해설-켜기)이 있습니다.

### 실수를 미리 잡아 주기
- **이름 검사기**: `.ui`에 없는 `self.이름`(오타)은 빨간 물결 밑줄과 비슷한 이름 제안, 없는 슬롯 함수는 주황 밑줄. 문법 오류, pyuic 변환 파일과 import 불일치도 알려 줍니다.
- **`on_위젯_시그널` 함정 경고**: `setupUi`가 이 이름을 자동 연결해서, 직접 `connect`까지 하면 함수가 두 번 실행됩니다.

### 대신 해 주기
- **시그널 연결 코드 넣기**: 시그널 탭에서 시그널을 더블클릭하면 `connect` 줄과 인자가 맞는 함수 틀을 Main.py에 넣어 줍니다. (Ctrl+Z로 한 번에 되돌리기)
- **`objectName` 바꾸기** (F2): `.ui`의 이름과 모든 참조, Main.py의 `self.이름`을 한꺼번에 바꿔서 짝이 깨지지 않게 합니다.
- **`.ui` 값 고치기**: `text` 같은 단순 속성은 속성 표에서 고치면 `.ui`에 바로 저장됩니다.
- **자동완성** (Tab): `self.` 뒤에 `.ui`의 위젯 이름, `self.위젯.` 뒤에 그 위젯 클래스의 메서드·시그널(`clicked`, `setText` …)이 나옵니다.

### 연습하고 정리하기
- **도전 모드** (Ctrl+T): 목표 화면 `.ui`를 보고 Designer로 똑같이 만들면, 저장할 때마다 체크리스트로 자동 채점합니다.
- **학습 폴더**: 자주 여는 폴더를 등록하면 파일 열기 창 왼쪽에 바로가기가 생기고, 시작 화면에 그 안의 `Main.py`가 모여 보입니다.
- **내 노트 연결**: 내 Obsidian 볼트(또는 `.md` 노트 폴더)를 연결하면, 선택한 위젯 클래스가 나오는 노트 섹션을 찾아 줍니다.

## 설치 (Windows)

1. [Python 3.10 이상](https://www.python.org/downloads/) 설치 — 설치 화면에서 **Add python.exe to PATH**를 체크하세요.
2. 이 저장소를 내려받아 압축을 풉니다 (**Code → Download ZIP**).
3. 폴더 안의 **`install.bat`** 을 더블클릭하세요. 필요한 패키지 설치와 바탕화면 아이콘 만들기가 한 번에 끝납니다.
4. 바탕화면의 **PyQt 학습 도우미** 아이콘으로 실행합니다. (또는 `PyQt 학습 도우미 실행.bat`)

> `install.bat` 하나만이 아니라 **폴더 전체**가 필요합니다. 명령줄로 실행하려면 `python run.py "경로/Main.py"` (`.ui`나 폴더도 가능). 창에 파일을 끌어다 놓아도 열립니다.

## 사용법

1. **파일 열기** (Ctrl+O): `Main.py`를 엽니다. 맞는 `.ui`가 자동으로 미리보기에 뜹니다.
2. 코드의 **파란 이름**에 마우스를 올려 화면의 위젯을 확인합니다.
3. 궁금한 줄을 클릭하면 오른쪽 아래에 해설이 나옵니다. 더 궁금하면 **Ctrl+E**.
4. **F5**로 실행합니다. 에러가 나면 해설과 함께 그 줄로 이동합니다.
5. Designer가 필요하면 **Ctrl+D**. 저장하면 도우미가 바로 반영합니다.

자세한 단축키와 색 표시의 뜻은 프로그램 안 **F1(사용법)** 과 코드 아래 **색 범례**에 있습니다.

## AI 해설 켜기

처음에는 **웹 AI 방식**으로 바로 쓸 수 있고(키 필요 없음), 아래 방법으로 답이 도우미 안에 바로 나오게 바꿀 수 있습니다.

| 방법 | 비용 | 설정 |
|---|---|---|
| **무료 AI 켜기** (Gemini 무료 티어) ← 추천 | 무료 (사용량 제한) | AI 해설 탭의 파란 **무료 AI 켜기** 버튼 → 구글 AI Studio에서 키를 만들어 **복사 버튼**만 누르면 자동 연결 |
| **웹 AI** (ChatGPT / Gemini / Claude 웹) | 무료 계정 | 기본값. Ctrl+E를 누르면 질문이 복사되고 웹 창이 열립니다. 붙여넣고, 답의 복사 버튼을 누르면 답이 도우미로 들어옵니다 |
| **Ollama** (내 PC) | 완전 무료, 인터넷 불필요 | [Ollama](https://ollama.com/download) 설치 후 모델 받기 (PC 성능 필요) |
| **Claude · GPT · Gemini API** | 유료 | AI 메뉴 → AI 모델·키 설정에서 키 입력 |

- API 키는 각자의 **Windows 자격 증명 관리자**에만 저장되고, 파일이나 저장소에는 남지 않습니다. 환경변수(`GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`)가 있으면 그것을 우선 씁니다.
- Gemini 무료 티어는 분당·하루 사용량 제한이 있고, 무료 티어에서는 입력한 내용이 Google 제품 개선에 쓰일 수 있습니다.
- 웹 AI 방식은 내 코드가 해당 사이트로 보내진다는 점을 알아 두세요. 웹사이트를 자동으로 조작하지 않고, 사용자가 붙여넣고 복사합니다.
- 목록에 없는 새 모델은 모델 칸에 이름을 직접 입력하면 됩니다.

## 요구 사항

- Windows, Python 3.10+
- `PyQt5`, `keyring`, `google-genai`, `openai`, `anthropic`, (선택) `jedi` — `install.bat`이 설치합니다.
- Designer 연동(Ctrl+D)은 `PyQt5Designer` 패키지의 `designer.exe`를 씁니다 (설치 스크립트가 시도).

## 개발

```
run.py                  진입점 (Qt 플러그인 경로 보정, 오류 창)
install.bat             처음 설치 (패키지 + 바탕화면 아이콘)
tools/make_shortcut.py  바탕화면 아이콘 만들기
studyhelper/
  mainwindow.py         화면 조립, 파일 감시, 실행
  preview.py            미리보기 + 위젯 강조
  editor.py             Main.py 편집기 (줄 번호, 하이라이트, hover, 자동완성 팝업)
  completer.py          자동완성 후보 (.ui 위젯, Qt 메서드·시그널, jedi)
  props.py              선택한 위젯 패널
  ui_model.py           .ui XML → 위젯 트리, 값 수정·이름 바꾸기
  locate.py             .py ↔ .ui 찾기, 클래스별 .ui 매핑
  checker.py            이름 검사기
  errors.py             traceback → 쉬운 해설
  explain.py            줄 해설 규칙
  codeview.py           pyuic 생성 코드 해설
  codegen.py, signaldialog.py  시그널 연결 코드 만들기
  renamedialog.py       objectName 바꾸기
  challenge.py          도전 모드
  studyfolders.py       학습 폴더
  notes.py              내 노트 검색·열기
  ai.py, explainpanel.py, freeai.py   AI 호출, AI 패널, 무료 AI 켜기
tests/                  자동 테스트
docs/                   개발 기록, 스크린샷
```

자동 테스트 실행:

```bash
python -m unittest discover -s tests -t .
```

화면 없이 돌리려면 환경변수 `QT_QPA_PLATFORM=offscreen`을 지정하세요.

## 기여

- 자동완성, 학습 폴더 등록과 Main 파일 모아 보기, 자동 테스트는 **[BlackBuddle](https://github.com/BlackBuddle)** 님이 Pull Request로 추가했습니다.
- 버그 제보와 개선 제안은 Issues / Pull Request로 환영합니다.
