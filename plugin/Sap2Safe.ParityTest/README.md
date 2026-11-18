# Sap2Safe.ParityTest — Kiểm chứng parity C# vs Python (SAP2SAFE)

Console app (.NET 8) kiểm chứng `Sap2Safe.Core` (C#) khớp 100% với bản
Python (`sap2safe/`) trên fixture thật `MONG.sf` (SAFE 22.5.1).
Chỉ đọc Core/Python/fixture — không sửa `sap2safe/*.py`, không sửa Core.

## Cách chạy (1 lệnh duy nhất)

```bash
~/.dotnet/dotnet run -c Release --project ~/workspace/sap2safe/plugin/Sap2Safe.ParityTest/
```

Lệnh này tự build (yêu cầu 0 lỗi / 0 cảnh báo), rồi chạy toàn bộ 5 check
và in kết quả ra console. Exit code 0 = tất cả PASS, khác 0 = có mục FAIL.

Tham số tùy chọn:

```bash
dotnet run -c Release --project ... -- --mong <MONG.sf> --out-dir /tmp/parity \
  --sap-root ~/workspace/sap2safe --python-ref <python_reference.py>
```

Mặc định: fixture `~/workspace/sap2safe_work/fixtures/MONG.sf`,
output `/tmp/parity/` (`cs.f2k`, `py.f2k`), sap-root `~/workspace/sap2safe`.

## Các check

| Check | Nội dung | Kỳ vọng |
|---|---|---|
| 1 — FormatNumber | So `Core.CsiText.FormatNumber` với Python `sap2safe.csi_text.format_number` (`f"{f:.10g}"` + quy tắc số nguyên/-0.0) trên 18 giá trị. Expected lấy **trực tiếp lúc chạy** bằng `python3 -c` (có fallback là giá trị đã lấy từ 1 lần chạy thật trước đó, chỉ dùng khi không gọi được python). Giá trị `5e-324` (min subnormal): lệch chỉ ghi nhận, không tính fail. | 18/18 khớp |
| 2 — Parity end-to-end (**quan trọng nhất**) | Cùng đầu vào suy ra từ MONG.sf (92 point, 15 pattern, 15 case, 72 combo, 1380 reaction; reaction = `-FX..-MZ` vì tải MONG.sf đã là tải SAFE; pipeline `last` / `flip_sign=true` / SAFE `22.5.1`), C# `Pipeline.BuildF2kModel` + `SfWriter.WriteF2k` → `/tmp/parity/cs.f2k`; Python `python_reference.py` (`app.build_f2k_model` + `sf_writer.write_f2k`) → `/tmp/parity/py.f2k`. Console tự gọi script Python rồi so byte sau khi chuẩn hóa GUID (`GUID=...` → `GUID=<GUID>`) và dòng header ngày giờ. Lệch (nếu có): in tối đa 20 dòng đầu kèm số dòng + nội dung 2 phía. | Khớp 100%, 7 bảng đúng thứ tự, 2035 dòng/file, 1380 dòng JOINT LOADS |
| 2-phụ | ΣFZ theo pattern: file C# vs MONG.sf (thông tin, không tính fail). | Lệch max ≤ 0.01 kN |
| 3 — pytest Python | Chạy `python3 -m pytest tests -q` trong `~/workspace/sap2safe` (PYTHONPATH trỏ đúng thư mục đó). | ≥39 pass, 0 fail |
| 4 — Parse MONG.sf (C#) | `CsiText.ParseCsiTables`: đủ 7 bảng expected, JOINT LOADS = 1380, POINT OBJECT CONNECTIVITY = 92 (tổng 41 bảng trong file). | PASS từng mục |
| 5 — Parity tách MAX/MIN | Cùng đầu vào suy ra từ MONG.sf nhưng mỗi dòng JOINT LOADS thành 2 dòng Max/Min (riêng WX1+ tại joint 1: F3 Min = 0.9 × F3 Max để tạo trường hợp tách); C# `Pipeline` → `/tmp/parity/cs_split.f2k`, Python `split_reference.py` → `/tmp/parity/py_split.f2k`, so byte sau chuẩn hoá GUID + header. Kỳ vọng phía C#: chỉ WX1+ tách (max_diff 29.63, F3, joint 1), combo đầu là `WX1+_ENV` loại Envelope (WX1+_MAX 1.0 + WX1+_MIN 1.0), 16 pattern, 16 case, 73 combo, 1472 point load. | Khớp byte 100% (2133 dòng/file) |

## Cách đọc kết quả

- Mỗi check in `PASS`/`FAIL` riêng + số liệu, cuối cùng in bảng `TONG KET`.
- Nếu Check 2 FAIL do lệch số: lỗi ở phía C# (sửa `CsiText.FormatNumber`
  hoặc `SfWriter.BuildTables` cho khớp Python) — **không sửa Python,
  không tự sửa Core trong project này**; báo lại kèm diff cụ thể.

## File trong thư mục này

- `Sap2Safe.ParityTest.csproj` — console net8.0, tham chiếu `../Sap2Safe.Core`.
- `Program.cs` — toàn bộ 5 check + so sánh + gọi Python/pytest qua Process.
- `python_reference.py` — phía tham chiếu Python (dev tool, push kèm):
  xây cùng đầu vào từ MONG.sf rồi ghi file bằng Python writer (Check 2).
- `split_reference.py` — phía tham chiếu Python cho Check 5 (tách MAX/MIN):
  cùng đầu vào MONG.sf nhưng mỗi dòng tải thành 2 dòng Max/Min, WX1+ tại
  joint 1 có F3 Min = 0.9 × F3 Max.
- `README.md` — file này.

Lưu ý: `~/workspace/sap2safe/plugin/` hiện **chưa có file `.sln`**
nên project chưa được thêm vào solution nào (`dotnet sln add` không áp
dụng được); build/chạy trực tiếp bằng đường dẫn `.csproj` như trên.
