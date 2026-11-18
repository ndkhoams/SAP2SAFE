#!/usr/bin/env python3
"""Phia tham chieu Python cho kiem chung parity C# vs Python (SAP2SAFE).

Xay dung CUNG DAU VAO nhu phia C# (xem Program.cs), chi tu file MONG.sf:
- Points: POINT OBJECT CONNECTIVITY (X, Y, Z=0).
- Restraints: JOINT ASSIGNMENTS - RESTRAINTS (Yes/No -> bool[6]).
- Pattern_info: LOAD PATTERN DEFINITIONS, chi pattern KHONG ket thuc
  bang _ABOVE (Type -> design_type, "Self Weight Multiplier" -> float).
- Outputs: cases = ten pattern theo thu tu xuat hien trong
  LOAD CASE DEFINITIONS (ten duy nhat); combos = gom cac dong cung Name
  trong LOAD COMBINATION DEFINITIONS (items [(Load Name, SF)],
  Type lay tu dong dau cua combo).
- Reactions: JOINT LOADS ASSIGNMENTS - FORCE, moi dong -> Reaction
  voi f/m = -FX..-MZ (DAO DAU vi tai trong MONG.sf da la tai SAFE).
- Selected = tat ca ten case + tat ca ten combo.
- Pipeline: step_mode="last", flip_sign=True, safe_version="22.5.1".

Ghi file ra --out (mac dinh /tmp/parity/py.f2k) bang
sap2safe.app.build_f2k_model + sap2safe.sf_writer.write_f2k.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Python reference cho parity C# vs Python")
    ap.add_argument("--mong", default="/home/hatch/workspace/sap2safe_work/fixtures/MONG.sf")
    ap.add_argument("--out", default="/tmp/parity/py.f2k")
    ap.add_argument("--sap-root", default="/home/hatch/workspace/sap2safe")
    args = ap.parse_args()

    sys.path.insert(0, args.sap_root)
    from sap2safe.app import build_f2k_model
    from sap2safe.model import Reaction, SapOutput
    from sap2safe.sf_reader import parse_sf
    from sap2safe.sf_writer import write_f2k

    tables = parse_sf(args.mong)

    joints_xyz = {
        r["UniqueName"]: (float(r["X"]), float(r["Y"]), 0.0)
        for r in tables["POINT OBJECT CONNECTIVITY"]
    }
    restraints = {
        r["UniqueName"]: tuple(r[k] == "Yes" for k in ("UX", "UY", "UZ", "RX", "RY", "RZ"))
        for r in tables["JOINT ASSIGNMENTS - RESTRAINTS"]
    }
    pattern_info = {
        r["Name"]: {
            "design_type": r["Type"],
            "self_wt_mult": float(r["Self Weight Multiplier"]),
        }
        for r in tables["LOAD PATTERN DEFINITIONS"]
        if not r["Name"].endswith("_ABOVE")
    }

    case_names: list[str] = []
    for r in tables["LOAD CASE DEFINITIONS - LINEAR STATIC"]:
        if r["Name"] not in case_names:
            case_names.append(r["Name"])

    outputs: list[SapOutput] = [SapOutput(name=n, kind="case") for n in case_names]
    combo_names: list[str] = []
    combo_items: dict[str, list[tuple[str, float]]] = {}
    combo_types: dict[str, str] = {}
    for r in tables["LOAD COMBINATION DEFINITIONS"]:
        name = r["Name"]
        if name not in combo_items:
            combo_names.append(name)
            combo_items[name] = []
            combo_types[name] = r.get("Type", "Linear Add")
        combo_items[name].append((r["Load Name"], float(r["SF"])))
    for name in combo_names:
        outputs.append(SapOutput(name=name, kind="combo",
                                  combo_type=combo_types[name],
                                  components=combo_items[name]))

    reactions = [
        Reaction(
            joint=r["UniqueName"], output_name=r["Load Pattern"],
            output_kind="case", step_type="", step_num=0.0,
            f1=-float(r["FX"]), f2=-float(r["FY"]), f3=-float(r["FZ"]),
            m1=-float(r["MX"]), m2=-float(r["MY"]), m3=-float(r["MZ"]),
        )
        for r in tables["JOINT LOADS ASSIGNMENTS - FORCE"]
    ]

    selected = case_names + combo_names
    model, _info, warnings = build_f2k_model(
        reactions, joints_xyz, outputs, selected,
        joints_restraint=restraints, pattern_info=pattern_info,
        step_mode="last", flip_sign=True, safe_version="22.5.1",
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    counts = write_f2k(args.out, model)
    print(f"PY: points={counts['points']} patterns={counts['patterns']} "
          f"cases={counts['cases']} combos={counts['combos']} "
          f"point_loads={counts['point_loads']} path={args.out}")
    if warnings:
        print("PY warnings: " + "; ".join(warnings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
