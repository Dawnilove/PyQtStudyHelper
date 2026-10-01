# PyQt 학습 도우미

Qt Designer로 만든 `.ui`와 직접 짜는 `Main.py`를 **나란히 놓고 연결해서 보는** PyQt5 학습용 도구.

```bash
python run.py "경로/Main.py"     # .ui 파일이나 폴더를 넘겨도 됨
```

## 화면

| 영역 | 하는 일 |
|---|---|
| 실시간 미리보기 | `uic.loadUi()`로 만든 실제 위젯. 클릭하면 그 위젯이 선택됨 (버튼 동작은 막힘) |
| 위젯 트리 | `.ui` 안의 위젯·레이아웃 계층. 레이아웃은 회색 기울임 |
| Main.py | 편집 가능 (Ctrl+S 저장). `.ui`에 있는 `self.이름`은 파랗게 표시, 마우스를 올리면 선택 |
| 속성 | 클래스·위치 / 속성 표 / Main.py에서 쓰는 곳 / 시그널 / 코드로 보기 / `.ui 원본` |
| 실행 결과 | ▶ 실행(F5) 출력과 에러 |

## 동작

- **.ui 자동 찾기**: 파이썬 파일을 열면 ① `from gui import ...`처럼 import한 모듈 → ② 코드 속 `'gui.ui'`, `f'{GUI_FILE_NAME}.ui'` 같은 문자열 → ③ 같은 폴더의 `.ui` 순서로 찾음. 후보가 여럿이면 툴바 드롭다운에서 바꿈. `.ui`를 열면 그걸 쓰는 `.py`(Main.py 우선)를 찾아 엶.
- **자동 갱신**: Designer에서 `.ui`를 저장하면 미리보기·트리·속성이 바로 다시 불러와짐 (선택 유지). Main.py가 밖에서 바뀌어도 다시 불러옴 (저장 안 한 편집이 있으면 건드리지 않음).
- **실행 안전장치**: ▶ 실행 시 Main.py가 `gui`를 import하는데 `gui.py`가 없거나 `gui.ui`보다 오래됐으면 먼저 다시 만들어 줌.
- **Designer에서 열기**: 현재 `.ui`를 Qt Designer로 엶 (`PyQt5Designer` 패키지의 designer.exe).

## 단계 계획

1. ✅ 미리보기, 속성 패널(코드로 보기), Main.py 연동, `.ui` 자동 감지, 실행
2. 이름 검사기(`.ui`에 없는 `self.이름` 밑줄, 없는 슬롯 경고, 안 쓰는 위젯 표시), 에러 번역과 줄 이동
3. 시그널 도우미(connect + 슬롯 틀 삽입), text 편집 → `.ui` 저장, Obsidian 노트 연결
4. 도전 모드, objectName 이름 바꾸기

## 구조

```
run.py                     진입점
studyhelper/
  mainwindow.py            화면 조립, 파일 감시, 실행
  preview.py               미리보기 + 빨간 강조 오버레이
  editor.py                Main.py 편집기 (줄 번호, 하이라이트, hover)
  props.py                 속성 패널
  ui_model.py              .ui XML → 위젯 트리
  locate.py                .py ↔ .ui 찾기
  codeview.py              pyuic 생성 코드 + 줄 해설
```
