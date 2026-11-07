"""Tạo file ví dụ examples/mau_joint_reactions.xlsx.

4 joint tại (0,0), (6,0), (0,6), (6,6), Z=0; 3 case Nonlinear Static
(SW, SDL, WX1+), mỗi case 1 step (Final State Only). Đơn vị kN, m.
Dùng để thử chế độ Excel offline mà không cần SAP2000.

Chạy:  python examples/make_example.py
"""

import os

from openpyxl import Workbook

HERE = os.path.dirname(os.path.abspath(__file__))

SW_F3 = {"J1": 100.0, "J2": 120.0, "J3": 110.0, "J4": 90.0}
SDL_F3 = {"J1": 50.0, "J2": 60.0, "J3": 55.0, "J4": 45.0}
COORDS = {"J1": (0, 0, 0), "J2": (6, 0, 0), "J3": (0, 6, 0), "J4": (6, 6, 0)}


def main() -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Joint Reactions"
    ws.append(["TABLE:  Joint Reactions"])
    ws.append(["Joint", "OutputCase", "CaseType", "StepType", "StepNum",
               "F1", "F2", "F3", "M1", "M2", "M3"])
    ws.append(["", "", "", "", "", "kN", "kN", "kN", "kN-m", "kN-m", "kN-m"])
    for j in ("J1", "J2", "J3", "J4"):
        ws.append([j, "SW", "Nonlinear Static", "Step", 1, 5, 0, SW_F3[j], 0, 20, 0])
        ws.append([j, "SDL", "Nonlinear Static", "Step", 1, 2, 0, SDL_F3[j], 0, 10, 0])
        ws.append([j, "WX1+", "Nonlinear Static", "Step", 1, 30, 0, 0, 0, 0, 15])
    coords = wb.create_sheet("Joint Coordinates")
    coords.append(["Joint", "X", "Y", "Z"])
    for j in ("J1", "J2", "J3", "J4"):
        coords.append([j, *COORDS[j]])
    path = os.path.join(HERE, "mau_joint_reactions.xlsx")
    wb.save(path)
    print(f"Đã tạo {path}")
    return path


if __name__ == "__main__":
    main()
