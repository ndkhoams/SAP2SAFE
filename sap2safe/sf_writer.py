"""Sinh file .sf / .F2K (SAFE text) theo ĐÚNG cú pháp file MONG.sf thật.

Nguồn mẫu: MONG.sf (SAFE 22.5.1) + file .$2k SAP2000 26.3.0
(model "NHA CAT KHO NPL TCVN"). Quy ước đã kiểm chứng từ file thật:
- Dòng đầu `File <tên file> was saved on YYYY/MM/DD at h:mm:ss am/pm`.
- Mỗi block: dòng trắng, `TABLE:  "TÊN BẢNG"`, dòng dữ liệu bắt đầu
  3 khoảng trắng, trường `Key=Value` cách nhau 3 khoảng trắng.
- Các bảng xuất (theo thứ tự alphabet như file CSI):
  PROGRAM CONTROL, LOAD PATTERN DEFINITIONS,
  LOAD CASE DEFINITIONS - LINEAR STATIC, LOAD COMBINATION DEFINITIONS,
  POINT OBJECT CONNECTIVITY, JOINT ASSIGNMENTS - RESTRAINTS,
  JOINT LOADS ASSIGNMENTS - FORCE.
- Mỗi case SAFE gồm pattern gốc + pattern `<tên>_ABOVE` (SF=1); chỉ
  pattern gốc có joint load, _ABOVE có 0 dòng load (đúng như MONG.sf:
  1380 dòng = 15 pattern x 92 point).
- Self Weight Multiplier lấy từ SAP (SW=1, còn lại 0) — KHÔNG ép về 0:
  tải SW trong SAFE là tải điểm đã đóng băng; tự trọng sàn SAFE (nếu có)
  tính riêng. Ghi chú này trong file .LOG.
- Combo được COPY Y HỆT định nghĩa từ SAP (kể cả combo chứa case
  nonlinear và combo Envelope); SAFE tự tính combo từ các case đã đóng
  băng (cộng tuyến tính) — ghi cảnh báo trong .LOG.
- KHÔNG tự sinh slab/bbox/area/spring: MONG.sf không có các bảng đó;
  file xuất ra chỉ gồm points + restraints + loads, import vào model
  SAFE đã có sẵn (hoặc mở như model mới chỉ gồm points+loads).
- GUID mới (uuid4) cho mỗi dòng cần GUID. Z của point trong SAFE = 0
  (đổi gốc cao độ; Z SAP chỉ dùng để lọc level).
"""

from __future__ import annotations

import datetime
import uuid

from .csi_text import format_kv_line, write_csi_tables
from .model import F2kModel

EXPECTED_TABLES = [
    "JOINT ASSIGNMENTS - RESTRAINTS",
    "JOINT LOADS ASSIGNMENTS - FORCE",
    "LOAD CASE DEFINITIONS - LINEAR STATIC",
    "LOAD COMBINATION DEFINITIONS",
    "LOAD PATTERN DEFINITIONS",
    "POINT OBJECT CONNECTIVITY",
    "PROGRAM CONTROL",
]

# Map DesignType của SAP -> Type pattern của SAFE (đọc từ MONG.sf + .$2k).
SAP_DESIGN_TYPE_TO_SAFE = {
    "Dead": "Dead",
    "Super Dead": "Super Dead",
    "Live": "Live",
    "Wind": "Wind",
    "Quake": "Seismic",
    "Seismic": "Seismic",
    "Other": "Other",
}


def safe_pattern_type(sap_design_type: str) -> str:
    return SAP_DESIGN_TYPE_TO_SAFE.get((sap_design_type or "").strip(), "Other")


def _guid() -> str:
    return str(uuid.uuid4())


def _joint_sort_key(name: str):
    return (0, int(name)) if str(name).lstrip("-").isdigit() else (1, str(name))


def _case_sort_key(name: str) -> str:
    # Khớp thứ tự trong MONG.sf: "WX1-" đứng trước "WX1+".
    return name.replace("+", "\uffff")


def _header_line(path: str) -> str:
    now = datetime.datetime.now()
    hour = now.hour % 12 or 12
    ampm = "am" if now.hour < 12 else "pm"
    import os
    base = os.path.basename(path)
    return (f"File {base} was saved on {now.year}/{now.month:02d}/{now.day:02d} "
            f"at {hour}:{now.minute:02d}:{now.second:02d} {ampm}")


