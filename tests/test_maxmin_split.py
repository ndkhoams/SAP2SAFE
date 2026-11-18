"""Test quy tắc tách MAX/MIN mặc định + combo _ENV (user chốt 18/11).

- Case có dòng Max/Min giống nhau hết -> 1 pattern tên gốc, không _ENV.
- Case có dòng Max/Min khác nhau -> tách _MAX/_MIN + combo Envelope
  <tên>_ENV, combo gốc dùng case đó viết lại sang _ENV (giữ nguyên SF).
- Case chỉ có dòng Step -> 1 pattern tên gốc, không tách.
"""

from sap2safe.app import build_f2k_model
from sap2safe.model import Reaction, SapOutput
from sap2safe.step_select import freeze_reactions

JOINTS_XYZ = {"J1": (0.0, 0.0, 0.0), "J2": (6.0, 0.0, 0.0)}


def _mm(joint, output, f3_max, f3_min, m2_max=0.0, m2_min=0.0):
    """2 dòng Max/Min của 1 joint cho 1 case (như SAP báo cáo)."""
    return [
        Reaction(joint=joint, output_name=output, output_kind="case",
                 step_type="Max", step_num=0.0,
                 f1=0.0, f2=0.0, f3=f3_max, m1=0.0, m2=m2_max, m3=0.0),
        Reaction(joint=joint, output_name=output, output_kind="case",
                 step_type="Min", step_num=0.0,
                 f1=0.0, f2=0.0, f3=f3_min, m1=0.0, m2=m2_min, m3=0.0),
    ]


def _step_rows(joint, output, f3):
    return [Reaction(joint=joint, output_name=output, output_kind="case",
                     step_type="Step", step_num=1.0,
                     f1=0.0, f2=0.0, f3=f3, m1=0.0, m2=0.0, m3=0.0)]


def _outputs(with_env_collision=False):
    outs = [
        SapOutput(name="SW", kind="case", case_type=2, is_nonlinear=True),
        SapOutput(name="SDL", kind="case", case_type=2, is_nonlinear=True),
        SapOutput(name="ULS_1", kind="combo", combo_type="Linear Add",
                  components=[("SW", 1.1), ("SDL", 1.2)]),
    ]
    if with_env_collision:
        outs.append(SapOutput(name="SW_ENV", kind="combo", combo_type="Linear Add",
                              components=[("SW", 1.0)]))
    return outs


def _combo_dict(model):
    return {c["name"]: (c["type"], list(c["items"])) for c in model.combos}


def test_max_equal_min_keeps_single_pattern_and_combo_unchanged():
    # (a) Max == Min mọi joint -> 1 pattern tên gốc, không _ENV.
    rows = (_mm("J1", "SW", 100.0, 100.0) + _mm("J2", "SW", 120.0, 120.0)
            + _mm("J1", "SDL", 50.0, 50.0) + _mm("J2", "SDL", 60.0, 60.0))
    model, info, _w = build_f2k_model(
        rows, JOINTS_XYZ, _outputs(), ["SW", "SDL", "ULS_1"])
    assert [p["name"] for p in model.patterns] == ["SW", "SDL"]
    assert [c["name"] for c in model.cases] == ["SW", "SDL"]
    combos = _combo_dict(model)
    assert set(combos) == {"ULS_1"}
    assert combos["ULS_1"] == ("Linear Add", [("SW", 1.1), ("SDL", 1.2)])
    assert info["splits"]["SW"]["split"] is False
    assert info["splits"]["SW"]["env"] is None
    assert any("giữ 1 pattern" in n for n in info["notes"])


def test_max_differs_splits_and_rewrites_combo():
    # (b) SW khác nhau ở J2 (F3 Max 120 vs Min 100) -> tách + _ENV + viết lại.
    rows = (_mm("J1", "SW", 100.0, 100.0) + _mm("J2", "SW", 120.0, 100.0)
            + _mm("J1", "SDL", 50.0, 50.0) + _mm("J2", "SDL", 60.0, 60.0))
    model, info, _w = build_f2k_model(
        rows, JOINTS_XYZ, _outputs(), ["SW", "SDL", "ULS_1"])
    assert [p["name"] for p in model.patterns] == ["SW_MAX", "SW_MIN", "SDL"]
    assert [c["name"] for c in model.cases] == ["SW_MAX", "SW_MIN", "SDL"]
    combos = _combo_dict(model)
    # _ENV đặt TRƯỚC combo gốc.
    assert [c["name"] for c in model.combos] == ["SW_ENV", "ULS_1"]
    assert combos["SW_ENV"] == ("Envelope", [("SW_MAX", 1.0), ("SW_MIN", 1.0)])
    assert combos["ULS_1"] == ("Linear Add", [("SW_ENV", 1.1), ("SDL", 1.2)])
    # Tải đã đổi dấu: SW_MAX FZ tại J2 = -120, SW_MIN FZ tại J2 = -100.
    loads = {(ld["point"], ld["pattern"]): ld["fz"] for ld in model.point_loads}
    assert loads[("J2", "SW_MAX")] == -120.0
    assert loads[("J2", "SW_MIN")] == -100.0
    assert loads[("J1", "SW_MAX")] == -100.0
    assert len(model.point_loads) == 6  # SW 2 pattern x 2 joint + SDL 1 x 2
    assert info["splits"]["SW"]["split"] is True
    assert info["splits"]["SW"]["env"] == "SW_ENV"
    assert info["splits"]["SW"]["max_diff"] == 20.0
    assert info["splits"]["SW"]["max_joint"] == "J2"
    assert any("SW_ENV" in n for n in info["notes"])
    assert any("viết lại" in n for n in info["notes"])


