"""Map output SAP -> pattern/case/combo SAFE + đổi dấu phản lực -> tải SAFE.

Quy tắc đã chốt với user (HIỆU CHỈNH theo file MONG.sf thật 07/11):
- Tải SAFE = -phản lực SAP trên cả 6 thành phần (checkbox mặc định BẬT).
- Tên KHÔNG sanitize kiểu cũ nữa: MONG.sf giữ nguyên `WX1+`, `WY1-`,
  `ENV SLS` (dấu +, -, khoảng trắng đều hợp lệ vì value có khoảng trắng
  được quote trong file .sf). Chỉ bỏ dấu `=` (phá cú pháp Key=Value).
- Combo được COPY Y HỆT định nghĩa từ SAP (Linear Add lẫn Envelope,
  kể cả combo chứa case nonlinear): SAFE tự tính combo từ các case đã
  đóng băng (cộng tuyến tính) — ghi cảnh báo trong .LOG. Chỉ khi thành
  phần combo không rõ (không có trong model) mới fallback standalone.
- SelfWtMult lấy từ SAP (SW=1, còn lại 0) — KHÔNG ép tất cả về 0 nữa.
"""

from __future__ import annotations

import re

from .model import FrozenLoad, SapOutput

MAX_SAFE_NAME_LEN = 64


def sanitize_name(name: str, max_len: int = MAX_SAFE_NAME_LEN) -> str:
    """Làm sạch tên tối thiểu để dùng trong file .sf.

    MONG.sf giữ nguyên `WX1+`, `WY1-`, `ENV SLS` nên chỉ loại dấu `=`
    (phá cú pháp Key=Value) và ký tự xuống dòng. Khoảng trắng được giữ
    vì writer sẽ quote value có khoảng trắng.
    """
    cleaned = (name or "").strip().replace("=", "_")
    cleaned = re.sub(r"[\r\n]+", " ", cleaned).strip()
    if not cleaned:
        cleaned = "LOAD"
    return cleaned[:max_len] or "LOAD"


def build_name_map(outputs: list[SapOutput]) -> dict[str, str]:
    """Map tên gốc SAP -> tên SAFE đã sanitize, duy nhất (trùng thì _2, _3...)."""
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for out in outputs:
        base = sanitize_name(out.name)
        candidate = base
        i = 2
        while candidate in used:
            suffix = f"_{i}"
            candidate = (base[: MAX_SAFE_NAME_LEN - len(suffix)] + suffix).rstrip("_")
            i += 1
        used.add(candidate)
        mapping[out.name] = candidate
    return mapping


def decide_combo_mapping(
    output: SapOutput, outputs_by_name: dict[str, SapOutput]
) -> tuple[str, list[tuple[str, float]], str]:
    """Trả về (chế độ, items, ghi chú).

    Chế độ "rebuild": copy y hệt định nghĩa combo từ SAP (Linear Add lẫn
    Envelope, kể cả combo chứa case nonlinear — SAFE tự tính combo từ các
    case đã đóng băng). Chế độ "standalone": chỉ khi thành phần combo
    không có trong model (phòng thủ) — combo gồm 1.0 x chính nó.
    """
    if output.kind == "case":
        return "standalone", [(output.name, 1.0)], "case đơn — frozen"
    for comp_name, _sf in output.components:
        if comp_name not in outputs_by_name:
            return (
                "standalone",
                [(output.name, 1.0)],
                f"combo chứa {comp_name} không có trong model — frozen để an toàn",
            )
    has_nonlinear = any(
        outputs_by_name[c].is_nonlinear for c, _s in output.components
        if outputs_by_name[c].kind == "case"
    )
    note = "copy y hệt định nghĩa SAP — SAFE tự tính từ case đã đóng băng"
    if has_nonlinear:
        note += " (CẢNH BÁO: combo chứa case nonlinear — SAFE cộng tuyến tính các vector đã đóng băng, không phải chạy lại phi tuyến)"
    return "rebuild", list(output.components), note


def apply_sign_flip(loads: list[FrozenLoad], flip: bool = True) -> list[FrozenLoad]:
    """Đổi dấu phản lực SAP -> tải SAFE (mặc định bật). Trả về list mới."""
    if not flip:
        return list(loads)
    flipped: list[FrozenLoad] = []
    for ld in loads:
        flipped.append(
            FrozenLoad(
                joint=ld.joint,
                x=ld.x,
                y=ld.y,
                pattern=ld.pattern,
                fx=-ld.fx,
                fy=-ld.fy,
                fz=-ld.fz,
                mx=-ld.mx,
                my=-ld.my,
                mz=-ld.mz,
                source_step=ld.source_step,
            )
        )
    return flipped
