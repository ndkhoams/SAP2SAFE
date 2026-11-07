"""Test sf_reader trên file MONG.sf THẬT (SAFE 22.5.1)."""

from pathlib import Path

import pytest

from sap2safe.sf_reader import (
    REFERENCE_SUM_FZ,
    load_values,
    parse_sf,
    sum_fz_by_pattern,
)

FIXTURES = Path(__file__).resolve().parent.parent.parent / "sap2safe_work" / "fixtures"
MONG = FIXTURES / "MONG.sf"


@pytest.fixture(scope="module")
def mong():
    assert MONG.exists(), f"Thiếu fixture thật: {MONG}"
    return parse_sf(str(MONG))


def test_mong_program_control(mong):
    pc = mong["PROGRAM CONTROL"]
    assert len(pc) == 1
    assert pc[0]["ProgramName"] == "SAFE"
    assert pc[0]["Version"] == "22.5.1"
    assert pc[0]["CurrUnits"] == "kN, m, C"


def test_mong_counts(mong):
    assert len(mong["LOAD PATTERN DEFINITIONS"]) == 30  # 15 + 15 _ABOVE
    assert len(mong["LOAD CASE DEFINITIONS - LINEAR STATIC"]) == 30  # 15 x 2 dòng
    assert len(mong["LOAD COMBINATION DEFINITIONS"]) == 394
    assert len(mong["POINT OBJECT CONNECTIVITY"]) == 92
    assert len(mong["JOINT ASSIGNMENTS - RESTRAINTS"]) == 92
    assert len(mong["JOINT LOADS ASSIGNMENTS - FORCE"]) == 1380  # 15 x 92


def test_mong_patterns(mong):
    rows = mong["LOAD PATTERN DEFINITIONS"]
    names = [r["Name"] for r in rows]
    assert names.count("SW") == 1 and names.count("SW_ABOVE") == 1
    sw = next(r for r in rows if r["Name"] == "SW")
    assert sw["Type"] == "Dead" and sw["Self Weight Multiplier"] == "1"
    assert all(r["Self Weight Multiplier"] == "0"
               for r in rows if r["Name"] != "SW")
    wx = next(r for r in rows if r["Name"] == "WX1+")
    assert wx["Type"] == "Wind"
    assert next(r for r in rows if r["Name"] == "EX")["Type"] == "Seismic"


def test_mong_combos(mong):
    rows = mong["LOAD COMBINATION DEFINITIONS"]
    names = []
    for r in rows:
        if r["Name"] not in names:
            names.append(r["Name"])
    # 72 combo: 36 ULS + 26 SLS + 8 Wind + 2 ENV (ENV SLS / ENV ULS).
    assert len(names) == 72
    assert "ENV SLS" in names and "ENV ULS" in names
    assert "ULS_35" in names and "ULS_36" in names
    uls1 = [r for r in rows if r["Name"] == "ULS_1"]
    assert [(r["Load Name"], float(r["SF"])) for r in uls1] == [
        ("SW", 1.1), ("SDL", 1.2), ("COL", 1.2), ("SOL", 1.2)]
    env_sls = [r for r in rows if r["Name"] == "ENV SLS"]
    assert len(env_sls) == 26 and env_sls[0]["Type"] == "Envelope"


def test_mong_sum_fz_matches_reference(mong):
    sums = sum_fz_by_pattern(mong)
    assert set(sums) == set(REFERENCE_SUM_FZ)
    for pattern, ref in REFERENCE_SUM_FZ.items():
        assert abs(sums[pattern] - ref) <= 0.01, pattern


def test_mong_point_1_sw_load(mong):
    loads = load_values(mong)
    v = loads[("1", "SW")]
    assert v == {"FX": 0.415, "FY": -130.833, "FZ": -200.347,
                 "MX": 196.249, "MY": 0.622, "MZ": -0.0231}
    # _ABOVE không có dòng joint load nào.
    assert not any(p.endswith("_ABOVE") for (_u, p) in loads)
