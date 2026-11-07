"""Xuất thêm file Excel SAFE-tables (.xlsx) — đường import dự phòng.

Nếu .F2K cần chỉnh, user có thể dùng file này qua Interactive Database
Editing trong SAFE. Tên sheet theo tên bảng trong SAFE Database
Documentation.
"""

from __future__ import annotations

from .model import F2kModel

SHEETS = [
    "Load Pattern Definitions",
    "Load Case Definitions",
    "Load Combination Definitions",
    "Joint Coordinates",
    "Joint Loads - Point",
]


def write_safe_tables_xlsx(path: str, model: F2kModel) -> dict:
    try:
        from openpyxl import Workbook
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("Chưa cài openpyxl: pip install -r requirements.txt") from e

    wb = Workbook()
    wb.remove(wb.active)

    ws = wb.create_sheet("Load Pattern Definitions")
    ws.append(["LoadPat", "Type", "SelfWtMult"])
    for p in model.patterns:
        ws.append([p["name"], p.get("type", "Other"), p.get("self_wt_mult", 0)])

    ws = wb.create_sheet("Load Case Definitions")
    ws.append(["LoadCase", "Type"])
    for c in model.cases:
        ws.append([c["name"], c.get("type", "Linear Static")])

    ws = wb.create_sheet("Load Combination Definitions")
    ws.append(["Combo", "Type", "Case", "ScaleFactor"])
    for combo in model.combos:
        for case, sf in combo["items"]:
            ws.append([combo["name"], combo.get("type", "Linear Add"), case, sf])

    ws = wb.create_sheet("Joint Coordinates")
    ws.append(["Joint", "X", "Y"])
    for p in model.points:
        ws.append([p["name"], p["x"], p["y"]])

    ws = wb.create_sheet("Joint Loads - Point")
    ws.append(["Joint", "LoadPat", "FX", "FY", "FZ", "MX", "MY", "MZ"])
    for ld in model.point_loads:
        ws.append([ld["point"], ld["pattern"], ld["fx"], ld["fy"], ld["fz"],
                   ld["mx"], ld["my"], ld["mz"]])

    wb.save(path)
    return {"path": path, "sheets": SHEETS}
