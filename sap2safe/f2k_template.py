"""So sánh file .F2K/.sf mẫu thật với các bảng writer sinh ra.

Dùng sf_reader (parser cú pháp CSI thật) thay cho parser đoán mò cũ.
"""

from __future__ import annotations

from .sf_reader import parse_sf
from .sf_writer import EXPECTED_TABLES


def parse_f2k(path: str) -> dict[str, list[dict]]:
    """Parse file .sf/.F2K mẫu -> {tên_bảng: [dict dòng, ...]}."""
    return parse_sf(path)


def compare_with_writer(sample_path: str) -> str:
    """So sánh file mẫu với các bảng writer sinh ra. Trả về báo cáo text."""
    sample = parse_sf(sample_path)
    lines = [f"So sánh file mẫu: {sample_path}", ""]
    lines.append(f"File mẫu có {len(sample)} TABLE block:")
    for name, rows in sample.items():
        lines.append(f'  - "{name}": {len(rows)} dòng')
    lines.append("")
    lines.append("Đối chiếu với các bảng writer sinh ra:")
    for expected in EXPECTED_TABLES:
        if expected in sample:
            lines.append(f"  [KHỚP] {expected}")
        else:
            lines.append(f"  [THIẾU trong mẫu] {expected} — mẫu không có block này")
    extra = [n for n in sample if n not in EXPECTED_TABLES]
    if extra:
        lines.append("")
        lines.append("Block có trong mẫu nhưng writer KHÔNG sinh (đúng thiết kế v0.1 —")
        lines.append("chỉ xuất points + restraints + loads, không sinh sàn/vật liệu):")
        for name in extra:
            lines.append(f"  [KHÔNG XUẤT] {name}")
    else:
        lines.append("")
        lines.append("Mẫu không có block nào ngoài các bảng writer đã sinh.")
    return "\n".join(lines)
