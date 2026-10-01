"""Create the desktop shortcut 'PyQt 학습 도우미' (pythonw -> run.py, no console window)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "PyQt 학습 도우미"


def main():
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    target = pyw if pyw.exists() else exe
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        "$d = [Environment]::GetFolderPath('Desktop'); "
        f"$l = $ws.CreateShortcut((Join-Path $d '{NAME}.lnk')); "
        f"$l.TargetPath = '{target}'; "
        f"$l.Arguments = '\"{ROOT / 'run.py'}\"'; "
        f"$l.WorkingDirectory = '{ROOT}'; "
        f"$l.IconLocation = '{target},0'; "
        "$l.Description = 'PyQt 학습 도우미 (.ui 미리보기 + Main.py 연동)'; "
        "$l.Save(); Write-Output (Join-Path $d '" + NAME + ".lnk')"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode == 0:
        print(f"    Shortcut created: {r.stdout.strip()}")
    else:
        print("    Could not create the shortcut. You can start the app with start.bat instead.")
        print(r.stderr.strip()[:500])


if __name__ == "__main__":
    main()
