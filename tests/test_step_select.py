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
    frozen, _w = freeze_reactions(_rows_for_steps(), "last", joints={"J1": (0.0, 0.0)})
    assert len(frozen) == 1
    assert frozen[0].fz == 120.0 and frozen[0].my == 30.0
    assert frozen[0].source_step == "Step 3"


def test_specific_step():
    frozen, _w = freeze_reactions(_rows_for_steps(), "specific",
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
    frozen, warnings = freeze_reactions(rows, "governing",
                                        joints={"J1": (0.0, 0.0), "J2": (6.0, 0.0)})
    assert len(frozen) == 2
    by_joint = {f.joint: f for f in frozen}
    assert by_joint["J1"].fz == 150.0 and by_joint["J1"].my == -20.0
    assert by_joint["J2"].fz == 80.0 and by_joint["J2"].my == 8.0
    assert any("governing step" in w for w in warnings)


def test_maxmin_splits_two_patterns_with_warning():
    frozen, warnings = freeze_reactions(_rows_for_steps(), "maxmin",
                                        joints={"J1": (0.0, 0.0)})
    assert {f.pattern for f in frozen} == {"PUSH_MAX", "PUSH_MIN"}
    by_pattern = {f.pattern: f for f in frozen}
    assert by_pattern["PUSH_MAX"].fz == 150.0  # max F3
    assert by_pattern["PUSH_MIN"].fz == 100.0  # min F3
    assert by_pattern["PUSH_MAX"].my == 30.0  # max M2 (ở step khác!)
    assert any("KHÔNG đồng thời" in w for w in warnings)


def test_joint_without_coordinates_is_skipped_with_warning():
    frozen, warnings = freeze_reactions(_rows_for_steps(), "last", joints={})
    assert frozen == []
    assert warnings
