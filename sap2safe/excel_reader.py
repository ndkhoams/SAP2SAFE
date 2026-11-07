"""Đọc file Excel Joint Reactions export từ SAP (chế độ offline, không cần SAP).

Tolerant với file export thật của SAP (Display > Show Tables):
- Phía trên bảng có thể có dòng tiêu đề TABLE / dòng đơn vị — hàm scan tìm
  dòng header thật bằng cách tìm ô chứa "Joint".
- Sheet Joint Reactions có thể tên bất kỳ chứa "Joint Reactions", nếu không
  thì lấy sheet đầu tiên có cột Joint + OutputCase.
- Tọa độ lấy từ sheet "Joint Coordinates" nếu có, nếu không thì tìm sheet
  có đủ cột Joint + X + Y + Z.
- Bỏ dòng tổng (Joint rỗng) và joint mesh nội bộ (tên bắt đầu bằng "~").
"""

from __future__ import annotations

from .model import Reaction

REQUIRED_COLS = ["Joint", "OutputCase", "F1", "F2", "F3", "M1", "M2", "M3"]
OPTIONAL_COLS = ["CaseType", "StepType", "StepNum"]


class ExcelReadError(ValueError):
    pass


def _norm(text) -> str:
    return str(text).strip() if text is not None else ""


def _find_header(ws, max_scan: int = 15):
    """Tìm dòng header thật: dòng đầu tiên (trong 15 dòng đầu) có ô 'Joint'."""
    for row in ws.iter_rows(min_row=1, max_row=max_scan, values_only=True):
        cells = [_norm(c) for c in row]
        if "Joint" in cells:
            colmap = {name: i for i, name in enumerate(cells) if name}
            return list(row), colmap
    return None, {}


def _col(colmap: dict, *names: str) -> int | None:
    for n in names:
        if n in colmap:
            return colmap[n]
    lowered = {k.lower(): v for k, v in colmap.items()}
    for n in names:
        if n.lower() in lowered:
            return lowered[n.lower()]
    return None


def _read_table_sheet(ws) -> list[dict]:
    _header, colmap = _find_header(ws)
    if not colmap:
        return []
    idx = {}
    for col in REQUIRED_COLS + OPTIONAL_COLS:
        idx[col] = _col(colmap, col)
    if idx["Joint"] is None or idx["OutputCase"] is None or idx["F1"] is None:
        return []
    rows: list[dict] = []
    header_row = None
    for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if header_row is None:
            if _norm(row[colmap.get("Joint", 0)] if colmap else "") == "Joint" or (
                colmap and _norm(next(iter([row[i] for i in colmap.values() if i < len(row)]), "")) == "Joint"
            ):
                header_row = r
            continue
        if header_row is not None and r <= header_row:
            continue
        if header_row is None:
            continue
        joint = _norm(row[idx["Joint"]]) if idx["Joint"] < len(row) else ""
        if not joint or joint.startswith("~"):
            continue
        def num(col: str) -> float:
            i = idx[col]
            if i is None or i >= len(row) or row[i] is None:
                return 0.0
            try:
                return float(row[i])
            except (TypeError, ValueError):
                return 0.0
        output = _norm(row[idx["OutputCase"]]) if idx["OutputCase"] < len(row) else ""
        if not output:
            continue
        step_num = num("StepNum")
        rows.append(
            {
                "joint": joint,
                "output": output,
                "case_type": _norm(row[idx["CaseType"]]) if idx["CaseType"] is not None and idx["CaseType"] < len(row) else "",
                "step_type": _norm(row[idx["StepType"]]) if idx["StepType"] is not None and idx["StepType"] < len(row) else "",
                "step_num": step_num,
                "f1": num("F1"),
                "f2": num("F2"),
                "f3": num("F3"),
                "m1": num("M1"),
                "m2": num("M2"),
                "m3": num("M3"),
            }
        )
    return rows


def read_joint_reactions(path: str):
    """Trả về (reactions, joints) với joints: dict tên -> (x, y, z).

    reactions: list[Reaction] (output_kind="case" mặc định; GUI/combo sẽ
    phân loại lại nếu tên output trùng combo — ở chế độ Excel, user chọn
    case/combo trong danh sách output đọc được).
    """
    try:
        from openpyxl import load_workbook
    except ImportError as e:  # pragma: no cover
        raise ExcelReadError("Chưa cài openpyxl: pip install -r requirements.txt") from e
    try:
        wb = load_workbook(path, data_only=True, read_only=True)
    except Exception as e:
        raise ExcelReadError(f"Không mở được file Excel: {path}\n{e}") from e

    reactions: list[Reaction] = []
    for ws in wb.worksheets:
        title = (ws.title or "").lower()
        if "joint reactions" in title or "reactions" in title:
            table = _read_table_sheet(ws)
            if table:
                reactions.extend(
                    Reaction(
                        joint=t["joint"],
                        output_name=t["output"],
                        output_kind="case",
                        step_type=t["step_type"],
                        step_num=t["step_num"],
                        f1=t["f1"],
                        f2=t["f2"],
                        f3=t["f3"],
                        m1=t["m1"],
                        m2=t["m2"],
                        m3=t["m3"],
                    )
                    for t in table
                )
                break
    if not reactions:
        # Fallback: sheet đầu tiên có bảng hợp lệ.
        for ws in wb.worksheets:
            table = _read_table_sheet(ws)
            if table:
                reactions.extend(
                    Reaction(
                        joint=t["joint"],
                        output_name=t["output"],
                        output_kind="case",
                        step_type=t["step_type"],
                        step_num=t["step_num"],
                        f1=t["f1"],
                        f2=t["f2"],
                        f3=t["f3"],
                        m1=t["m1"],
                        m2=t["m2"],
                        m3=t["m3"],
                    )
                    for t in table
                )
                break
    if not reactions:
        raise ExcelReadError(
            "Không tìm thấy bảng Joint Reactions trong file Excel "
            "(cần các cột Joint, OutputCase, F1, F2, F3, M1, M2, M3)."
        )

    joints: dict[str, tuple[float, float, float]] = {}
    for ws in wb.worksheets:
        title = (ws.title or "").lower()
        _header, colmap = _find_header(ws)
        if not colmap:
            continue
        j = _col(colmap, "Joint")
        ix = _col(colmap, "X")
        iy = _col(colmap, "Y")
        iz = _col(colmap, "Z")
        if j is None or ix is None or iy is None:
            continue
        if "joint coordinates" not in title and "coordinates" not in title:
            # Chỉ nhận sheet tọa độ khi tên gợi ý, hoặc sheet thứ 2 trở đi
            # có đủ cột — tránh nhầm bảng reactions (cũng có Joint nhưng
            # không có cột X/Y).
            if iz is None:
                continue
        for row in ws.iter_rows(values_only=True):
            if row is None or j >= len(row):
                continue
            name = _norm(row[j])
            if not name or name.startswith("~") or name == "Joint":
                continue
            try:
                x = float(row[ix]) if row[ix] is not None else 0.0
                y = float(row[iy]) if row[iy] is not None else 0.0
                z = float(row[iz]) if iz is not None and row[iz] is not None else 0.0
            except (TypeError, ValueError):
                continue
            joints[name] = (x, y, z)
        if joints:
            break
    wb.close()
    return reactions, joints


def list_outputs(reactions: list[Reaction]) -> list[str]:
    """Danh sách output (case/combo) theo thứ tự xuất hiện."""
    seen: list[str] = []
    for r in reactions:
        if r.output_name not in seen:
            seen.append(r.output_name)
    return seen
