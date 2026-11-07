"""Fixture tổng hợp cho test SAP2SAFE (không dùng dữ liệu chat).

4 cột tại (0,0), (6,0), (0,6), (6,6), Z=0.
Cases SW/SDL/WX1+ là Nonlinear Static, 1 step (Final State Only).
Combo COMB1 = 1.2*SW + 1.6*SDL — Linear Add nhưng thành phần nonlinear.
"""

import pytest

from sap2safe.model import Reaction, SapOutput

JOINTS_XYZ = {
    "J1": (0.0, 0.0, 0.0),
    "J2": (6.0, 0.0, 0.0),
    "J3": (0.0, 6.0, 0.0),
    "J4": (6.0, 6.0, 0.0),
}


def _r(joint, output, kind, f1, f2, f3, m1=0.0, m2=0.0, m3=0.0,
       step_type="Step", step_num=1.0):
    return Reaction(joint=joint, output_name=output, output_kind=kind,
                    step_type=step_type, step_num=step_num,
                    f1=f1, f2=f2, f3=f3, m1=m1, m2=m2, m3=m3)


@pytest.fixture
def joints_xyz():
    return dict(JOINTS_XYZ)


@pytest.fixture
def outputs():
    return [
        SapOutput(name="SW", kind="case", case_type=2, is_nonlinear=True),
        SapOutput(name="SDL", kind="case", case_type=2, is_nonlinear=True),
        SapOutput(name="WX1+", kind="case", case_type=2, is_nonlinear=True),
        SapOutput(name="COMB1", kind="combo", combo_type="Linear Add",
                  components=[("SW", 1.2), ("SDL", 1.6)]),
    ]


@pytest.fixture
def reactions():
    rows = []
    sw_f3 = {"J1": 100.0, "J2": 120.0, "J3": 110.0, "J4": 90.0}
    sdl_f3 = {"J1": 50.0, "J2": 60.0, "J3": 55.0, "J4": 45.0}
    for j in ("J1", "J2", "J3", "J4"):
        rows.append(_r(j, "SW", "case", 5.0, 0.0, sw_f3[j], 0.0, 20.0, 0.0))
        rows.append(_r(j, "SDL", "case", 2.0, 0.0, sdl_f3[j], 0.0, 10.0, 0.0))
        rows.append(_r(j, "WX1+", "case", 30.0, 0.0, 0.0, 0.0, 0.0, 15.0))
        rows.append(_r(j, "COMB1", "combo", 0.0, 0.0,
                      1.2 * sw_f3[j] + 1.6 * sdl_f3[j]))
    return rows
