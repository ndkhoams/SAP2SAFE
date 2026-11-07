"""Test đọc Excel Joint Reactions (file mẫu do chính test tạo ra)."""

from pathlib import Path

import pytest
from openpyxl import Workbook

from sap2safe.excel_reader import list_outputs, read_joint_reactions

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "mau_joint_reactions.xlsx"


def _make_workbook(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Joint Reactions"
    # Dòng tiêu đề TABLE + đơn vị phía trên header (đúng kiểu SAP export).
    ws.append(["TABLE:  Joint Reactions"])
    ws.append(["Joint", "OutputCase", "CaseType", "StepType", "StepNum",
               "F1", "F2", "F3", "M1", "M2", "M3"])
    ws.append(["", "", "", "", "", "kN", "kN", "kN", "kN-m", "kN-m", "kN-m"])
    ws.append(["J1", "SW", "Nonlinear Static", "Step", 1, 5, 0, 100, 0, 20, 0])
    ws.append(["J2", "SW", "Nonlinear Static", "Step", 1, 5, 0, 120, 0, 25, 0])
    ws.append(["~1", "SW", "Nonlinear Static", "Step", 1, 1, 0, 10, 0, 0, 0])  # mesh -> bỏ
    ws.append(["", "SW", "Nonlinear Static", "Step", 1, 0, 0, 0, 0, 0, 0])  # dòng tổng -> bỏ
    ws.append(["J1", "SDL", "Nonlinear Static", "Step", 1, 2, 0, 50, 0, 10, 0])
    coords = wb.create_sheet("Joint Coordinates")
    coords.append(["Joint", "X", "Y", "Z"])
    coords.append(["J1", 0, 0, 0])
    coords.append(["J2", 6, 0, 0])
    wb.save(path)


def test_reader_parses_sap_style_workbook(tmp_path):
    path = tmp_path / "reactions.xlsx"
    _make_workbook(path)
    reactions, joints = read_joint_reactions(str(path))
    assert len(reactions) == 3  # bỏ joint "~1" và dòng tổng
    assert {r.joint for r in reactions} == {"J1", "J2"}
    assert list_outputs(reactions) == ["SW", "SDL"]
    sw_j2 = next(r for r in reactions if r.joint == "J2" and r.output_name == "SW")
    assert sw_j2.f3 == 120.0 and sw_j2.m2 == 25.0
    assert joints["J2"] == (6.0, 0.0, 0.0)


def test_reader_rejects_file_without_reactions_table(tmp_path):
    path = tmp_path / "empty.xlsx"
    wb = Workbook()
    wb.active.append(["Hello", "World"])
    wb.save(path)
    with pytest.raises(ValueError, match="Joint Reactions"):
        read_joint_reactions(str(path))


def test_example_file_parses():
    assert EXAMPLE.exists(), "examples/mau_joint_reactions.xlsx chưa được tạo"
    reactions, joints = read_joint_reactions(str(EXAMPLE))
    assert len(joints) == 4
    assert set(list_outputs(reactions)) == {"SW", "SDL", "WX1+"}
    assert joints["J4"] == (6.0, 6.0, 0.0)
