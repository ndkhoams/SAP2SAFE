# Hướng dẫn test SAP2SAFE v0.1 — kiểm chứng lần đầu trên máy thật

## 0. Thử nhanh không cần SAP (5 phút, trên máy nào cũng được)

```bash
pip install -r requirements.txt
python -m pytest tests/ -q   # 39 test pass (gồm test trên file thật)
python main.py
```

Trong app: chọn chế độ Excel offline → chọn file
`examples/mau_joint_reactions.xlsx` → "Đọc model" → Z = 0 → "Liệt kê
joint tại Z" (phải ra 4 joint) → tick SW, SDL, WX1+ → "Xem preview"
(ΣFZ SW = −420 kN, SDL = −210 kN) → "Xuất .F2K + .sf". Kiểm tra 4 file
`.f2k` / `.sf` / `.xlsx` / `.log` trong thư mục xuất.

## 1. TEST VÀNG — chạy app trên file LINEAR rồi so với MONG.sf

Đây là test quan trọng nhất, làm trên máy Windows có SAP2000:

1. Mở file SAP **linear** (`1.NHA CAT KHO NPL TCVN - linear.sdb`) trong
   SAP2000 (đã chạy phân tích xong).
2. Trong app: "Kết nối SAP đang mở" → "Đọc model" → Z gợi ý `-1.5` →
   "Liệt kê joint tại Z" (phải ra **92 joint**) → tick **cả 15 case**
   (SW, SDL, COL, SOL, Lr, WX1±, WX2±, WY1±, WY2±, EX, EY) + các combo
   (ULS_1..36, SLS_1..26, Wind_*, ENV ULS, ENV SLS) → Last step → xuất.
3. Trong app: nút **"So sánh với file SAFE mẫu..."** → chọn file
   `MONG.sf`. Validator báo:
   - Joint load: xuất **1380**, mẫu 1380; khóa chung 1380.
   - Lệch tuyệt đối FX..MZ: max ≈ 0 (dung sai 0.01) → **KHỚP**.
   - ΣFZ từng pattern khớp bảng tham chiếu (SW −3963.847, SDL −865.919,
     COL/SOL −1803.994, Lr −2164.796, EX 0.002, EY 0.000,
     WX1± +4283.84, WX2± +2254.95, WY1± +4022.64, WY2± −1504.17 kN).
4. Nếu lệch: validator chỉ BÁO SỐ LỆCH, không tự sửa. Gửi lại báo cáo
   validator (kèm file .log) để xem lệch ở pattern/joint nào — có thể
   MONG.sf được tạo từ model hơi khác (tên model trong MONG.sf là
   "1 fdt_V2016"), khi đó lệch là thông tin, không phải lỗi writer.

## 2. TEST PHI TUYẾN — chạy file NONLINEAR, đối chiếu ΣFZ

1. Mở file SAP **nonlinear** trong SAP2000, làm đúng các bước như mục 1.
2. So sánh ΣFZ từng pattern trong file `.log` mới với bảng tham chiếu
   mục 1: chênh lệch chính là **mức chênh do phi tuyến** (kỳ vọng: các
   case gió/động đất chênh nhiều hơn case tĩnh đứng). Ghi lại bảng chênh
   để quyết định có chấp nhận "đóng băng" cho combo phi tuyến không.
3. Kiểm tra trong file `.sf` mới: combo ULS_1 vẫn là
   `1.1*SW + 1.2*SDL + 1.2*COL + 1.2*SOL` (copy y hệt, kể cả khi các case
   thành phần là NonStatic).

## 3. Checklist import file xuất vào SAFE (lần đầu — bắt buộc)

1. Mở SAFE → File > Import > SAFE .f2k → chọn file `.f2k` vừa xuất
   (hoặc mở thẳng file `.sf`).
2. Nếu SAFE báo lỗi cú pháp: DỪNG, lưu lại thông báo lỗi + dòng lỗi trong
   file để sửa writer theo đúng dòng đó.
3. Nếu import được, kiểm tra:
   - [ ] Số point = 92 (số joint tại Z trong SAP), UniqueName trùng ID SAP.
   - [ ] Load pattern: 15 gốc + 15 `_ABOVE`; case: 15 (mỗi case 2 dòng);
         combo đủ như đã chọn (72 combo nếu chọn hết).
   - [ ] Đối chiếu **3–5 joint ngẫu nhiên**: Display > Load Assigns >
         Joint Loads, so FX/FY/FZ/MX/MY/MZ với bảng preview trong app.
   - [ ] ΣFZ từng pattern trong SAFE khớp dòng ΣFZ trong file `.log`.
   - [ ] SelfWtMult: SW = 1, còn lại 0.
   - [ ] Pattern `_ABOVE` không có joint load nào.
   - [ ] File xuất không có sàn — import vào model SAFE đã có sẵn móng/sàn.

## 4. Kiểm dấu (quan trọng nhất, 5 phút, làm 1 lần)

Lấy 1 cột chịu nén rõ ràng (vd SW, point 1): tải SAFE phải là
FX=0.415, FY=−130.833, **FZ=−200.347** (âm = ép xuống móng).
- Nếu đúng → quy tắc đổi dấu của app đã đúng.
- Nếu FZ > 0 → TẮT checkbox "Đổi dấu" trong app, xuất lại, và báo lại
  để sửa mặc định thành không đổi dấu.

## 5. Test chế độ COM với model SAP thật (nếu gặp lỗi COM)

1. Mở SAP2000 v26 (model đã chạy phân tích xong, có case Nonlinear
   Static, Results Saved = Final State Only).
2. Trong app: "Kết nối SAP đang mở" → "Đọc model" → chọn Z → "Liệt kê
   joint tại Z" → tick 1 case nonlinear + 1 combo → Last step → xuất.
3. Đối chiếu phản lực trong SAP (Display > Show Tables > Joint
   Reactions) với tải trong SAFE tại cùng joint/case.
4. Nếu tên hàm COM báo lỗi: ghi lại thông báo lỗi (kèm version SAP) —
   tên hàm trong `sap_reader.py` cần đối chiếu file `.chm` trong thư mục
   cài SAP (`C:\Program Files\Computers and Structures\SAP2000 <version>\`).
   Riêng `LoadPattern.GetSelfWtMult` chưa xác minh bằng CHM — nếu COM
   không có hàm này, app mặc định SelfWtMult=0 và ghi chú trong log.

## 6. Lưu ý về tên và combo

- Tên giữ nguyên như SAP: `WX1+`, `WY1-`, `ENV SLS` đều hợp lệ trong
  file .sf (value có khoảng trắng được quote). Trùng tên → `_2`, `_3`.
- Combo Envelope (ENV ULS/SLS) được copy y hệt vào SAFE; SAFE tự tính
  envelope từ các case đã đóng băng.
- Combo Envelope / Response Spectrum ở chế độ tách MAX-MIN: vector đó
  KHÔNG đồng thời, chỉ dùng khi bạn chấp nhận (xem cảnh báo trong app
  và file `.log`).
