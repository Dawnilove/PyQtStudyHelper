"""코드 아래 색 범례 (짧은 줄 + 툴팁용 전체 설명)."""


def _chip(bg, fg, text, border=None):
    b = f"border:1px solid {border};" if border else ""
    return (f"<span style='background:{bg};color:{fg};{b}'>&nbsp;{text}&nbsp;</span>")


LEGEND_FULL = " &nbsp; ".join(f"<span style='white-space:nowrap'>{x}</span>" for x in [
    "<b>색 표시</b>",
    "<span style='color:#0b6bcb'><b><u>파란 밑줄</u></b></span> .ui 위젯 (마우스 올리기)",
    "<span style='color:#e03131'>〰 빨간 물결</span> .ui에 없는 이름",
    "<span style='color:#e8890c'>〰 주황 물결</span> 함수 없음·주의",
    _chip("#ffd666", "#5c3c00", "노랑") + " 선택한 위젯을 쓰는 곳",
    _chip("#ffd9d9", "#8a1f1f", "빨강 줄") + " 실행 에러 난 줄",
    _chip("#d3f9d8", "#1e6b2e", "초록 줄") + " 방금 넣은 코드",
    _chip("#eaf2ff", "#1f3a5f", "파랑 줄") + " 지금 줄 (해설 대상)",
    "<span style='color:#e03131'>●</span> 문제 있는 줄 번호",
])


LEGEND = " &nbsp; ".join(f"<span style='white-space:nowrap'>{x}</span>" for x in [
    "<span style='color:#0b6bcb'><u>파랑 밑줄</u></span> 위젯",
    "<span style='color:#e03131'>〰 빨강</span> 없는 이름",
    "<span style='color:#e8890c'>〰 주황</span> 주의",
    _chip("#ffd666", "#5c3c00", "노랑") + " 선택",
    _chip("#ffd9d9", "#8a1f1f", "빨강") + " 에러 줄",
    _chip("#d3f9d8", "#1e6b2e", "초록") + " 방금 넣음",
    _chip("#eaf2ff", "#1f3a5f", "파랑") + " 현재 줄",
])
