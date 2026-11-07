"""Sinh file .LOG kèm theo .F2K/.sf: nguồn từng pattern + tổng kiểm tra.

Tổng kiểm tra bắt buộc: ΣFZ (SAFE) theo từng pattern phải bằng -ΣF3 (SAP)
sau đổi dấu. Nếu lệch, file LOG ghi rõ để user không import mù.

Ghi chú theo file MONG.sf thật:
- SelfWtMult lấy từ SAP (SW=1, còn lại 0): tải SW trong SAFE là tải điểm
  đã đóng băng; tự trọng sàn SAFE (nếu có) tính riêng.
- Mỗi case gồm pattern gốc + pattern _ABOVE; _ABOVE có 0 dòng joint load.
- Combo copy y hệt SAP; combo chứa case nonlinear thì SAFE cộng tuyến
  tính các vector đã đóng băng, không phải chạy lại phi tuyến.
"""

from __future__ import annotations

from collections import defaultdict

from . import __version__


def write_log(path: str, info: dict) -> str:
    """`info` gồm: z, tol, units, flip_sign, name_map, sources, loads, warnings,
    counts, safe_version, notes, sap_sums (dict pattern -> ΣF3 SAP),
    validation (text validator, tùy chọn)."""
    lines = [
        f"SAP2SAFE v{__version__} — LOG xuat file",
        "=" * 60,
        f"Level Z = {info.get('z')} m (tol {info.get('tol')} m)",
        f"Don vi: {info.get('units', 'kN, m, C')}",
        f"SAFE version (PROGRAM CONTROL): {info.get('safe_version', '22.5.1')}",
        f"Doi dau phan luc -> tai SAFE: {'BAT' if info.get('flip_sign', True) else 'TAT'}",
        f"So joint: {info.get('counts', {}).get('points', 0)} | "
        f"pattern: {info.get('counts', {}).get('patterns', 0)} | "
        f"case: {info.get('counts', {}).get('cases', 0)} | "
        f"combo: {info.get('counts', {}).get('combos', 0)}",
        "",
        "Ghi chu (theo file MONG.sf that):",
        "  - SelfWtMult lay tu SAP (SW=1, con lai 0); tai SW trong SAFE la",
        "    tai diem da dong bang, tu trong san SAFE (neu co) tinh rieng.",
        "  - Moi case gom pattern goc + pattern _ABOVE; _ABOVE co 0 dong",
        "    joint load (chi pattern goc co tai).",
        "  - Combo copy y het dinh nghia SAP; combo chua case nonlinear thi",
        "    SAFE cong tuyen tinh cac vector da dong bang, khong phai chay",
        "    lai phi tuyen.",
        "  - File chi gom points + restraints + loads (khong co slab/area/",
        "    spring) — giong MONG.sf; import vao model SAFE da co san.",
    ]
    for note in info.get("notes") or []:
        lines.append(f"  - {note}")
    lines.append("")
    lines.append("Bang map ten (SAP -> SAFE):")
    for orig, safe in (info.get("name_map") or {}).items():
        lines.append(f"  {orig} -> {safe}")
    lines.append("")
    lines.append("Nguon tung pattern:")
    for src in info.get("sources") or []:
        lines.append(f"  {src}")
    lines.append("")
    lines.append("Tong kiem tra theo tung pattern (FZ SAFE phai = -F3 SAP):")
    sums_safe: dict[str, float] = defaultdict(float)
    for ld in info.get("loads") or []:
        sums_safe[ld["pattern"]] += ld["fz"]
    sap_sums = info.get("sap_sums") or {}
    ok_all = True
    for pattern in sorted(set(list(sums_safe) + list(sap_sums))):
        fz = sums_safe.get(pattern, 0.0)
        f3 = sap_sums.get(pattern, 0.0)
        ok = abs(fz + f3) < 1e-6
        ok_all = ok_all and ok
        lines.append(
            f"  {pattern}: sum FZ SAFE = {fz:.3f} kN | sum F3 SAP = {f3:.3f} kN "
            f"| {'KHOP' if ok else 'LECH!'}"
        )
    lines.append("")
    lines.append(f"Ket luan tong kiem tra: {'KHOP' if ok_all else 'CO LECH — KIEM TRA LAI TRUOC KHI IMPORT'}")
    warnings = info.get("warnings") or []
    if warnings:
        lines.append("")
        lines.append("Canh bao:")
        for w in warnings:
            lines.append(f"  ! {w}")
    if info.get("validation"):
        lines.append("")
        lines.append("Ket qua validator so voi file SAFE mau:")
        lines.append(info["validation"])
    text = "\n".join(lines) + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text
