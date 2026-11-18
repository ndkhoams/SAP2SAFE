# SAP2SAFE v0.1 — chuyển 1 level SAP2000 sang SAFE (.F2K/.sf)

App Windows (Python + Tkinter) chuyển phản lực tại 1 cao độ Z của SAP2000
thành tải điểm trong SAFE, đủ load pattern / load case / load combo — kể cả
load case **Nonlinear Static** mà tool mặc định không chuyển được.

## Vì sao cần app này

- **SAP2000 KHÔNG có nút Export to SAFE** (đó là tính năng của ETABS).
- Exporter mặc định dựa trên cộng dồn tuyến tính (superposition). Case phi
  tuyến có nhiều step, giá trị lớn nhất từng thành phần rơi ở các step khác
  nhau, không đồng thời — không gộp thành 1 vector được.
- Cách làm của app: **"đóng băng"** vector phản lực đã tính xong ở 1 step do
  bạn chọn thành tải điểm trong SAFE (tải SAFE = −phản lực SAP). Combo được
  copy y hệt định nghĩa từ SAP; SAFE tự tính combo từ các case đã đóng băng.

## File mẫu vàng (không đoán format nữa)

Writer viết theo đúng cú pháp file **MONG.sf thật** (SAFE 22.5.1) và file
**.$2k thật** (SAP2000 26.3.0, model "NHA CAT KHO NPL TCVN"):
cú pháp `TABLE:  "TÊN BẢNG"` + dòng `Key=Value` (3 khoảng trắng phân cách),
GUID uuid4 mỗi dòng cần GUID, số dạng repr ngắn (`0.415`, `1.41E-05`).

File xuất chỉ gồm 7 bảng — đúng như MONG.sf, **không tự sinh slab/bbox/
area/spring**: `PROGRAM CONTROL`, `LOAD PATTERN DEFINITIONS`,
`LOAD CASE DEFINITIONS - LINEAR STATIC`, `LOAD COMBINATION DEFINITIONS`,
`POINT OBJECT CONNECTIVITY`, `JOINT ASSIGNMENTS - RESTRAINTS`,
`JOINT LOADS ASSIGNMENTS - FORCE`. Import file xuất vào model SAFE đã có sẵn
(hoặc mở như model mới chỉ gồm points + loads).

## Cài đặt (Windows)

```bat
pip install -r requirements.txt
python main.py
```

Build file .exe độc lập:

```bat
python build_exe.py
rem -> dist\SAP2SAFE.exe
```

## Ba chế độ nguồn

1. **COM (cần SAP2000 đang mở hoặc file .sdb)** — đọc qua SAP OAPI
   (`CSI.SAP2000.API.SapObject`, helper `SAP2000v1.Helper`, không hardcode
   version SAP). Đọc case/combo, tọa độ joint, gối từng DOF.
2. **File .$2k (offline)** — đọc định nghĩa model (pattern/case/combo/
   joint/Z/gối) mà không cần mở SAP. Phản lực vẫn cần COM hoặc Excel.
   App gợi ý Z = cao độ có nhiều joint có gối nhất (vd Z=-1.5: 92 joint).
3. **Excel offline (không cần SAP)** — đọc file Excel Joint Reactions
   export từ SAP (Display > Show Tables). Thử ngay bằng file mẫu
   `examples/mau_joint_reactions.xlsx`.

## Luồng 5 bước trong app

1. **Nguồn SAP** — kết nối SAP / mở .sdb / chọn .$2k / chọn file Excel,
   rồi "Đọc model".
2. **Chọn level** — chọn cao độ Z trong combobox (mặc định gợi ý Z của các
   joint có gối) hoặc nhập tay + tol (mặc định 0.005 m), "Liệt kê joint
   tại Z". Lấy TẤT CẢ joint object tại Z (loại joint mesh `~*`), kể cả
   chân vách/dầm — mỗi joint 1 điểm riêng, KHÔNG gộp. UniqueName trong
   SAFE giữ nguyên ID joint SAP, Z=0 trong SAFE (đổi gốc cao độ).
