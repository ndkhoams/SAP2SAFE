"""Parse file .sf / .F2K (SAFE text) theo đúng cú pháp CSI.

Dùng cho: nút "Kiểm mẫu" trong GUI, validator so sánh với MONG.sf,
và test round-trip writer -> reader.

SỐ THAM CHIẾU từ MONG.sf thật (SAFE 22.5.1, 92 point x 15 pattern):
xem REFERENCE_SUM_FZ dưới đây — đã tính trực tiếp từ file, dung sai 0.01 kN.
"""

from __future__ import annotations

from collections import defaultdict

from .csi_text import parse_csi_tables

# ΣFZ (kN) theo từng pattern trong MONG.sf — tính trực tiếp từ file thật.
REFERENCE_SUM_FZ = {
    "SW": -3963.847, "SDL": -865.919, "COL": -1803.994, "SOL": -1803.994,
    "Lr": -2164.796, "EX": 0.002, "EY": 0.000,
    "WX1+": 4283.841, "WX1-": 4283.839, "WX2+": 2254.952, "WX2-": 2254.949,
    "WY1+": 4022.640, "WY1-": 4022.643, "WY2+": -1504.172, "WY2-": -1504.173,
}

LOAD_COLUMNS = ("FX", "FY", "FZ", "MX", "MY", "MZ")


def parse_sf(path: str) -> dict[str, list[dict[str, str]]]:
    """Parse file .sf/.F2K -> {tên_bảng: [dict dòng, ...]}."""
    return parse_csi_tables(path)


def sum_fz_by_pattern(tables: dict[str, list[dict]]) -> dict[str, float]:
    """ΣFZ theo từng Load Pattern từ bảng JOINT LOADS ASSIGNMENTS - FORCE."""
    sums: dict[str, float] = defaultdict(float)
    for row in tables.get("JOINT LOADS ASSIGNMENTS - FORCE", []):
        try:
            sums[row.get("Load Pattern", "")] += float(row.get("FZ", 0))
        except ValueError:
            continue
    return dict(sums)


def load_values(tables: dict[str, list[dict]]) -> dict[tuple[str, str], dict[str, float]]:
    """{(UniqueName, LoadPattern): {FX..MZ}} từ bảng joint loads."""
    out: dict[tuple[str, str], dict[str, float]] = {}
    for row in tables.get("JOINT LOADS ASSIGNMENTS - FORCE", []):
        key = (row.get("UniqueName", ""), row.get("Load Pattern", ""))
        try:
            out[key] = {c: float(row.get(c, 0)) for c in LOAD_COLUMNS}
        except ValueError:
            continue
    return out


def so_sanh_voi_mong_sf(output_path: str, mong_path: str, tol: float = 0.01) -> str:
    """Validator: so file app xuất ra với file SAFE mẫu (MONG.sf).

    So khớp theo khóa (UniqueName, LoadPattern): đếm joint load, đối chiếu
    từng FX..MZ, báo max/mean lệch tuyệt đối + tương đối, và ΣFZ từng
    pattern. Chỉ BÁO CÁO số lệch — KHÔNG tự sửa số.
    """
    out_tables = parse_sf(output_path)
    ref_tables = parse_sf(mong_path)
    out_loads = load_values(out_tables)
    ref_loads = load_values(ref_tables)
    lines = [f"So sánh file xuất: {output_path}", f"với file mẫu: {mong_path}", ""]
    out_points = out_tables.get("POINT OBJECT CONNECTIVITY", [])
    ref_points = ref_tables.get("POINT OBJECT CONNECTIVITY", [])
    lines.append(f"Point: xuất {len(out_points)}, mẫu {len(ref_points)}")
    out_pats = {r.get("Name", "") for r in out_tables.get("LOAD PATTERN DEFINITIONS", [])}
    ref_pats = {r.get("Name", "") for r in ref_tables.get("LOAD PATTERN DEFINITIONS", [])}
    lines.append(f"Pattern: xuất {len(out_pats)}, mẫu {len(ref_pats)}")
    lines.append(f"Joint load: xuất {len(out_loads)}, mẫu {len(ref_loads)}")
    lines.append("")
    common = set(out_loads) & set(ref_loads)
    only_out = set(out_loads) - set(ref_loads)
    only_ref = set(ref_loads) - set(out_loads)
    lines.append(f"Khóa (point, pattern) chung: {len(common)}")
    if only_out:
        lines.append(f"  Chỉ có trong file xuất: {len(only_out)} (vd {sorted(only_out)[:3]})")
    if only_ref:
        lines.append(f"  Chỉ có trong file mẫu: {len(only_ref)} (vd {sorted(only_ref)[:3]})")
    max_abs = 0.0
    sum_abs = 0.0
    n_val = 0
    worst: tuple | None = None
    for key in sorted(common):
        for col in LOAD_COLUMNS:
            d = abs(out_loads[key][col] - ref_loads[key][col])
            sum_abs += d
            n_val += 1
            if d > max_abs:
                max_abs = d
                worst = (key, col, out_loads[key][col], ref_loads[key][col])
    mean_abs = sum_abs / n_val if n_val else 0.0
    lines.append(f"Lệch tuyệt đối FX..MZ: max = {max_abs:.6f}, mean = {mean_abs:.6f} "
                 f"(dung sai {tol})")
    if worst:
        lines.append(f"  Lệch lớn nhất tại {worst[0]} {worst[1]}: "
                     f"xuất {worst[2]}, mẫu {worst[3]}")
    if not common:
        verdict = "KHÔNG SO ĐƯỢC — không có khóa (point, pattern) chung"
    elif max_abs <= tol:
        verdict = "KHỚP (trong dung sai)"
    else:
        verdict = "CÓ LỆCH — xem chi tiết trên"
    lines.append(f"Kết luận lệch: {verdict}")
    lines.append("")
    lines.append("ΣFZ theo từng pattern (xuất vs mẫu):")
    out_sums = sum_fz_by_pattern(out_tables)
    ref_sums = sum_fz_by_pattern(ref_tables)
    for pattern in sorted(set(out_sums) | set(ref_sums)):
        o = out_sums.get(pattern, 0.0)
        r = ref_sums.get(pattern, 0.0)
        flag = "KHỚP" if abs(o - r) <= tol else "LỆCH"
        lines.append(f"  {pattern}: xuất {o:.3f} | mẫu {r:.3f} | {flag}")
    return "\n".join(lines)