def build_tables(model: F2kModel) -> list[tuple[str, list[str]]]:
    tables: list[tuple[str, list[str]]] = []

    # JOINT ASSIGNMENTS - RESTRAINTS (lấy đúng U/R từng joint).
    rows = []
    for p in sorted(model.points, key=lambda d: _joint_sort_key(d["name"])):
        r = p.get("restraint") or (True, True, True, True, True, True)
        rows.append(format_kv_line([
            ("UniqueName", p["name"]),
            ("UX", bool(r[0])), ("UY", bool(r[1])), ("UZ", bool(r[2])),
            ("RX", bool(r[3])), ("RY", bool(r[4])), ("RZ", bool(r[5])),
        ]))
    tables.append(("JOINT ASSIGNMENTS - RESTRAINTS", rows))

    # JOINT LOADS ASSIGNMENTS - FORCE (gom theo pattern, rồi theo joint).
    pattern_order = [p["name"] for p in model.patterns]
    order_index = {name: i for i, name in enumerate(pattern_order)}
    loads = sorted(
        model.point_loads,
        key=lambda ld: (order_index.get(ld["pattern"], 999),
                        _joint_sort_key(ld["point"])),
    )
    rows = []
    for ld in loads:
        rows.append(format_kv_line([
            ("UniqueName", ld["point"]),
            ("Load Pattern", ld["pattern"]),
            ("FX", ld["fx"]), ("FY", ld["fy"]), ("FZ", ld["fz"]),
            ("MX", ld["mx"]), ("MY", ld["my"]), ("MZ", ld["mz"]),
            ("X Dimension", 0), ("Y Dimension", 0), ("GUID", _guid()),
        ]))
    tables.append(("JOINT LOADS ASSIGNMENTS - FORCE", rows))

    # LOAD CASE DEFINITIONS - LINEAR STATIC (mỗi case = pattern + _ABOVE).
    rows = []
    for case in sorted(model.cases, key=lambda c: _case_sort_key(c["name"])):
        name = case["name"]
        rows.append(format_kv_line([
            ("Name", name),
            ("Exclude Group", "None"),
            ("Initial Condition", "Nonlinear Case"),
            ("Nonlinear Case", "None"),
            ("Load Type", "Load"),
            ("Load Name", name),
            ("Load SF", 1),
            ("Design Type", "Program Determined"),
            ("GUID", _guid()),
        ]))
        rows.append(format_kv_line([
            ("Name", name),
            ("Load Type", "Load"),
            ("Load Name", f"{name}_ABOVE"),
            ("Load SF", 1),
        ]))
    tables.append(("LOAD CASE DEFINITIONS - LINEAR STATIC", rows))

    # LOAD COMBINATION DEFINITIONS (copy y hệt định nghĩa SAP).
    rows = []
    for combo in model.combos:
        items = combo["items"]
        if not items:
            continue
        first_case, first_sf = items[0]
        rows.append(format_kv_line([
            ("Name", combo["name"]),
            ("Type", combo.get("type", "Linear Add")),
            ("Is Auto", "No"),
            ("Load Name", first_case),
            ("SF", first_sf),
            ("GUID", _guid()),
        ]))
        for case, sf in items[1:]:
            rows.append(format_kv_line([
                ("Name", combo["name"]),
                ("Load Name", case),
                ("SF", sf),
            ]))
    tables.append(("LOAD COMBINATION DEFINITIONS", rows))

    # LOAD PATTERN DEFINITIONS (pattern + _ABOVE ngay sau mỗi pattern).
    rows = []
    for p in model.patterns:
        rows.append(format_kv_line([
            ("Name", p["name"]),
            ("Is Auto Load", "No"),
            ("Type", p.get("type", "Other")),
            ("Self Weight Multiplier", p.get("self_wt_mult", 0)),
            ("GUID", _guid()),
        ]))
        rows.append(format_kv_line([
            ("Name", f"{p['name']}_ABOVE"),
            ("Is Auto Load", "No"),
            ("Type", p.get("type", "Other")),
            ("Self Weight Multiplier", 0),
            ("GUID", _guid()),
        ]))
    tables.append(("LOAD PATTERN DEFINITIONS", rows))

    # POINT OBJECT CONNECTIVITY (Z=0 trong SAFE — đổi gốc cao độ).
    rows = []
    for p in sorted(model.points, key=lambda d: _joint_sort_key(d["name"])):
        rows.append(format_kv_line([
            ("UniqueName", p["name"]),
            ("Is Auto Point", "No"),
            ("IsSpecial", "Yes"),
            ("X", p["x"]), ("Y", p["y"]), ("Z", 0),
            ("GUID", _guid()),
        ]))
    tables.append(("POINT OBJECT CONNECTIVITY", rows))

    # PROGRAM CONTROL.
    rows = [format_kv_line([
        ("ProgramName", "SAFE"),
        ("Version", model.safe_version),
        ("CurrUnits", "kN, m, C"),
        ("CompBmCode", "AISC 360-16"),
        ("ConcFrmCode", "ACI 318-14"),
        ("ConcSlbCode", "ACI 318-14"),
    ])]
    tables.append(("PROGRAM CONTROL", rows))
    return tables


def write_sf(path: str, model: F2kModel) -> dict:
    """Ghi file .sf (hoặc .F2K — cùng nội dung). Trả về số lượng đã ghi."""
    write_csi_tables(path, _header_line(path), build_tables(model))
    return {
        "points": len(model.points),
        "patterns": len(model.patterns),
        "cases": len(model.cases),
        "combos": len(model.combos),
        "point_loads": len(model.point_loads),
        "path": path,
    }


# Alias: .F2K và .sf dùng chung cú pháp TABLE của CSI.
def write_f2k(path: str, model: F2kModel) -> dict:
    return write_sf(path, model)


def build_lines(model: F2kModel) -> list[str]:
    """Các dòng text sẽ ghi (để test kiểm tra nội dung mà không cần ghi file)."""
    lines = [_header_line("SAP2SAFE.f2k"), " "]
    for name, rows in build_tables(model):
        lines.append(f'TABLE:  "{name}"')
        lines.extend(rows)
        lines.append(" ")
    return lines
