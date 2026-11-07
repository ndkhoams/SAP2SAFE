"""Đổi đơn vị về hệ nội bộ kN, m (lực kN, mô men kN-m, chiều dài m).

SAP OAPI GetPresentUnits trả mã enum eForce / eLength. Bảng mã enum dưới đây
theo tài liệu CSI OAPI thường gặp — CHƯA XÁC MINH bằng CHM đúng version SAP
của user; nếu mã trên máy thật khác, hàm vẫn đúng khi gọi bằng tên đơn vị
dạng chuỗi ("kN", "kgf", "N", "Ton", "kip", "lb", "m", "mm", "cm", "ft", "in").
Vì vậy sap_reader luôn log cả mã enum lẫn tên đã dịch, để user đối chiếu.
"""

from __future__ import annotations

FORCE_TO_KN = {
    "N": 0.001,
    "kN": 1.0,
    "kgf": 0.00980665,
    "tonf": 9.80665,
    "Ton": 9.80665,
    "kip": 4.448221615,
    "lb": 0.004448221615,
}

LENGTH_TO_M = {
    "m": 1.0,
    "mm": 0.001,
    "cm": 0.01,
    "ft": 0.3048,
    "in": 0.0254,
}

# Mã enum eForce / eLength theo CSI OAPI (đối chiếu CHM trên máy thật).
FORCE_UNIT_CODES = {1: "lb", 2: "kip", 3: "N", 4: "kN", 5: "kgf", 6: "tonf"}
LENGTH_UNIT_CODES = {1: "in", 2: "ft", 3: "mm", 4: "cm", 5: "m"}

UNIT_FACTORS = {"force": FORCE_TO_KN, "length": LENGTH_TO_M}


def force_factor(unit) -> float:
    """Hệ số nhân để đổi 1 đơn vị lực -> kN. `unit`: tên chuỗi hoặc mã enum int."""
    if isinstance(unit, int):
        unit = FORCE_UNIT_CODES.get(unit)
        if unit is None:
            raise ValueError(f"Mã đơn vị lực không rõ: {unit} (đối chiếu CHM SAP)")
    try:
        return FORCE_TO_KN[unit]
    except KeyError:
        raise ValueError(f"Đơn vị lực không hỗ trợ: {unit!r}") from None


def length_factor(unit) -> float:
    """Hệ số nhân để đổi 1 đơn vị dài -> m. `unit`: tên chuỗi hoặc mã enum int."""
    if isinstance(unit, int):
        unit = LENGTH_UNIT_CODES.get(unit)
        if unit is None:
            raise ValueError(f"Mã đơn vị dài không rõ: {unit} (đối chiếu CHM SAP)")
    try:
        return LENGTH_TO_M[unit]
    except KeyError:
        raise ValueError(f"Đơn vị dài không hỗ trợ: {unit!r}") from None


def to_kn_m(value: float, unit_code) -> float:
    """Đổi một giá trị lực sang kN. `unit_code`: tên đơn vị hoặc mã enum eForce."""
    return value * force_factor(unit_code)


def to_m(value: float, unit_code) -> float:
    """Đổi một giá trị dài sang m. `unit_code`: tên đơn vị hoặc mã enum eLength."""
    return value * length_factor(unit_code)


def moment_factor(force_unit, length_unit) -> float:
    """Hệ số nhân để đổi 1 đơn vị mô men -> kN-m."""
    return force_factor(force_unit) * length_factor(length_unit)
