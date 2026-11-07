"""Dataclasses trung gian — không phụ thuộc COM, import được trên Linux.

Luồng dữ liệu: SAP (JointReact / Excel) -> Reaction -> freeze (step_select)
-> FrozenLoad (chưa đổi dấu) -> mapping (đổi dấu + sanitize tên)
-> F2kModel -> f2k_writer / excel_writer / report.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Joint:
    """Một joint object của SAP tại level đang chuyển."""

    name: str
    x: float
    y: float
    z: float
    restrained: bool = False
    # Gối từng DOF (U1,U2,U3,R1,R2,R3); None = chưa rõ (mặc định Yes cả 6
    # khi xuất, kèm cảnh báo trong log).
    restraint: tuple[bool, bool, bool, bool, bool, bool] | None = None


@dataclass
class Reaction:
    """Một dòng phản lực JointReact: 1 joint x 1 step của 1 output."""

    joint: str
    output_name: str
    output_kind: str  # "case" | "combo"
    step_type: str = ""  # "Step" | "Max" | "Min" | "Mode" | ""
    step_num: float = 0.0
    f1: float = 0.0
    f2: float = 0.0
    f3: float = 0.0
    m1: float = 0.0
    m2: float = 0.0
    m3: float = 0.0


@dataclass
class SapOutput:
    """Một load case hoặc load combo trong model SAP."""

    name: str
    kind: str  # "case" | "combo"
    case_type: int | None = None  # eLoadCaseType (chỉ cho kind="case")
    is_nonlinear: bool = False
    combo_type: str | None = None  # "Linear Add" | "Envelope" | ...
    components: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class FrozenLoad:
    """Vector tải đã "đóng băng" tại 1 joint — CHƯA đổi dấu (còn là phản lực SAP).

    Sau mapping, fx..mz mang dấu của tải SAFE (đã đảo nếu flip_sign=True).
    """

    joint: str
    x: float
    y: float
    pattern: str  # tên pattern SAFE (đã sanitize) hoặc tên output gốc
    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0
    mx: float = 0.0
    my: float = 0.0
    mz: float = 0.0
    source_step: str = ""  # vd "Step 1" / "Max" / "governing: Step 3"


@dataclass
class SlabOutline:
    """Outline sàn tại level (polygon khép kín, tọa độ XY)."""

    points: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class F2kModel:
    """Mọi thứ cần để sinh .F2K + file Excel SAFE-tables + file .LOG."""

    patterns: list[dict] = field(default_factory=list)  # {name, type, self_wt_mult}
    cases: list[dict] = field(default_factory=list)  # {name, type}
    combos: list[dict] = field(default_factory=list)  # {name, type, items:[(case, sf)]}
    points: list[dict] = field(default_factory=list)  # {name, x, y}
    point_loads: list[dict] = field(default_factory=list)  # {point, pattern, fx..mz}
    # KHÔNG tự sinh slab/bbox: MONG.sf không có area/spring/slab outline.
    # Các trường dưới giữ lại để tương thích, writer .sf không dùng chúng.
    slab_thickness: float = 0.5  # m (không dùng ở v0.1)
    slab_offset: float = 0.5  # m (không dùng ở v0.1)
    material: str = "C30/37"  # (không dùng ở v0.1)
    slab_outline: list[tuple[float, float]] = field(default_factory=list)
    units: str = "kN, m, C"
    # Version SAFE ghi trong PROGRAM CONTROL (lấy từ MONG.sf thật).
    safe_version: str = "22.5.1"
