"""Test s2k_reader trên file .$2k THẬT (SAP2000 26.3.0).

Fixture: ~/workspace/sap2safe_work/fixtures/{linear,nonlinear}/
"1.NHA CAT KHO NPL TCVN - {linear,nonlinear}.$2k".

HIỆU CHỈNH brief: combo thực tế là 72 (36 ULS + 26 SLS + 8 Wind +
2 ENV), không phải 62 như brief ghi (brief thiếu ULS_35/ULS_36 và 8
combo Wind_*).
"""

from pathlib import Path

import pytest

from sap2safe.s2k_reader import parse_s2k, s2k_outputs

FIXTURES = Path(__file__).resolve().parent.parent.parent / "sap2safe_work" / "fixtures"
LINEAR_2K = FIXTURES / "linear" / "1.NHA CAT KHO NPL TCVN - linear.$2k"
NONLINEAR_2K = FIXTURES / "nonlinear" / "1.NHA CAT KHO NPL TCVN - nonlinear.$2k"


@pytest.fixture(scope="module")
def linear():
    assert LINEAR_2K.exists(), f"Thiếu fixture thật: {LINEAR_2K}"
    return parse_s2k(str(LINEAR_2K))


@pytest.fixture(scope="module")
def nonlinear():
    assert NONLINEAR_2K.exists(), f"Thiếu fixture thật: {NONLINEAR_2K}"
    return parse_s2k(str(NONLINEAR_2K))


def test_program_control(linear):
    assert linear.program == "SAP2000"
    assert linear.version == "26.3.0"
    assert linear.units == "KN, m, C"


def test_patterns(linear):
    names = [p["name"] for p in linear.patterns]
    assert names == ["SW", "SDL", "COL", "SOL", "Lr", "WX1+", "WX2+", "WX1-",
                     "WX2-", "WY1+", "WY2+", "WY1-", "WY2-", "EX", "EY"]
    by_name = {p["name"]: p for p in linear.patterns}
    assert by_name["SW"]["design_type"] == "Dead"
    assert by_name["SW"]["self_wt_mult"] == 1
    assert by_name["SDL"]["design_type"] == "Super Dead"
    assert by_name["SDL"]["self_wt_mult"] == 0
    assert by_name["EX"]["design_type"] == "Quake"
    assert by_name["Lr"]["design_type"] == "Live"
    assert by_name["WX1+"]["design_type"] == "Wind"


def test_cases_linear_vs_nonlinear(linear, nonlinear):
    assert len(linear.cases) == 15
    assert all(not c.is_nonlinear for c in linear.cases)  # LinStatic
    assert len(nonlinear.cases) == 15
    assert all(c.is_nonlinear for c in nonlinear.cases)  # NonStatic
    assert [c.name for c in linear.cases] == [c.name for c in nonlinear.cases]
    # Case SW chỉ gồm 1 pattern SW (Full Load).
    assert linear.case_loads["SW"] == [("SW", 1.0)]


def test_combos_count_and_uls1(linear):
    assert len(linear.combos) == 72  # 36 ULS + 26 SLS + 8 Wind + 2 ENV
    uls = [n for n in linear.combo_order if n.startswith("ULS_")]
    sls = [n for n in linear.combo_order if n.startswith("SLS_")]
    wind = [n for n in linear.combo_order if n.startswith("Wind_")]
    env = [n for n in linear.combo_order if n.startswith("ENV")]
    assert len(uls) == 36 and len(sls) == 26
    assert len(wind) == 8 and set(env) == {"ENV ULS", "ENV SLS"}
    assert linear.combos["ULS_1"]["type"] == "Linear Add"
    assert linear.combos["ULS_1"]["items"] == [
        ("SW", 1.1), ("SDL", 1.2), ("COL", 1.2), ("SOL", 1.2)]
    assert linear.combos["ENV ULS"]["type"] == "Envelope"
    assert [c for c, _s in linear.combos["ENV ULS"]["items"]] == [
        f"ULS_{i}" for i in range(1, 35)]  # 34 thành phần, không có ULS_35/36
    assert [c for c, _s in linear.combos["ENV SLS"]["items"]] == [
        f"SLS_{i}" for i in range(1, 27)]
    assert linear.combos["Wind_WX1+"]["items"] == [("WX1+", 1.0)]


def test_linear_nonlinear_identical_except_case_type(linear, nonlinear):
    assert linear.patterns == nonlinear.patterns
    assert linear.combos == nonlinear.combos
    assert linear.joints == nonlinear.joints
    assert linear.restraints == nonlinear.restraints


def test_restrained_joints_at_z_minus_1_5(linear):
    assert len(linear.joints) == 424
    assert len(linear.restraints) == 92
    assert linear.suggested_z() == -1.5
    at_z = linear.restrained_joints_at_z(-1.5)
    assert len(at_z) == 92
    assert at_z[:5] == ["1", "4", "7", "9", "27"]
    assert linear.joints["1"] == (12.4, 2.2, -1.5)


def test_s2k_outputs_shape(linear):
    outs = s2k_outputs(linear)
    assert len(outs) == 15 + 72
    assert outs[0].kind == "case" and outs[-1].kind == "combo"
    env_uls = next(o for o in outs if o.name == "ENV ULS")
    assert env_uls.combo_type == "Envelope" and len(env_uls.components) == 34