def test_step_only_case_keeps_single_pattern():
    # (c) Case chỉ có dòng Step -> 1 pattern tên gốc, không tách.
    rows = _step_rows("J1", "SW", 100.0) + _step_rows("J2", "SW", 120.0)
    model, info, _w = build_f2k_model(rows, JOINTS_XYZ, _outputs(), ["SW"])
    assert [p["name"] for p in model.patterns] == ["SW"]
    assert model.combos == []
    assert info["splits"]["SW"]["split"] is False
    assert info["splits"]["SW"]["has_maxmin"] is False


def test_split_without_any_combo_still_creates_env():
    # (d) Không combo nào dùng SW nhưng SW tách -> vẫn có SW_ENV trong file.
    rows = _mm("J1", "SW", 100.0, 90.0) + _mm("J2", "SW", 120.0, 100.0)
    model, info, _w = build_f2k_model(rows, JOINTS_XYZ, _outputs(), ["SW"])
    combos = _combo_dict(model)
    assert set(combos) == {"SW_ENV"}
    assert combos["SW_ENV"] == ("Envelope", [("SW_MAX", 1.0), ("SW_MIN", 1.0)])


def test_tolerance_boundary():
    # Chênh lệch trong dung sai (1e-6 rel) -> không tách; vượt dung sai -> tách.
    rows = _mm("J1", "SW", 100.0, 100.0000001) + _mm("J2", "SW", 120.0, 120.0)
    _m, info, _w = build_f2k_model(rows, JOINTS_XYZ, _outputs(), ["SW"])
    assert info["splits"]["SW"]["split"] is False
    rows = _mm("J1", "SW", 100.0, 100.001) + _mm("J2", "SW", 120.0, 120.0)
    _m, info, _w = build_f2k_model(rows, JOINTS_XYZ, _outputs(), ["SW"])
    assert info["splits"]["SW"]["split"] is True


def test_joint_missing_one_side_is_filled_with_warning():
    # J1 đủ 2 phía và khác nhau -> tách; J2 chỉ có dòng Max -> _MIN lấy
    # dòng Max bù vào + warning, không crash.
    rows = (_mm("J1", "SW", 100.0, 90.0)
            + [Reaction(joint="J2", output_name="SW", output_kind="case",
                        step_type="Max", step_num=0.0,
                        f1=0.0, f2=0.0, f3=120.0, m1=0.0, m2=0.0, m3=0.0)])
    model, info, warnings = build_f2k_model(
        rows, JOINTS_XYZ, _outputs(), ["SW"])
    assert [p["name"] for p in model.patterns] == ["SW_MAX", "SW_MIN"]
    loads = {(ld["point"], ld["pattern"]): ld["fz"] for ld in model.point_loads}
    assert loads[("J2", "SW_MIN")] == -120.0  # bù từ dòng Max
    assert info["splits"]["SW"]["filled_joints"] == ["J2"]
    assert any("J2" in w and "thiếu dòng Min" in w for w in warnings)


def test_env_name_collision_gets_suffix():
    # Đã có combo tên SW_ENV trong model -> combo tự sinh lấy SW_ENV_2.
    rows = _mm("J1", "SW", 100.0, 90.0) + _mm("J2", "SW", 120.0, 100.0)
    model, info, _w = build_f2k_model(
        rows, JOINTS_XYZ, _outputs(with_env_collision=True),
        ["SW", "SW_ENV"])
    combos = _combo_dict(model)
    assert combos["SW_ENV_2"] == ("Envelope", [("SW_MAX", 1.0), ("SW_MIN", 1.0)])
    # Combo gốc tên SW_ENV vẫn giữ tên, chỉ thành phần SW viết lại -> SW_ENV_2.
    assert combos["SW_ENV"] == ("Linear Add", [("SW_ENV_2", 1.0)])
    assert info["splits"]["SW"]["env"] == "SW_ENV_2"


def test_freeze_reports_only_side():
    # Chỉ có dòng Max (không có Min) -> 1 pattern, splits ghi only_side.
    rows = [Reaction(joint="J1", output_name="SW", output_kind="case",
                     step_type="Max", step_num=0.0,
                     f1=0.0, f2=0.0, f3=100.0, m1=0.0, m2=0.0, m3=0.0)]
    _frozen, _w, splits = freeze_reactions(rows, "last", joints={"J1": (0.0, 0.0)})
    assert splits["SW"].split is False
    assert splits["SW"].only_side == "Max"
