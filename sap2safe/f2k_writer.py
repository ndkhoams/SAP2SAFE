"""Alias giữ tương thích: .F2K và .sf dùng chung cú pháp TABLE của CSI.

Writer thật nằm ở sf_writer.py (cú pháp đọc từ file MONG.sf thật).
Module này chỉ re-export để code cũ (import f2k_writer) vẫn chạy.
"""

from .sf_writer import EXPECTED_TABLES, build_lines, write_f2k, write_sf

__all__ = ["EXPECTED_TABLES", "build_lines", "write_f2k", "write_sf"]
