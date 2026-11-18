"""Test logic chọn step để đóng băng phản lực."""

from sap2safe.model import Reaction
from sap2safe.step_select import freeze_reactions


def _rows_for_steps():
    # 1 joint J1, 1 output PUSH, 3 step; F3 tăng dần, M2 đổi dấu.
    rows = []
    for step, (f3, m2) in enumerate([(100.0, 10.0), (150.0, -20.0), (120.0, 30.0)], start=1):
        rows.append(Reaction(joint="J1", output_name="PUSH", output_kind="case",
                             step_type="Step", step_num=float(step),
                             f1=1.0, f2=0.0, f3=f3, m1=0.0, m2=m2, m3=0.0))
    return rows


def test_last_step_picks_highest_step_num():
    frozen, _w, _s = freeze_reactions(_rows_for_steps(), "last", joints={"J1": (0.0, 0.0)})
    assert len(frozen) == 1
    assert frozen[0].fz == 120.0 and frozen[0].my == 30.0
    assert frozen[0].source_step == "Step 3"


def test_specific_step():
    frozen, _w, _s = freeze_reactions(_rows_for_steps(), "specific",
                                  specific=("Step", 2.0), joints={"J1": (0.0, 0.0)})
    assert len(frozen) == 1
    assert frozen[0].fz == 150.0 and frozen[0].my == -20.0


def test_governing_step_uses_simultaneous_vector():
    # J1 step2 có max |F3| = 150 -> mọi joint lấy vector tại step 2.
    rows = _rows_for_steps()
    rows.append(Reaction(joint="J2", output_name="PUSH", output_kind="case",
                         step_type="Step", step_num=1.0, f3=50.0, m2=5.0))
    rows.append(Reaction(joint="J2", output_name="PUSH", output_kind="case",
                         step_type="Step", step_num=2.0, f3=80.0, m2=8.0))
    frozen, warnings, _s = freeze_reactions(rows, "governing",
                                        joints={"J1": (0.0, 0.0), "J2": (6.0, 0.0)})
    assert len(frozen) == 2
    by_joint = {f.joint: f for f in frozen}
    assert by_joint["J1"].fz == 150.0 and by_joint["J1"].my == -20.0
    assert by_joint["J2"].fz == 80.0 and by_joint["J2"].my == 8.0
    assert any("governing step" in w for w in warnings)


def _rows_maxmin(f3_max=150.0, f3_min=100.0, m2_max=30.0, m2_min=30.0):
    # 1 joint J1, 1 output PUSH, 2 dòng Max/Min do SAP báo cáo.
    return [
        Reaction(joint="J1", output_name="PUSH", output_kind="case",
                 step_type="Max", step_num=0.0,
                 f1=1.0, f2=0.0, f3=f3_max, m1=0.0, m2=m2_max, m3=0.0),
        Reaction(joint="J1", output_name="PUSH", output_kind="case",
                 step_type="Min", step_num=0.0,
                 f1=1.0, f2=0.0, f3=f3_min, m1=0.0, m2=m2_min, m3=0.0),
    ]


def test_maxmin_step_rows_behave_like_last():
    # Đổi 18/11: mode "maxmin" là alias của logic tách mặc định — case chỉ
    # có dòng Step thì KHÔNG tách, lấy step cuối như mode "last".
    frozen, _w, splits = freeze_reactions(_rows_for_steps(), "maxmin",
                                          joints={"J1": (0.0, 0.0)})
    assert len(frozen) == 1
    assert frozen[0].pattern == "PUSH"
    assert frozen[0].fz == 120.0 and frozen[0].my == 30.0
    assert splits["PUSH"].split is False
    assert splits["PUSH"].has_maxmin is False


def test_maxmin_splits_two_patterns_with_warning():
    # Dòng Max/Min khác nhau (F3 150 vs 100) -> tách _MAX/_MIN, Max trước.
    frozen, warnings, splits = freeze_reactions(_rows_maxmin(), "maxmin",
                                                joints={"J1": (0.0, 0.0)})
    assert {f.pattern for f in frozen} == {"PUSH_MAX", "PUSH_MIN"}
    by_pattern = {f.pattern: f for f in frozen}
    assert by_pattern["PUSH_MAX"].fz == 150.0  # Max F3
    assert by_pattern["PUSH_MIN"].fz == 100.0  # Min F3
    assert by_pattern["PUSH_MAX"].my == 30.0
    assert splits["PUSH"].split is True
    assert splits["PUSH"].max_diff == 50.0
    assert splits["PUSH"].max_joint == "J1"
    assert splits["PUSH"].max_component == "F3"
    assert any("KHÔNG đồng thời" in w or "không đồng thời" in w for w in warnings)


def test_last_keeps_single_pattern_when_max_equals_min():
    # Max == Min mọi thành phần -> 1 pattern tên gốc, lấy dòng Max.
    frozen, _w, splits = freeze_reactions(
        _rows_maxmin(f3_max=150.0, f3_min=150.0), "last", joints={"J1": (0.0, 0.0)})
    assert len(frozen) == 1
    assert frozen[0].pattern == "PUSH"
    assert frozen[0].fz == 150.0
    assert frozen[0].source_step == "Max 0"
    assert splits["PUSH"].split is False
    assert splits["PUSH"].max_diff == 0.0


def test_joint_without_coordinates_is_skipped_with_warning():
    frozen, warnings, _s = freeze_reactions(_rows_for_steps(), "last", joints={})
    assert frozen == []
    assert warnings
