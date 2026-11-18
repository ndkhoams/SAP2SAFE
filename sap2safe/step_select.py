"""Chọn step để "đóng băng" phản lực phi tuyến thành 1 vector duy nhất.

Bản chất: nonlinear case có nhiều step; Max của từng thành phần xảy ra ở
các step khác nhau, KHÔNG đồng thời — không được gộp Max từng thành phần
thành 1 vector.

Quy tắc tách MAX/MIN MẶC ĐỊNH (user chốt 18/11, áp dụng ở mode "last" và
"maxmin" — mode "maxmin" cũ nay là alias của logic này):
- Case có dòng Max/Min do SAP báo cáo (vd Nonlinear Static Final State
  Only trả đúng 2 dòng Max/Min mỗi joint): so sánh vector Max và Min
  từng joint, đủ 6 thành phần. Khác nhau (dung sai
  |Max-Min| > 1e-6 * max(1, |Max|, |Min|)) ở bất kỳ joint/thành phần
  nào -> tách thành 2 pattern <tên>_MAX + <tên>_MIN (Max trước Min sau);
  giống nhau hết -> 1 pattern tên gốc (lấy dòng Max). Pipeline tạo thêm
  combo Envelope <tên>_ENV (MAX 1.0 + MIN 1.0) và viết lại các combo gốc
  dùng case đó sang _ENV (xem app.py).
- Case chỉ có dòng "Step": giữ hành vi "last" cũ (step có StepNum lớn
  nhất), 1 pattern tên gốc, không tách.
- Các mode:
  - "last":      như trên (mặc định).
  - "specific":   1 step do user chọn (StepType + StepNum).
  - "governing":  step có max |F3| tại joint khống chế; lấy vector đồng thời
                  tại step đó cho mọi joint.
  - "maxmin":    alias của logic tách mặc định (như "last"). Logic tách
                  cũ (gộp cực đại từng thành phần qua mọi step, combo trỏ
                  tên gốc) đã bỏ vì xử lý combo chưa nhất quán.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .model import FrozenLoad, Reaction

STEP_MODES = ("last", "specific", "governing", "maxmin")

# Dung sai so sánh Max/Min (user chốt 18/11): khác nhau nếu ở bất kỳ
# joint/thành phần nào |Max-Min| > 1e-6 * max(1, |Max|, |Min|).
SPLIT_TOL_REL = 1e-6

_COMPONENTS = (("F1", "f1"), ("F2", "f2"), ("F3", "f3"),
               ("M1", "m1"), ("M2", "m2"), ("M3", "m3"))


@dataclass
class SplitInfo:
    """Kết quả phân tích tách MAX/MIN của 1 case (output).

    Pipeline dùng thông tin này để tạo combo _ENV và viết lại combo gốc.
    `env_name`: tên combo _ENV trong file xuất (đã xử lý trùng) — Pipeline
    điền; None nếu case không tách.
    `only_side`: "Max" nếu chỉ có dòng Max (không có Min), "Min" nếu chỉ
    có dòng Min, None nếu có đủ 2 phía hoặc không có phía nào.
    """

    output: str
    has_maxmin: bool = False
    split: bool = False
    max_diff: float = 0.0
    max_joint: str | None = None
    max_component: str | None = None
    only_side: str | None = None
    filled_joints: list[str] = field(default_factory=list)
    env_name: str | None = None


def _differs(a: float, b: float) -> bool:
    """True nếu 2 giá trị khác nhau vượt dung sai tách MAX/MIN."""
    return abs(a - b) > SPLIT_TOL_REL * max(1.0, abs(a), abs(b))


def _step_key(r: Reaction) -> tuple[str, float]:
    return (r.step_type or "", float(r.step_num))


def _group_by_output(rows: list[Reaction]) -> dict[str, list[Reaction]]:
    grouped: dict[str, list[Reaction]] = defaultdict(list)
    for r in rows:
        grouped[r.output_name].append(r)
    return grouped


def _pick_typed_row(steps: dict[tuple[str, float], Reaction],
                    want: str) -> Reaction | None:
    """Dòng có StepType == want (không phân biệt hoa/thường), StepNum lớn nhất.

    Hòa StepNum thì lấy dòng gặp trước (giữ thứ tự chèn của dict).
    """
    best: Reaction | None = None
    best_num: float | None = None
    for key, r in steps.items():
        if key[0].strip().lower() != want:
            continue
        if best is None or key[1] > best_num:  # type: ignore[operator]
            best, best_num = r, key[1]
    return best


def _last_step_row(steps: dict[tuple[str, float], Reaction]) -> Reaction | None:
    """Dòng có StepNum lớn nhất (hòa thì lấy dòng gặp trước)."""
    best: Reaction | None = None
    best_num: float | None = None
    for key, r in steps.items():
        if best is None or key[1] > best_num:  # type: ignore[operator]
            best, best_num = r, key[1]
    return best


def _make_load(output_name: str, pattern: str, joint: str,
               x: float, y: float, r: Reaction) -> FrozenLoad:
    return FrozenLoad(
        joint=joint,
        x=x,
        y=y,
        pattern=pattern,
        fx=r.f1,
        fy=r.f2,
        fz=r.f3,
        mx=r.m1,
        my=r.m2,
        mz=r.m3,
        source_step=f"{r.step_type or 'Step'} {r.step_num:g}",
    )


def freeze_reactions(
    rows: list[Reaction],
    mode: str = "last",
    specific: tuple[str, float] | None = None,
    joints: dict[str, tuple[float, float]] | None = None,
) -> tuple[list[FrozenLoad], list[str], dict[str, SplitInfo]]:
    """Đóng băng các dòng Reaction thành FrozenLoad (CHƯA đổi dấu).

    `joints`: dict tên joint -> (x, y); joint không có trong dict sẽ bị bỏ
    qua kèm cảnh báo. Trả về (frozen, warnings, splits) với `splits` là
    dict tên case -> SplitInfo (quy tắc tách MAX/MIN mặc định).
    """
    if mode not in STEP_MODES:
        raise ValueError(f"Step mode không hỗ trợ: {mode!r} (chọn trong {STEP_MODES})")
    joints = joints or {}
    frozen: list[FrozenLoad] = []
    warnings: list[str] = []
    splits: dict[str, SplitInfo] = {}
    grouped = _group_by_output(rows)

    for output_name, out_rows in grouped.items():
        # Gom theo joint -> {step_key: Reaction} (giữ thứ tự xuất hiện).
        by_joint: dict[str, dict[tuple[str, float], Reaction]] = defaultdict(dict)
        for r in out_rows:
            by_joint[r.joint][_step_key(r)] = r

        if mode in ("last", "maxmin"):
            splits[output_name] = _freeze_last_or_maxmin(
                output_name, by_joint, joints, frozen, warnings)
            continue

        splits[output_name] = SplitInfo(output=output_name)
        chosen_step: dict[str, tuple[str, float]] = {}
        if mode == "specific":
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
            frozen.append(_make_load(output_name, output_name, joint, x, y, r))

    return frozen, warnings, splits


def _freeze_last_or_maxmin(
    output_name: str,
    by_joint: dict[str, dict[tuple[str, float], Reaction]],
    joints: dict[str, tuple[float, float]],
    frozen: list[FrozenLoad],
    warnings: list[str],
) -> SplitInfo:
    """Logic "last" + tách MAX/MIN mặc định (mode "maxmin" là alias).

    - Không có dòng Max/Min nào: hành vi "last" cũ (StepNum lớn nhất).
    - Có dòng Max/Min: so sánh 2 vector từng joint; khác nhau -> tách
      _MAX/_MIN (+ cảnh báo không đồng thời); giống nhau -> 1 pattern
      tên gốc từ dòng Max.
    """
    info = SplitInfo(output=output_name)

    # Bước 1: dòng Max/Min/last-step từng joint.
    per_joint: dict[str, tuple[Reaction | None, Reaction | None, Reaction | None]] = {}
    has_maxmin = False
    has_max_any = False
    has_min_any = False
    for joint, steps in by_joint.items():
        max_row = _pick_typed_row(steps, "max")
        min_row = _pick_typed_row(steps, "min")
        last_row = _last_step_row(steps)
        if max_row is not None or min_row is not None:
            has_maxmin = True
        if max_row is not None:
            has_max_any = True
        if min_row is not None:
            has_min_any = True
        per_joint[joint] = (max_row, min_row, last_row)
    info.has_maxmin = has_maxmin
    if has_max_any and not has_min_any:
        info.only_side = "Max"
    elif has_min_any and not has_max_any:
        info.only_side = "Min"

    if not has_maxmin:
        # Hành vi "last" cũ, không tách.
        for joint, steps in by_joint.items():
            if joint not in joints:
                warnings.append(f"{output_name} / {joint}: không có tọa độ, bỏ qua.")
                continue
            r = _last_step_row(steps)
            assert r is not None  # joint có ít nhất 1 dòng
            x, y = joints[joint]
            frozen.append(_make_load(output_name, output_name, joint, x, y, r))
        return info

    # Bước 2: so sánh Max/Min ở các joint có đủ 2 phía.
    split = False
    for joint, (max_row, min_row, _last_row) in per_joint.items():
        if max_row is None or min_row is None:
            continue
        for label, attr in _COMPONENTS:
            a = getattr(max_row, attr)
            b = getattr(min_row, attr)
            if _differs(a, b):
                split = True
                d = abs(a - b)
                if d > info.max_diff:
                    info.max_diff = d
                    info.max_joint = joint
                    info.max_component = label
    info.split = split

    if not split:
        # Giống nhau hết: 1 pattern tên gốc, lấy dòng Max (thiếu Max thì
        # lấy dòng Min, thiếu cả 2 thì lấy step cuối — không warning vì
        # đây vẫn là 1 vector duy nhất, không phải bù phía tách).
        for joint, (max_row, min_row, last_row) in per_joint.items():
            if joint not in joints:
                warnings.append(f"{output_name} / {joint}: không có tọa độ, bỏ qua.")
                continue
            r = max_row if max_row is not None else (
                min_row if min_row is not None else last_row)
            assert r is not None
            x, y = joints[joint]
            frozen.append(_make_load(output_name, output_name, joint, x, y, r))
        return info

    # Bước 3: tách — _MAX trước, _MIN sau. Joint thiếu 1 phía thì lấy phía
    # còn lại bù vào (ghi warning); joint chỉ có dòng Step thì lấy step
    # cuối bù cho cả 2 phía (ghi warning).
    warnings.append(
        f"{output_name}: tách MAX/MIN — Max khác Min (chênh lệch lớn nhất "
        f"{info.max_diff:g} ở {info.max_component}, joint {info.max_joint}); "
        "vector _MAX/_MIN là các dòng envelope do SAP báo cáo, có thể "
        "không đồng thời."
    )
    for suffix, want, other in (("_MAX", "max", "Min"), ("_MIN", "min", "Max")):
        for joint, (max_row, min_row, last_row) in per_joint.items():
            if joint not in joints:
                warnings.append(f"{output_name} / {joint}: không có tọa độ, bỏ qua.")
                continue
            own = max_row if want == "max" else min_row
            alt = min_row if want == "max" else max_row
            if own is not None:
                r = own
            elif alt is not None:
                r = alt
                info.filled_joints.append(joint)
                warnings.append(
                    f"{output_name} / {joint}: thiếu dòng {want.capitalize()} — "
                    f"dùng dòng {other} bù vào khi tách MAX/MIN."
                )
            else:
                r = last_row
                assert r is not None
                info.filled_joints.append(joint)
                warnings.append(
                    f"{output_name} / {joint}: không có dòng Max/Min — dùng "
                    "step cuối bù vào khi tách MAX/MIN."
                )
            x, y = joints[joint]
            frozen.append(_make_load(
                output_name, output_name + suffix, joint, x, y, r))
    return info
