"""Parse file .$2k text của SAP2000 (không cần SAP/COM, chạy trên Linux).

Dùng cho: GUI chế độ offline thứ 2 — đọc .$2k để lấy danh sách pattern /
case / combo / joint / Z mà không cần mở SAP. Phản lực vẫn cần COM hoặc
file Excel Joint Reactions (file .$2k không chứa kết quả phân tích).

Tên bảng/cột lấy đúng từ file .$2k thật SAP2000 26.3.0
(model "NHA CAT KHO NPL TCVN"):
- "PROGRAM CONTROL": ProgramName, Version, CurrUnits.
- "LOAD PATTERN DEFINITIONS": LoadPat, DesignType, SelfWtMult, GUID.
- "LOAD CASE DEFINITIONS": Case, Type (LinStatic/NonStatic/...),
  DesignType, GUID.
- "COMBINATION DEFINITIONS": ComboName, ComboType, CaseName, ScaleFactor.
- "JOINT COORDINATES": Joint, XorR, Y, Z (cột X tên là XorR).
- "JOINT RESTRAINT ASSIGNMENTS": Joint, U1, U2, U3, R1, R2, R3 (Yes/No).
- "CASE - STATIC 1 - LOAD ASSIGNMENTS": Case, LoadName, LoadSF.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .csi_text import parse_csi_tables
from .model import SapOutput


@dataclass
class S2kModel:
    program: str = ""
    version: str = ""
    units: str = ""
    # pattern: {name, design_type, self_wt_mult} — giữ đúng thứ tự trong file.
    patterns: list[dict] = field(default_factory=list)
    cases: list[SapOutput] = field(default_factory=list)
    # combo: tên -> {"type": str, "items": [(case, sf), ...]} (giữ thứ tự file).
    combos: dict[str, dict] = field(default_factory=dict)
    combo_order: list[str] = field(default_factory=list)
    joints: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    restraints: dict[str, tuple[bool, bool, bool, bool, bool, bool]] = field(
        default_factory=dict)
    # case -> [(load_name, sf)] từ CASE - STATIC 1 - LOAD ASSIGNMENTS.
    case_loads: dict[str, list[tuple[str, float]]] = field(default_factory=dict)

    def restrained_joints_at_z(self, z: float, tol: float = 0.005) -> list[str]:
        """ID các joint có gối tại cao độ Z (mặc định gợi ý Z này)."""
        return sorted(
            (j for j, (x, y, zz) in self.joints.items()
             if j in self.restraints and abs(zz - z) <= tol),
            key=_joint_sort_key,
        )

    def z_levels(self, tol: float = 0.005) -> list[float]:
        levels: list[float] = []
        for _x, _y, z in self.joints.values():
            if not any(abs(z - lv) <= tol for lv in levels):
                levels.append(z)
        return sorted(levels)

    def suggested_z(self) -> float | None:
        """Cao độ có nhiều joint có gối nhất (vd Z=-1.5: 92 joint)."""
        best: tuple[int, float] | None = None
        for z in self.z_levels():
            n = sum(1 for j in self.restraints
                    if abs(self.joints[j][2] - z) <= 0.005)
            if best is None or n > best[0]:
                best = (n, z)
        return best[1] if best else None


def _joint_sort_key(name: str):
    return (0, int(name)) if name.lstrip("-").isdigit() else (1, name)


def _yes(value: str | None) -> bool:
    return str(value).strip().lower() == "yes"


def parse_s2k(path: str) -> S2kModel:
    tables = parse_csi_tables(path)
    model = S2kModel()
    pc = tables.get("PROGRAM CONTROL", [])
    if pc:
        model.program = pc[0].get("ProgramName", "")
        model.version = pc[0].get("Version", "")
        model.units = pc[0].get("CurrUnits", "")
    for row in tables.get("LOAD PATTERN DEFINITIONS", []):
        try:
            sw = float(row.get("SelfWtMult", 0))
        except ValueError:
            sw = 0.0
        model.patterns.append({
            "name": row.get("LoadPat", ""),
            "design_type": row.get("DesignType", ""),
            "self_wt_mult": sw,
        })
    for row in tables.get("LOAD CASE DEFINITIONS", []):
        ctype = row.get("Type", "")
        model.cases.append(SapOutput(
            name=row.get("Case", ""),
            kind="case",
            case_type=None,
            is_nonlinear=ctype.lower().startswith("non"),
        ))
    for row in tables.get("COMBINATION DEFINITIONS", []):
        name = row.get("ComboName", "")
        if not name:
            continue
        if name not in model.combos:
            model.combos[name] = {
                "type": row.get("ComboType", "Linear Add"),
                "items": [],
            }
            model.combo_order.append(name)
        try:
            sf = float(row.get("ScaleFactor", 1))
        except ValueError:
            sf = 1.0
        model.combos[name]["items"].append((row.get("CaseName", ""), sf))
    for row in tables.get("JOINT COORDINATES", []):
        try:
            model.joints[row.get("Joint", "")] = (
                float(row.get("XorR", 0)),
                float(row.get("Y", 0)),
                float(row.get("Z", 0)),
            )
        except ValueError:
            continue
    for row in tables.get("JOINT RESTRAINT ASSIGNMENTS", []):
        model.restraints[row.get("Joint", "")] = tuple(
            _yes(row.get(k)) for k in ("U1", "U2", "U3", "R1", "R2", "R3")
        )
    for row in tables.get("CASE - STATIC 1 - LOAD ASSIGNMENTS", []):
        try:
            sf = float(row.get("LoadSF", 1))
        except ValueError:
            sf = 1.0
        model.case_loads.setdefault(row.get("Case", ""), []).append(
            (row.get("LoadName", ""), sf))
    return model


def s2k_outputs(model: S2kModel) -> list[SapOutput]:
    """Danh sách output (case + combo) để dùng chung với pipeline app."""
    outs = list(model.cases)
    for name in model.combo_order:
        combo = model.combos[name]
        outs.append(SapOutput(
            name=name, kind="combo", combo_type=combo["type"],
            components=list(combo["items"]),
        ))
    return outs