3. **Chọn output + step** — tick case/combo (combo được chọn sẽ tự động
   gồm cả các case thành phần để đóng băng); step mode: Last step (mặc
   định cho Nonlinear Static/Staged), Step cụ thể, Governing step
   (max |F3|), hoặc tách MAX-MIN (chỉ Envelope/RS). Checkbox đổi dấu
   mặc định BẬT.
4. **Tham số xuất** — version SAFE (mặc định 22.5.1, theo MONG.sf),
   thư mục xuất.
5. **Preview + xuất** — bảng preview + ΣFZ từng pattern; nút xuất sinh 4 file:
   `.f2k` + `.sf` (cùng nội dung), `.xlsx` (bảng SAFE-tables dự phòng),
   `.log` (nguồn từng pattern + tổng kiểm tra ΣFZ = −ΣF3). Nút
   "So sánh với file SAFE mẫu..." chạy validator so với MONG.sf.

## Quy tắc đã chốt (theo file thật)

- Nội bộ làm việc bằng **kN, m**. `SelfWtMult` lấy từ SAP (SW=1, còn lại 0):
  tải SW trong SAFE là tải điểm đã đóng băng; tự trọng sàn SAFE (nếu có)
  tính riêng.
- Mỗi case SAFE gồm pattern gốc + pattern `<tên>_ABOVE` (SF=1); chỉ
  pattern gốc có joint load, `_ABOVE` có 0 dòng load.
- Combo copy y hệt định nghĩa SAP (Linear Add lẫn Envelope, kể cả combo
  chứa case nonlinear). CẢNH BÁO: combo chứa case nonlinear thì SAFE cộng
  tuyến tính các vector đã đóng băng, không phải chạy lại phi tuyến.
- Tên giữ nguyên như SAP (`WX1+`, `WY1-`, `ENV SLS`) — chỉ bỏ dấu `=`;
  trùng tên → `_2`, `_3`...
- Gối lấy đúng từng DOF (UX/UY/UZ/RX/RY/RZ) từ SAP; chế độ Excel không có
  thông tin gối → mặc định Yes cả 6 DOF, ghi cảnh báo trong log.

## Test (Linux)

```bash
python -m pytest tests/ -q   # 39 test, gồm test trên file $2k + MONG.sf thật
python main.py --help
python -c "import sap2safe"
```

Test COM trên Windows được skip với lý do rõ ràng (COM chỉ có trên Windows).
Test fixture thật nằm ở `~/workspace/sap2safe_work/fixtures/` (không copy
vào repo): 15 pattern, 15 case, **72 combo** (36 ULS + 26 SLS + 8 Wind +
2 ENV), 92 joint có gối ở Z=-1.5, ΣFZ tham chiếu trong `sf_reader.py`.

## Plugin chạy trong SAP2000 v26 (C#, `plugin/`)

Bản plugin C# chạy in-process trong SAP2000 v26 (Tools > Add/Show Plugins),
đọc trực tiếp model đang mở qua CSiAPIv1 — không qua COM ngoài, không cần
file trung gian. Logic tính toán port 1-1 từ app Python sang thư viện
`Sap2Safe.Core` (netstandard2.0); parity với Python đã kiểm chứng 100%
trên fixture MONG.sf (2035/2035 dòng sau chuẩn hoá GUID + header, 1380 dòng
JOINT LOADS, ΣFZ khớp 15/15 pattern).

```bash
~/.dotnet/dotnet build -c Release plugin/Sap2Safe.sln   # 0 lỗi / 0 cảnh báo (Linux, chỉ biên dịch)
~/.dotnet/dotnet run -c Release --project plugin/Sap2Safe.ParityTest/   # parity C# vs Python
```

Chi tiết: `plugin/README.md`; checklist test trên Windows + SAP thật:
`plugin/HUONG_DAN_TEST_PLUGIN.md`. **Chưa kiểm chứng:** chạy thật trong
SAP2000 v26, import `.F2K` vào SAFE, ánh xạ int loại combo (DLL không có
enum loại combo — xem `plugin/Sap2Safe.Plugin/API_DUMP.md`).
