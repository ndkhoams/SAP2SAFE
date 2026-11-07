"""Chọn step để "đóng băng" phản lực phi tuyến thành 1 vector duy nhất.

Bản chất: nonlinear case có nhiều step; Max của từng thành phần xảy ra ở
các step khác nhau, KHÔNG đồng thời — không được gộp Max từng thành phần
thành 1 vector. Các mode:
- "last":      StepNum lớn nhất (mặc định cho Nonlinear Static / Staged).
- "specific":   1 step do user chọn (StepType + StepNum).
- "governing":  step có max |F3| tại joint khống chế; lấy vector đồng thời
                tại step đó cho mọi joint.
- "maxmin":    tách 2 pattern <tên>_MAX / <tên>_MIN (chỉ cho Envelope / RS /
                Moving). Mất tính đồng thời — hàm trả kèm cảnh báo.
"""

from __future__ import annotations

from collections import defaultdict

from .model import FrozenLoad, Reaction

STEP_MODES = ("last", "specific", "governing", "maxmin")


def _step_key(r: Reaction) -> tuple[str, float]:
    return (r.step_type or "", float(r.step_num))


def _group_by_output(rows: list[Reaction]) -> dict[str, list[Reaction]]:
    grouped: dict[str, list[Reaction]] = defaultdict(list)
    for r in rows:
        grouped[r.output_name].append(r)
    return grouped


def freeze_reactions(
    rows: list[Reaction],
    mode: str = "last",
    specific: tuple[str, float] | None = None,
    joints: dict[str, tuple[float, float]] | None = None,
) -> tuple[list[FrozenLoad], list[str]]:
    """Đóng băng các dòng Reaction thành FrozenLoad (CHƯA đổi dấu).

    `joints`: dict tên joint -> (x, y); joint không có trong dict sẽ bị bỏ
    qua kèm cảnh báo. Trả về (frozen, warnings).
    """
    if mode not in STEP_MODES:
        raise ValueError(f"Step mode không hỗ trợ: {mode!r} (chọn trong {STEP_MODES})")
    joints = joints or {}
    frozen: list[FrozenLoad] = []
    warnings: list[str] = []
    grouped = _group_by_output(rows)

    for output_name, out_rows in grouped.items():
        # Gom theo joint -> {step_key: Reaction}
        by_joint: dict[str, dict[tuple[str, float], Reaction]] = defaultdict(dict)
        for r in out_rows:
            by_joint[r.joint][_step_key(r)] = r

        if mode == "maxmin":
            _freeze_maxmin(output_name, by_joint, joints, frozen, warnings)
            continue

        chosen_step: dict[str, tuple[str, float]] = {}
        if mode == "last":
            for joint, steps in by_joint.items():
                chosen_step[joint] = max(steps.keys(), key=lambda k: k[1])
        elif mode == "specific":
            if specific is None:
                raise ValueError("Mode 'specific' cần tham số specific=(StepType, StepNum)")
            for joint, steps in by_joint.items():
                if specific not in steps:
                    warnings.append(
                        f"{output_name} / {joint}: không có step {specific}, "
                        "bỏ qua joint này."
                    )
                    continue
                chosen_step[joint] = specific
        elif mode == "governing":
            # Joint khống chế = joint có max |F3| trên mọi step; step khống chế
            # = step đạt max |F3| đó. Lấy vector đồng thời tại step đó.
            best: tuple[float, str, tuple[str, float]] | None = None
            for joint, steps in by_joint.items():
                for key, r in steps.items():
                    if best is None or abs(r.f3) > best[0]:
                        best = (abs(r.f3), joint, key)
            if best is None:
                continue
            gov_step = best[2]
            warnings.append(
                f"{output_name}: governing step = {gov_step[0] or 'Step'} {gov_step[1]} "
                f"(max |F3| tại joint {best[1]})."
            )
            chosen_step = {j: gov_step for j in by_joint if gov_step in by_joint[j]}

        for joint, step in chosen_step.items():
            if joint not in joints:
                warnings.append(f"{output_name} / {joint}: không có tọa độ, bỏ qua.")
                continue
            r = by_joint[joint][step]
            x, y = joints[joint]
            frozen.append(
                FrozenLoad(
                    joint=joint,
                    x=x,
                    y=y,
                    pattern=output_name,
                    fx=r.f1,
                    fy=r.f2,
                    fz=r.f3,
                    mx=r.m1,
                    my=r.m2,
                    mz=r.m3,
                    source_step=f"{r.step_type or 'Step'} {r.step_num:g}",
                )
            )

    return frozen, warnings


def _freeze_maxmin(output_name, by_joint, joints, frozen, warnings):
    """Tách mỗi output thành 2 pattern _MAX / _MIN theo từng thành phần.

    CẢNH BÁO: Max của F3 và Max của M2 có thể ở 2 step khác nhau — vector
    _MAX không phải trạng thái đồng thời thật. Chỉ dùng khi user chấp nhận.
    """
    warnings.append(
        f"{output_name}: tách MAX/MIN — các thành phần cực đại có thể ở các "
        "step khác nhau, vector này KHÔNG đồng thời (xem HUONG_DAN_TEST.md)."
    )
    for suffix, pick in (("_MAX", max), ("_MIN", min)):
        for joint, steps in by_joint.items():
            if joint not in joints:
                continue
            vals = list(steps.values())
            x, y = joints[joint]
            frozen.append(
                FrozenLoad(
                    joint=joint,
                    x=x,
                    y=y,
                    pattern=f"{output_name}{suffix}",
                    fx=pick(v.f1 for v in vals),
                    fy=pick(v.f2 for v in vals),
                    fz=pick(v.f3 for v in vals),
                    mx=pick(v.m1 for v in vals),
                    my=pick(v.m2 for v in vals),
                    mz=pick(v.m3 for v in vals),
                    source_step=f"{suffix[1:]} từng thành phần",
                )
            )
