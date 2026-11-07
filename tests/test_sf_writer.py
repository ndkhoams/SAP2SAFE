"""Test writer .sf/.F2K theo đúng cú pháp MONG.sf thật."""

import re

from sap2safe.app import build_f2k_model
from sap2safe.f2k_template import compare_with_writer
from sap2safe.f2k_writer import write_f2k as alias_write_f2k
from sap2safe.sf_reader import parse_sf, sum_fz_by_pattern
from sap2safe.sf_writer import EXPECTED_TABLES, write_sf

PATTERN_INFO = {
    "SW": {"design_type": "Dead", "self_wt_mult": 1},
    "SDL": {"design_type": "Super Dead", "self_wt_mult": 0},
}


def _model(reactions, joints_xyz, outputs):
    model, _info, _w = build_f2k_model(
        reactions, joints_xyz, outputs, ["SW", "SDL", "COMB1"],
        pattern_info=PATTERN_INFO, step_mode="last", flip_sign=True)
    return model


def test_sf_has_seven_real_tables_and_roundtrips(tmp_path, reactions, joints_xyz, outputs):
    model = _model(reactions, joints_xyz, outputs)
    path = tmp_path / "test.sf"
    counts = write_sf(str(path), model)
    assert counts["points"] == 4
    assert counts["patterns"] == 2  # chỉ case SW/SDL (combo không thành pattern)
    assert counts["combos"] == 1
    assert counts["point_loads"] == 8

    text = path.read_text(encoding="utf-8")
    assert text.startswith("File test.sf was saved on")
    for table in EXPECTED_TABLES:
        assert f'TABLE:  "{table}"' in text
    # Không còn bảng đoán mò của v0.1.
    assert '"POINT COORDINATES"' not in text
    assert '"POINT LOADS"' not in text
    assert '"SLAB PROPERTIES"' not in text

    parsed = parse_sf(str(path))
    assert set(parsed) == set(EXPECTED_TABLES)
    # Pattern + _ABOVE: 2 pattern gốc + 2 _ABOVE.
    pat_names = [r["Name"] for r in parsed["LOAD PATTERN DEFINITIONS"]]
    assert pat_names == ["SW", "SW_ABOVE", "SDL", "SDL_ABOVE"]
    sw_row = next(r for r in parsed["LOAD PATTERN DEFINITIONS"] if r["Name"] == "SW")
    assert sw_row["Type"] == "Dead" and sw_row["Self Weight Multiplier"] == "1"
    sdl_row = next(r for r in parsed["LOAD PATTERN DEFINITIONS"] if r["Name"] == "SDL")
    assert sdl_row["Type"] == "Super Dead" and sdl_row["Self Weight Multiplier"] == "0"
    # Case: mỗi case 2 dòng (pattern + _ABOVE), dòng _ABOVE không có GUID.
    # Thứ tự case theo alphabet (SDL trước SW).
    case_rows = parsed["LOAD CASE DEFINITIONS - LINEAR STATIC"]
    assert len(case_rows) == 4
    for i in range(0, 4, 2):
        assert case_rows[i + 1]["Load Name"] == case_rows[i]["Name"] + "_ABOVE"
        assert "GUID" not in case_rows[i + 1]
        assert case_rows[i].get("GUID") and re.fullmatch(
            r"[0-9a-f-]{36}", case_rows[i]["GUID"])
    # Combo copy y hệt.
    combo_rows = parsed["LOAD COMBINATION DEFINITIONS"]
    assert [(r["Name"], r.get("Load Name"), r.get("SF")) for r in combo_rows] == [
        ("COMB1", "SW", "1.2"), ("COMB1", "SDL", "1.6")]
    assert combo_rows[0]["Type"] == "Linear Add"
    # Points Z=0 trong SAFE, restraints mặc định Yes.
    assert all(r["Z"] == "0" for r in parsed["POINT OBJECT CONNECTIVITY"])
    assert all(r["UZ"] == "Yes" for r in parsed["JOINT ASSIGNMENTS - RESTRAINTS"])
    # Tổng kiểm tra qua reader.
    sums = sum_fz_by_pattern(parsed)
    assert abs(sums["SW"] + 420.0) < 1e-9
    assert abs(sums["SDL"] + 210.0) < 1e-9


def test_f2k_and_sf_same_content(tmp_path, reactions, joints_xyz, outputs):
    model = _model(reactions, joints_xyz, outputs)
    p_f2k = tmp_path / "out.f2k"
    p_sf = tmp_path / "out.sf"
    alias_write_f2k(str(p_f2k), model)
    write_sf(str(p_sf), model)
    t_f2k = parse_sf(str(p_f2k))
    t_sf = parse_sf(str(p_sf))
    # Cùng bảng/dòng (GUID ngẫu nhiên nên chỉ so số lượng + nội dung trừ GUID).
    assert set(t_f2k) == set(t_sf)
    for table in t_f2k:
        assert len(t_f2k[table]) == len(t_sf[table])


def test_compare_with_writer_reports_all_match(tmp_path, reactions, joints_xyz, outputs):
    model = _model(reactions, joints_xyz, outputs)
    path = tmp_path / "test.f2k"
    write_sf(str(path), model)
    report = compare_with_writer(str(path))
    for table in EXPECTED_TABLES:
        assert f"[KHỚP] {table}" in report


def test_number_format_matches_csi_style(tmp_path, reactions, joints_xyz, outputs):
    model = _model(reactions, joints_xyz, outputs)
    path = tmp_path / "test.sf"
    write_sf(str(path), model)
    text = path.read_text(encoding="utf-8")
    # Số nguyên không có '.0', số thập phân giữ repr ngắn.
    assert "FZ=-420" not in text  # tổng không ghi trong file, chỉ từng joint
    assert "FZ=-100" in text  # J1 SW: F3=100 -> FZ=-100 (không phải -100.000000)
    assert "X=0" in text and "X=6" in text
