"""Build file .exe bằng PyInstaller (chạy trên Windows).

Cách dùng:
    pip install -r requirements.txt
    python build_exe.py

Kết quả: dist/SAP2SAFE.exe (file chạy độc lập, one-file, windowed).
"""

import os
import subprocess
import sys

APP_NAME = "SAP2SAFE"
ENTRY = "main.py"


def main() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",          # 1 file exe duy nhất
        "--windowed",         # không hiện console
        "--name", APP_NAME,
        "--hidden-import", "openpyxl",
        "--hidden-import", "openpyxl.cell",
        ENTRY,
    ]
    print("Chạy:", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode == 0:
        exe = os.path.join("dist", APP_NAME + ".exe")
        print(f"\nXong! File exe tại: {os.path.abspath(exe)}")
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
