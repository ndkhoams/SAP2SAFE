"""Validator round-trip: MONG.sf -> (đảo dấu thành phản lực SAP giả định)
-> writer -> so lại với MONG.sf. Phải khớp gần tuyệt đối.

Đây là test vàng trên Linux khi chưa có JointReact thật từ COM: nó chứng
minh writer sinh đúng cú pháp + đúng số từ chính dữ liệu file thật.
"""

from pathlib import Path

import pytest

from sap2safe.app import build_f2k_model
from sap2safe.model import Reaction, SapOutput
from sap2safe.sf_reader import parse_sf, so_sanh_voi_mong_sf
from sap2safe.sf_writer import write_sf

FIXTURES = Path(__file__).resolve().parent.parent.parent / "sap2safe_work" / "fixtures"
MONG = FIXTURES / "MONG.sf"


@pytest.fixture(scope="module")
def mong():
    assert MONG.exists(), f"Thiếu fixture thật: {MONG}"
    return parse_sf(str(MONG))


def test_roundtrip_mong_loads_match_within_tolerance(tmp_path, mong):
    # Phản lực SAP giả định = -tải SAFE trong MONG.sf.
    reactions: list[Reaction] = []
    for row in mong["JOINT LOADS ASSIGNMENTS - FORCE"]:
        reactions.append(Reaction(
            joint=row["UniqueName"], output_name=row["Load Pattern"],
            output_kind="case", step_type="Step", step_num=1.0,
            f1=-float(row["FX"]), f2=-float(row["FY"]), f3=-float(row["FZ"]),
            m1=-float(row["MX"]), m2=-float(row["MY"]), m3=-float(row["MZ"]),
        ))
    joints_xyz = {}
    restraints = {}
    for row in mong["POINT OBJECT CONNECTIVITY"]:
        joints_xyz[row["UniqueName"]] = (float(row["X"]), float(row["Y"]), 0.0)
    for row in mong["JOINT ASSIGNMENTS - RESTRAINTS"]:
        restraints[row["UniqueName"]] = tuple(
            row[k] == "Yes" for k in ("UX", "UY", "UZ", "RX", "RY", "RZ"))
    pattern_info = {}
    for row in mong["LOAD PATTERN DEFINITIONS"]:
        name = row["Name"]
        if name.endswith("_ABOVE"):
            continue
        pattern_info[name] = {"design_type": row["Type"],
                              "self_wt_mult": float(row["Self Weight Multiplier"])}
    outputs = [SapOutput(name=n, kind="case", case_type=2, is_nonlinear=True)
               for n in pattern_info]
    selected = list(pattern_info)
    model, _info, _w = build_f2k_model(
        reactions, joints_xyz, outputs, selected,
        joints_restraint=restraints, pattern_info=pattern_info,
        step_mode="last", flip_sign=True, safe_version="22.5.1")
    out_path = tmp_path / "roundtrip.sf"
    write_sf(str(out_path), model)
    report = so_sanh_voi_mong_sf(str(out_path), str(MONG), tol=0.01)
    assert "Joint load: xuất 1380, mẫu 1380" in report
    assert "KHỚP (trong dung sai)" in report
    assert "LỆCH" not in report.split("ΣFZ")[0].split("Kết luận lệch:")[1].split("\n")[0]
    # ΣFZ từng pattern khớp số tham chiếu.
    assert report.count("| KHỚP") == 15


def test_validator_detects_difference(tmp_path, mong):
    # Đổi 1 giá trị trong file xuất -> validator phải báo lệch.
    import shutil
    bad = tmp_path / "bad.sf"
    shutil.copy(str(MONG), bad)
    text = bad.read_text(encoding="utf-8")
    text = text.replace("FZ=-200.347", "FZ=-999.0", 1)
    bad.write_text(text, encoding="utf-8")
    report = so_sanh_voi_mong_sf(str(bad), str(MONG), tol=0.01)
    assert "CÓ LỆCH" in report
