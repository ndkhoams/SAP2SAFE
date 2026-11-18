# Hướng dẫn test plugin SAP2SAFE trong SAP2000 v26 (Windows)

Plugin chạy in-process trong SAP2000, KHÔNG chạy được trên Linux — các bước dưới đây
chỉ làm được trên máy Windows có SAP2000 v26.

## 1. Cài đặt

1. Build Release trên máy Windows (hoặc copy bản build từ Linux):
   `dotnet build -c Release` trong `~/workspace/sap2safe/plugin/` (file `Sap2Safe.sln`).
   Trên máy Windows có SAP, `CSiApiDll` tự trỏ tới
   `C:\Program Files\Computers and Structures\SAP2000 26\CSiAPIv1.dll`.
2. Copy 2 file vào thư mục plugin của SAP (cùng 1 thư mục):
   - `Sap2Safe.Plugin.dll`
   - `Sap2Safe.Core.dll`
   - (không cần `CSiAPIv1.dll` — SAP đã có; không cần `version.txt`, chỉ để đối chiếu)
3. Mở SAP2000 v26 → menu plugin (Tools / SAP2SAFE) → bấm mục SAP2SAFE.
   Form phải hiện NON-MODAL (vẫn bấm được vào model SAP phía dưới). Nếu SAP treo
   cứng khi mở form → báo ngay (nghi modal).

## 2. Kiểm tra trước khi test số

- [ ] Title bar form có `(build yyyyMMdd-HHmmss)` khớp nội dung `version.txt`
      trong thư mục build (chống stale-build: build mới → timestamp mới).
- [ ] Mục 1 hiện đúng tên file .sdb, đơn vị hiện tại, số pattern/case/combo/joint.
- [ ] Combobox Z liệt kê đủ cao độ; Z gợi ý = cao độ có nhiều joint có gối nhất.
- [ ] ListBox Cases/Combos đủ tên; combo Envelope (nếu có) hiện đúng `[Envelope]`
      trong ngoặc — **điểm này xác minh ánh xạ int -> tên loại combo** (xem API_DUMP.md
      mục 1: DLL không có enum loại combo, ánh xạ theo tài liệu CSI OAPI, chưa xác
      minh bằng runtime). Kiểm tra cả combo Linear Add / SRSS / Absolute Add nếu có.
- [ ] Đóng form bằng nút X và bằng nút Đóng — SAP không báo lỗi plugin, mở lại
      plugin vẫn chạy (Finish gọi đúng 1 lần).

## 3. Test luồng chính (model nhỏ, đã chạy phân tích)

1. Chọn Z (mặc định gợi ý) → **Liệt kê joint tại Z** → label hiện số joint + số joint
   có gối + số dòng phản lực đã đọc.
2. Chọn 1–2 case (kể cả 1 case Nonlinear Static nếu có) + 1 combo → step mode `last`
   → **Xem preview**: grid hiện đủ cột Joint/X/Y/Pattern/FX..MZ; label ΣFZ theo pattern.
3. **Xuất .F2K + .sf (+ .log)** → 3 file `SAP2SAFE_Z{z}.f2k/.sf/.log` trong thư mục xuất.
4. Mở file `.log`: mục "Tong kiem tra" phải KHOP hết mọi pattern
   (ΣFZ SAFE = -ΣF3 SAP); có LECH thì không import.
5. Import file `.f2k` (hoặc `.sf`) vào model SAFE đã có sẵn → so số point/pattern/
   load với file `.log` (counts).
6. So sánh 1 case với app Python: cùng model, cùng Z, cùng case, step `last` —
   số trong grid preview phải khớp file Excel/Python đã xuất trước đó.

## 4. Test các step mode

- `specific` (StepType `Step`, StepNum `1`): preview chỉ lấy đúng step đó; nhập
  StepNum chữ → phải báo lỗi tiếng Việt, không lặng lẽ dùng mặc định.
- `governing`: log/preview ghi governing step theo max |F3|.
- `maxmin` (chỉ combo Envelope/RS): mỗi pattern tách `_MAX`/`_MIN`; log cảnh báo
  vector không đồng thời.
- Bỏ tick "Đổi dấu phản lực": ΣFZ đổi dấu so với lúc tick.

## 5. Test lỗi (không được crash SAP)

- Model chưa chạy phân tích (Run Analysis) → bấm Liệt kê joint: phải báo lỗi
  "chưa chạy phân tích..." bằng MessageBox, SAP vẫn sống, form vẫn đóng được.
- Nhập Z chữ / tol âm / StepNum chữ → MessageBox tiếng Việt, không crash.
- Đổi Z sau khi liệt kê joint rồi bấm Preview → phải yêu cầu liệt kê lại.
- Sau khi đọc phản lực xong: kiểm tra trong SAP (Display → Show Tables /
  Results Setup) rằng lựa chọn case/combo để xuất kết quả đã được TRẢ LẠI như
  trước khi bấm (SapStateGuard restore).

## 6. Những điểm chỉ xác minh được trên máy thật (chưa xác minh trên Linux)

- `GetNameList` có lọc `eLoadCaseType` có trả đúng loại case không.
- `JointReact("", ObjectElm)` có trả tất cả joint không; tên LoadCase trả về trong
  mảng có đúng tên case không.
- Ánh xạ int loại combo (0 Linear Add / 1 Envelope / 2 Absolute Add / 3 SRSS /
  4 Range Add) — xem mục 2.
- `GetCoordCartesian(..., "Global")` có nhận chuỗi `"Global"` làm hệ tọa độ không.
- Form WinForms hiển thị đúng trên màn hình thật (layout 5 groupbox, không tràn/cắt).
- File `.f2k` import vào SAFE 22.5.1 không lỗi, đủ 7 bảng.
