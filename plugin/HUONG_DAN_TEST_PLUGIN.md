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
- [ ] Nút "Chọn tất cả" / "Bỏ chọn" trên mỗi listbox Cases/Combos chọn/bỏ hết item.
- [ ] Cụm nút Xem preview / Xuất / Đóng nằm TRÊN lưới preview, nhìn thấy ngay
      không cần cuộn (bản cũ nút nằm dưới lưới nên bị che).
- [ ] Đóng form bằng nút X và bằng nút Đóng — SAP không báo lỗi plugin, mở lại
      plugin vẫn chạy (Finish gọi đúng 1 lần).

## 3. Test luồng chính (model nhỏ, đã chạy phân tích)

1. Chọn Z (mặc định gợi ý) → **Liệt kê joint tại Z** → label hiện số joint + số joint
   có gối + số dòng phản lực đã đọc.
2. Chọn 1–2 case (kể cả 1 case Nonlinear Static nếu có) + 1 combo — hoặc bấm
   "Chọn tất cả" ở mỗi listbox để chọn hết → form luôn đóng băng ở Last step
   → **Xem preview**: grid hiện đủ cột Joint/X/Y/Pattern/FX..MZ; label ΣFZ theo pattern.
3. **Xuất .F2K + .sf (+ .log)** → 3 file `SAP2SAFE_Z{z}.f2k/.sf/.log` trong thư mục xuất.
4. Mở file `.log`: mục "Tong kiem tra" phải KHOP hết mọi pattern
   (ΣFZ SAFE = -ΣF3 SAP); có LECH thì không import.
5. Import file `.f2k` (hoặc `.sf`) vào model SAFE đã có sẵn → so số point/pattern/
   load với file `.log` (counts).
6. Nếu có case tách MAX/MIN (xem `.log` mục 4): sau khi import, mở trong SAFE
   Define > Load Combinations kiểm tra combo `<tên>_ENV` loại Envelope
   (2 thành phần `<tên>_MAX` 1.0 + `<tên>_MIN` 1.0) và các combo gốc đã trỏ
   sang `_ENV` thay cho tên case gốc.
7. So sánh 1 case với app Python: cùng model, cùng Z, cùng case, step `last` —
   số trong grid preview phải khớp file Excel/Python đã xuất trước đó.

## 4. Step mode — chỉ còn Last step + tách MAX/MIN mặc định (từ bản build mới nhất)

- Form chỉ còn Last step (label xám "Đóng băng ở Last step" dưới 2 listbox);
  các lựa chọn Step cụ thể / Governing / Tách MAX-MIN đã bỏ khỏi UI theo yêu
  cầu 18/11. Đổi dấu phản lực -> tải SAFE luôn BẬT (không còn checkbox).
- **Tách MAX/MIN là hành vi MẶC ĐỊNH, không có control UI:** với mỗi case,
  plugin so sánh vector Max và Min do SAP báo cáo (từng joint, đủ 6 thành
  phần, dung sai |Max−Min| > 1e-6 × max(1, |Max|, |Min|)):
  - Max = Min ở mọi joint → chỉ xuất 1 pattern, giữ nguyên tên gốc (vd SW).
  - Max ≠ Min ở bất kỳ joint/thành phần nào → case tách thành 2 pattern
    `<tên>_MAX` + `<tên>_MIN` (Max trước Min sau), tạo thêm combo Envelope
    `<tên>_ENV` (MAX 1.0 + MIN 1.0) đặt TRƯỚC các combo gốc; các combo gốc
    dùng case đó được viết lại sang `_ENV` (giữ nguyên SF, vd 1.1·SW →
    1.1·SW_ENV). `_ENV` được tạo ngay cả khi không combo gốc nào dùng tới
    case đó. Tên `_ENV` trùng tên đã có thì thêm `_2`, `_3`...
  - Case chỉ có dòng Step (Linear Static) thì lấy step cuối, không tách.
- Kiểm tra trong file `.log` sau khi xuất: mỗi case có dòng "Tách MAX/MIN
  mặc định: case ..." ghi chênh lệch lớn nhất tìm được + kết luận tách hay
  giữ 1 pattern, và dòng "Combo gốc viết lại sang combo _ENV: ..." liệt kê
  các combo đã viết lại. Trong file `.f2k`/`.sf`: bảng LOAD COMBINATION
  DEFINITIONS phải có combo `<tên>_ENV` loại Envelope đứng trước các combo
  gốc; sau khi import vào SAFE, mở Define > Load Combinations kiểm tra combo
  `<tên>_ENV` (SW_MAX 1.0 + SW_MIN 1.0) có đủ và các combo gốc đã trỏ sang
  `_ENV` thay cho tên case gốc.
- Vector `_MAX`/`_MIN` là các dòng envelope do SAP báo cáo, có thể không
  đồng thời — xem cảnh báo trong form (popup Cảnh báo sau khi Xem preview)
  và file `.log`.

## 5. Test lỗi (không được crash SAP)

- Model chưa chạy phân tích (Run Analysis) → bấm Liệt kê joint: phải báo lỗi
  "chưa chạy phân tích..." bằng MessageBox, SAP vẫn sống, form vẫn đóng được.
- Nhập Z chữ / tol âm → MessageBox tiếng Việt, không crash.
- Đổi Z sau khi liệt kê joint rồi bấm Preview → phải yêu cầu liệt kê lại.
- Sau khi đọc phản lực xong: kiểm tra trong SAP (Display → Show Tables /
  Results Setup) rằng lựa chọn case/combo để xuất kết quả đã được TRẢ LẠI như
  trước khi bấm (SapStateGuard restore).

## 6. Những điểm chỉ xác minh được trên máy thật (chưa xác minh trên Linux)

- `GetNameList` có lọc `eLoadCaseType` có trả đúng loại case không.
- `JointReact` gọi theo từng joint tại Z (đã sửa ở head `3dcdb57` sau khi gọi
  chung `""` trả về 1 trên SAP thật): bấm Liệt kê joint phải đọc được phản lực
  (vd 92 joint × 15 case × 2 dòng Max/Min); nếu chậm bất thường thì báo lại
  (1380 lần gọi API).
- Ánh xạ int loại combo (0 Linear Add / 1 Envelope / 2 Absolute Add / 3 SRSS /
  4 Range Add) — xem mục 2.
- `GetCoordCartesian(..., "Global")` có nhận chuỗi `"Global"` làm hệ tọa độ không.
- Form WinForms hiển thị đúng trên màn hình thật (layout 5 groupbox, không tràn/cắt).
- File `.f2k` import vào SAFE 22.5.1 không lỗi, đủ 7 bảng.
- Tách MAX/MIN mặc định (mục 4): import file có case tách vào SAFE, kiểm tra
  combo `<tên>_ENV` loại Envelope và các combo gốc đã viết lại sang `_ENV`.
