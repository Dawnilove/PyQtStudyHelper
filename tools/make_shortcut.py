"""Create the desktop shortcut 'PyQt 학습 도우미' (pythonw -> run.py, no console window)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "PyQt 학습 도우미"


def q(p) -> str:
    """PowerShell single-quoted string literal."""
    return "'" + str(p).replace("'", "''") + "'"


def main():
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    target = pyw if pyw.exists() else exe
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        "$d = [Environment]::GetFolderPath('Desktop'); "
        f"$l = $ws.CreateShortcut((Join-Path $d {q(NAME + '.lnk')})); "
        f"$l.TargetPath = {q(target)}; "
        f"$l.Arguments = {q(chr(34) + str(ROOT / 'run.py') + chr(34))}; "
        f"$l.WorkingDirectory = {q(ROOT)}; "
        f"$l.IconLocation = {q(str(target) + ',0')}; "
        "$l.Description = 'PyQt 학습 도우미 (.ui 미리보기 + Main.py 연동)'; "
        "$l.Save()"
    )
    # PowerShell answers in the console code page, not UTF-8: don't echo its output back
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       capture_output=True)
    if r.returncode == 0:
        print(f"    Shortcut created on the desktop: {NAME}")
    else:
        print(f"    Could not create the shortcut. Start the app with '{NAME} 실행.bat' instead.")


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")      # never crash on a console that can't show a character
    main()

