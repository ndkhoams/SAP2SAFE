#!/usr/bin/env python3
"""Phia tham chieu Python cho Check 5 (parity tách MAX/MIN) — SAP2SAFE.

Xay dung CUNG DAU VAO nhu phia C# (xem Program.cs Check5SplitParity),
chi tu file MONG.sf:
- Points / Restraints / Pattern_info / Outputs / Combos: giong het
  python_reference.py (Check 2).
- Reactions: moi dong JOINT LOADS -> 2 dong Reaction: Max (f/m = -FX..-MZ)
  va Min (giong Max, TRU pattern WX1+ tai joint "1": F3 nhan 0.9 de tao
  ra truong hop tach). StepType "Max"/"Min", StepNum 0.0.
- Selected = tat ca ten case + tat ca ten combo.
- Pipeline: step_mode="last", flip_sign=True, safe_version="22.5.1".

Ky vong: chi WX1+ tach (WX1+_MAX/WX1+_MIN + combo Envelope WX1+_ENV);
8 combo goc chua WX1+ (SLS_3, SLS_11, SLS_19, ULS_3, ULS_11, ULS_19,
ULS_27, Wind_WX1+) viet lai sang WX1+_ENV (giu nguyen SF). Tong:
16 pattern, 16 case, 73 combo, 1472 point load.

Ghi file ra --out bang sap2safe.app.build_f2k_model + sf_writer.write_f2k.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Python reference cho Check 5 (tach MAX/MIN)")
    ap.add_argument("--mong", default="/home/hatch/workspace/sap2safe_work/fixtures/MONG.sf")
    ap.add_argument("--out", default="/tmp/parity/py_split.f2k")
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

    reactions: list[Reaction] = []
    for r in tables["JOINT LOADS ASSIGNMENTS - FORCE"]:
        f1 = -float(r["FX"])
        f2 = -float(r["FY"])
        f3 = -float(r["FZ"])
        m1 = -float(r["MX"])
        m2 = -float(r["MY"])
        m3 = -float(r["MZ"])
        reactions.append(Reaction(
            joint=r["UniqueName"], output_name=r["Load Pattern"],
            output_kind="case", step_type="Max", step_num=0.0,
            f1=f1, f2=f2, f3=f3, m1=m1, m2=m2, m3=m3))
        f3_min = f3 * 0.9 if (r["Load Pattern"] == "WX1+"
                             and r["UniqueName"] == "1") else f3
        reactions.append(Reaction(
            joint=r["UniqueName"], output_name=r["Load Pattern"],
            output_kind="case", step_type="Min", step_num=0.0,
            f1=f1, f2=f2, f3=f3_min, m1=m1, m2=m2, m3=m3))

    selected = case_names + combo_names
    model, info, warnings = build_f2k_model(
        reactions, joints_xyz, outputs, selected,
        joints_restraint=restraints, pattern_info=pattern_info,
        step_mode="last", flip_sign=True, safe_version="22.5.1",
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    counts = write_f2k(args.out, model)
    print(f"PY-SPLIT: points={counts['points']} patterns={counts['patterns']} "
          f"cases={counts['cases']} combos={counts['combos']} "
          f"point_loads={counts['point_loads']} path={args.out}")
    for name, sp in info["splits"].items():
        if sp["has_maxmin"]:
            print(f"PY-SPLIT: case {name}: split={sp['split']} env={sp['env']} "
                  f"max_diff={sp['max_diff']:g} joint={sp['max_joint']} "
                  f"comp={sp['max_component']}")
    for note in info["notes"]:
        print(f"PY-SPLIT note: {note}")
    if warnings:
        print("PY-SPLIT warnings: " + "; ".join(warnings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
