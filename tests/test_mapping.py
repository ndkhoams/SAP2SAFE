"""Test mapping: đổi dấu, sanitize tên (giữ +, -, khoảng trắng), combo copy.

Hiệu chỉnh theo MONG.sf thật: tên KHÔNG bị sanitize kiểu cũ nữa
(`WX1+`, `ENV SLS` giữ nguyên); combo được copy y hệt định nghĩa SAP.
"""

from sap2safe.app import build_f2k_model
from sap2safe.mapping import (
    apply_sign_flip,
    build_name_map,
    decide_combo_mapping,
    sanitize_name,
)
from sap2safe.model import FrozenLoad, SapOutput


def test_sanitize_keeps_plus_minus_space():
    assert sanitize_name("WX1+") == "WX1+"  # MONG.sf giữ nguyên dấu +
    assert sanitize_name("WY1-") == "WY1-"
    assert sanitize_name("ENV SLS") == "ENV SLS"  # khoảng trắng được giữ (writer quote)
    assert sanitize_name("A=B") == "A_B"  # chỉ '=' bị loại (phá Key=Value)
    assert sanitize_name("") == "LOAD"


def test_name_map_dedupes():
    outs = [SapOutput(name="A=B", kind="case"),
            SapOutput(name="A_B", kind="case")]
    mapping = build_name_map(outs)
    assert mapping["A=B"] == "A_B"
    assert mapping["A_B"] == "A_B_2"  # trùng -> thêm hậu tố


def test_sign_flip_negates_all_six_components():
    loads = [FrozenLoad(joint="J1", x=0, y=0, pattern="SW",
                        fx=5, fy=-3, fz=100, mx=1, my=20, mz=-7)]
    flipped = apply_sign_flip(loads, True)
    assert (flipped[0].fx, flipped[0].fy, flipped[0].fz) == (-5, 3, -100)
    assert (flipped[0].mx, flipped[0].my, flipped[0].mz) == (-1, -20, 7)
    kept = apply_sign_flip(loads, False)
    assert kept[0].fz == 100  # tắt đổi dấu -> giữ nguyên


def test_combo_with_nonlinear_components_is_copied_verbatim(outputs):
    # Hiệu chỉnh v0.1: combo chứa nonlinear KHÔNG còn standalone nữa mà
    # copy y hệt định nghĩa — SAFE tự tính từ các case đã đóng băng.
    by_name = {o.name: o for o in outputs}
    mode, items, note = decide_combo_mapping(by_name["COMB1"], by_name)
    assert mode == "rebuild"
    assert items == [("SW", 1.2), ("SDL", 1.6)]
    assert "nonlinear" in note


def test_linear_combo_is_copied():
    outs = [
        SapOutput(name="DEAD", kind="case", case_type=1, is_nonlinear=False),
        SapOutput(name="LIVE", kind="case", case_type=1, is_nonlinear=False),
        SapOutput(name="C1", kind="combo", combo_type="Linear Add",
                  components=[("DEAD", 1.2), ("LIVE", 1.6)]),
    ]
    by_name = {o.name: o for o in outs}
    mode, items, _note = decide_combo_mapping(by_name["C1"], by_name)
    assert mode == "rebuild"
    assert items == [("DEAD", 1.2), ("LIVE", 1.6)]


def test_envelope_combo_is_copied_too():
    outs = [
        SapOutput(name="SLS_1", kind="combo", combo_type="Linear Add",
                  components=[("SW", 1.0)]),
        SapOutput(name="ENV SLS", kind="combo", combo_type="Envelope",
                  components=[("SLS_1", 1.0)]),
    ]
    by_name = {o.name: o for o in outs}
    mode, items, _note = decide_combo_mapping(by_name["ENV SLS"], by_name)
    assert mode == "rebuild"  # MONG.sf copy cả combo Envelope
    assert items == [("SLS_1", 1.0)]


def test_combo_with_unknown_component_falls_back_standalone():
    outs = [SapOutput(name="C9", kind="combo", combo_type="Linear Add",
                      components=[("GHOST", 1.0)])]
    mode, items, _note = decide_combo_mapping(outs[0], {o.name: o for o in outs})
    assert mode == "standalone"
    assert items == [("C9", 1.0)]


def test_pipeline_sum_fz_equals_minus_sum_f3(reactions, joints_xyz, outputs):
    # Combo được chọn nhưng KHÔNG thành pattern riêng: chỉ case SW/SDL
    # được đóng băng; combo copy định nghĩa tham chiếu tới các case đó.
    model, info, _warnings = build_f2k_model(
        reactions, joints_xyz, outputs, ["SW", "SDL", "COMB1"],
        step_mode="last", flip_sign=True)
    sap_sums = info["sap_sums"]
    safe_sums = {}
    for ld in model.point_loads:
        safe_sums[ld["pattern"]] = safe_sums.get(ld["pattern"], 0.0) + ld["fz"]
    assert set(safe_sums) == set(sap_sums) == {"SW", "SDL"}
    for pattern, fz in safe_sums.items():
        assert abs(fz + sap_sums[pattern]) < 1e-9
    assert abs(safe_sums["SW"] + 420.0) < 1e-9  # ΣF3 SW = 420 -> ΣFZ = -420
    assert abs(safe_sums["SDL"] + 210.0) < 1e-9
    combo = next(c for c in model.combos if c["name"] == "COMB1")
    assert combo["items"] == [("SW", 1.2), ("SDL", 1.6)]  # copy y hệt
    assert len(model.point_loads) == 8  # 4 joint x 2 case (combo không có load riêng)
