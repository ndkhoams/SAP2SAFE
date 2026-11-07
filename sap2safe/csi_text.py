"""Parser/format dùng chung cho file text của họ CSI (.s2k/.e2k/.f2k/.sf/$2k).

Cú pháp THẬT, đọc từ file MONG.sf (SAFE 22.5.1) và file .$2k SAP2000 26.3.0
(model "NHA CAT KHO NPL TCVN") — không đoán:
- Dòng đầu: `File <đường dẫn> was saved on ...` (bỏ qua khi parse).
- Mỗi block: một dòng trắng (1 khoảng trắng), rồi `TABLE:  "TÊN BẢNG"`,
  rồi mỗi dòng dữ liệu bắt đầu bằng 3 khoảng trắng.
- Mỗi trường dạng `Key=Value`, các trường cách nhau 3 khoảng trắng.
  Key có khoảng trắng thì đặt trong dấu `"..."`; value text có khoảng
  trắng/dấu phẩy thì đặt trong dấu `"..."` (vd `Type="Super Dead"`,
  `Name="ENV SLS"`, `CurrUnits="kN, m, C"`). Value `WX1+` không cần quote.
- Dòng dài dùng ` _` ở cuối + xuống dòng, dòng nối bắt đầu 8 khoảng trắng.
- Số giữ dạng repr ngắn của Python: `0.415`, `-200.347`, `1.41E-05`, `0`.
"""

from __future__ import annotations

import re

TABLE_RE = re.compile(r'^TABLE:\s+"(.*)"\s*$')
# Token Key=Value, quote-aware: Key có thể "quoted" hoặc bare; Value có thể
# "quoted" hoặc tới khoảng trắng. Dùng regex quét từng cặp.
_KV_RE = re.compile(
    r'(?:"([^"]+)"|([A-Za-z0-9_?]+))\s*=\s*'
    r'(?:"((?:[^"\\]|\\.)*)"|([^\s]+))'
)


def join_logical_lines(raw_lines: list[str]) -> list[str]:
    """Nối các dòng bị ngắt bằng ` _` (dòng nối bắt đầu 8 khoảng trắng)."""
    out: list[str] = []
    buf = ""
    for raw in raw_lines:
        line = raw.rstrip("\n")
        if buf:
            buf += line.lstrip()
        else:
            buf = line
        if buf.rstrip().endswith(" _"):
            # " _" là dấu nối dòng: thay bằng đúng 3 khoảng trắng phân cách
            # trường (dòng nối bắt đầu bằng 8 khoảng trắng thụt đầu dòng).
            buf = buf.rstrip()[:-2] + "   "
            continue
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return out


def parse_kv_line(line: str) -> dict[str, str]:
    """Parse 1 dòng dữ liệu `Key=Value   Key2=Value2 ...` thành dict."""
    result: dict[str, str] = {}
    for m in _KV_RE.finditer(line):
        key = m.group(1) if m.group(1) is not None else m.group(2)
        value = m.group(3) if m.group(3) is not None else m.group(4)
        result[key] = value
    return result


def format_number(value) -> str:
    """Format số đúng kiểu CSI: repr ngắn, bỏ '.0', 'e' -> 'E'."""
    if isinstance(value, bool):
        raise TypeError("bool phải format thành Yes/No trước khi ghi")
    if isinstance(value, int):
        return str(value)
    f = float(value)
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    text = f"{f:.10g}"
    return text.replace("e", "E").replace("E+", "E")


def format_key(key: str) -> str:
    """Key có khoảng trắng/ký tự đặc biệt -> đặt trong dấu ngoặc kép."""
    if re.search(r"[\s=]", key):
        return f'"{key}"'
    return key


def format_value(value) -> str:
    """Value text có khoảng trắng/dấu phẩy -> đặt trong dấu ngoặc kép."""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return format_number(value)
    text = str(value)
    if text == "" or re.search(r"[\s,=]", text):
        return f'"{text}"'
    return text


def format_kv_line(fields: list[tuple[str, object]]) -> str:
    """1 dòng dữ liệu: 3 khoảng trắng + các Key=Value cách nhau 3 khoảng."""
    parts = [f"{format_key(k)}={format_value(v)}" for k, v in fields if v is not None]
    return "   " + "   ".join(parts)


def parse_csi_tables(path: str) -> dict[str, list[dict[str, str]]]:
    """Parse file text CSI -> {tên_bảng: [dict dòng, ...]}.

    Bỏ qua dòng đầu `File ... was saved on ...` và các dòng trắng.
    """
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = join_logical_lines(f.readlines())
    tables: dict[str, list[dict[str, str]]] = {}
    current: str | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("File ") and "was saved on" in stripped:
            continue
        m = TABLE_RE.match(stripped)
        if m:
            current = m.group(1)
            tables.setdefault(current, [])
            continue
        if current is None:
            continue
        if line.startswith("   "):
            row = parse_kv_line(stripped)
            if row:
                tables[current].append(row)
    return tables


def write_csi_tables(path: str, header_line: str,
                     tables: list[tuple[str, list[str]]]) -> None:
    """Ghi file text CSI: dòng header, rồi từng block TABLE.

    `tables`: list (tên_bảng, [dòng dữ liệu đã format]).
    """
    out: list[str] = [header_line, " "]
    for name, rows in tables:
        out.append(f'TABLE:  "{name}"')
        out.extend(rows)
        out.append(" ")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
