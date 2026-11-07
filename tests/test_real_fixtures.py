"""Đối chiếu chéo các file THẬT: $2k (linear/nonlinear) <-> MONG.sf."""

from pathlib import Path

import pytest

from sap2safe.s2k_reader import parse_s2k
from sap2safe.sf_reader import parse_sf

FIXTURES = Path(__file__).resolve().parent.parent.parent / "sap2safe_work" / "fixtures"
LINEAR_2K = FIXTURES / "linear" / "1.NHA CAT KHO NPL TCVN - linear.$2k"
MONG = FIXTURES / "MONG.sf"


@pytest.fixture(scope="module")
def pair():
    assert LINEAR_2K.exists() and MONG.exists()
    return parse_s2k(str(LINEAR_2K)), parse_sf(str(MONG))


def test_xy_match_92_of_92_within_tolerance(pair):
    s2k, sf = pair
    sf_points = {}
    for r in sf["POINT OBJECT CONNECTIVITY"]:
        sf_points[r["UniqueName"]] = (float(r["X"]), float(r["Y"]), float(r["Z"]))
    restrained = s2k.restrained_joints_at_z(-1.5)
    assert len(restrained) == 92
    assert set(restrained) == set(sf_points)
    for j in restrained:
        x, y, _z = s2k.joints[j]
        sx, sy, sz = sf_points[j]
        assert abs(x - sx) <= 1e-6 and abs(y - sy) <= 1e-6, j
        assert sz == 0  # Z=0 trong SAFE (đổi gốc cao độ)


def test_combo_uls1_identical_in_2k_and_sf(pair):
    s2k, sf = pair
    sf_uls1 = [(r["Load Name"], float(r["SF"])) for r in
               sf["LOAD COMBINATION DEFINITIONS"] if r["Name"] == "ULS_1"]
    assert sf_uls1 == s2k.combos["ULS_1"]["items"]
    assert sf_uls1 == [("SW", 1.1), ("SDL", 1.2), ("COL", 1.2), ("SOL", 1.2)]


def test_sf_env_combos_match_2k(pair):
    s2k, sf = pair
    for env in ("ENV ULS", "ENV SLS"):
        sf_items = [(r["Load Name"], float(r["SF"])) for r in
                    sf["LOAD COMBINATION DEFINITIONS"] if r["Name"] == env]
        assert sf_items == s2k.combos[env]["items"], env


def test_sf_points_are_exactly_the_restrained_joints(pair):
    s2k, sf = pair
    sf_ids = {r["UniqueName"] for r in sf["POINT OBJECT CONNECTIVITY"]}
    assert sf_ids == set(s2k.restraints)
    sf_restr = {r["UniqueName"]: r for r in sf["JOINT ASSIGNMENTS - RESTRAINTS"]}
    assert set(sf_restr) == set(s2k.restraints)
    # Tất cả gối trong model này đều Yes cả 6 DOF.
    assert all(all(sf_restr[j][k] == "Yes" for k in ("UX", "UY", "UZ", "RX", "RY", "RZ"))
               for j in sf_restr)
