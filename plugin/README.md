# SAP2SAFE — Plugin chạy TRONG SAP2000 v26 (C#)

Bản plugin C# của app SAP2SAFE (Python + Tkinter): chạy in-process trong
SAP2000 v26, đọc trực tiếp model đang mở qua CSiAPIv1 (không qua COM
ngoài, không cần file trung gian) rồi xuất `.F2K` + `.sf` + `.log` như
app Python. Logic tính toán dùng chung một Core duy nhất, đã kiểm chứng
parity 100% với Python trên fixture thật (xem dưới).

## Cấu trúc

```
plugin/
├── Sap2Safe.sln                  # Core + Plugin + ParityTest
├── README.md                     # file này
├── HUONG_DAN_TEST_PLUGIN.md      # checklist test trên Windows + SAP thật
├── Sap2Safe.Core/                # netstandard2.0, KHÔNG phụ thuộc CSiAPIv1
│   ├── Model.cs                  # Joint, Reaction, SapOutput, FrozenLoad, F2kModel...
│   ├── CsiText.cs                # format/parse file text CSI (Key=Value, TABLE:)
│   ├── Mapping.cs                # sanitize tên, map combo, đổi dấu phản lực
│   ├── StepSelect.cs             # đóng băng step: last/specific/governing/maxmin
│   ├── Units.cs                  # eUnits (1..16) -> hệ số kN/m
│   ├── SfWriter.cs               # sinh 7 bảng .sf/.F2K đúng như MONG.sf
│   └── Pipeline.cs               # build_f2k_model (closure combo, pattern/case/combo)
├── Sap2Safe.Plugin/              # net8.0-windows, WinForms, nạp trong SAP
│   ├── cPlugin.cs                # điểm vào SAP: Main non-modal + Finish đúng 1 lần
│   ├── SapReader.cs              # đọc in-process từ cSapModel + SapStateGuard
│   ├── MainForm.cs               # form 5 bước như app Python
│   └── API_DUMP.md               # chữ ký thật dump từ CSiAPIv1.dll v2.7.0.0
└── Sap2Safe.ParityTest/          # console net8.0, kiểm chứng C# vs Python
    ├── Program.cs                # 5 check, exit 0 khi tất cả pass
    ├── python_reference.py       # phía tham chiếu Python, Check 2 (dev tool)
    ├── split_reference.py        # phía tham chiếu Python, Check 5 tách MAX/MIN
    └── README.md
```

## Build (Linux — chỉ kiểm chứng biên dịch)

```bash
~/.dotnet/dotnet build -c Release Sap2Safe.sln   # 0 lỗi / 0 cảnh báo
```

Cần .NET SDK 8 (`~/.dotnet/dotnet`, 8.0.427); gói
`Microsoft.WindowsDesktop.App.Ref` được restore tự động từ NuGet (cần mạng).
`CSiAPIv1.dll` được reference với `<Private>false</Private>` nên KHÔNG copy
vào thư mục output — thư mục output chỉ có `Sap2Safe.Plugin.dll`,
`Sap2Safe.Core.dll`, `version.txt` (+ `.pdb`/`.deps.json`).
Đường dẫn DLL: ưu tiên `C:\Program Files\Computers and Structures\SAP2000 26\CSiAPIv1.dll`
(máy Windows có SAP), fallback bản local trên Linux, override bằng
`-p:CSiApiDll=<đường dẫn>`.

Chống stale-build: mỗi lần build đóng dấu `yyyyMMdd-HHmmss` (giờ UTC+7) vào
`AssemblyMetadata` + file `version.txt` cạnh DLL; title bar form hiện đúng
dấu này. Build không sửa file `.cs` nguồn. Lưu ý: `version.txt` do MSBuild
ghi có BOM UTF-8 ở đầu file — code .NET đọc tự strip BOM, còn Python thì
nhớ trim.

WinForms chỉ biên dịch được trên Linux, KHÔNG chạy được form — xem giới hạn
dưới đây.

## Parity với app Python (đã kiểm chứng trên Linux)

```bash
~/.dotnet/dotnet run -c Release --project Sap2Safe.ParityTest/
python3 -m pytest ~/workspace/sap2safe/tests/ -q   # 49/49 pass
```

Kết quả: **TẤT CẢ PASS** — FormatNumber 18/18 giá trị khớp Python từng chữ
số; round-trip MONG.sf end-to-end khớp **100%** (2035/2035 dòng sau chuẩn hoá
GUID + dòng header ngày giờ; 1380 dòng JOINT LOADS; 92 point, 15 pattern,
72 combo); ΣFZ khớp 15/15 pattern, chênh lệch lớn nhất 0.000000.
Check 5 (tách MAX/MIN mặc định): trên cùng đầu vào MONG.sf với dòng Min của
WX1+ tại joint 1 giảm 10% F3, C# và Python cùng tách đúng 1 pattern WX1+
(max_diff 29.63, F3, joint 1), tạo combo Envelope `WX1+_ENV` đặt trước các
combo gốc, viết lại 8 combo gốc dùng WX1+ (SLS_3, SLS_11, SLS_19, ULS_3,
ULS_11, ULS_19, ULS_27, Wind_WX1+) sang `WX1+_ENV` (giữ nguyên SF);
16 pattern, 16 case, 73 combo, 1472 point load; 2 file xuất khớp byte 100%
(2133 dòng).
Parity mới chỉ kiểm trên một fixture MONG.sf, một pipeline duy nhất
(`step_mode="last"`, `flip_sign=true`, SAFE 22.5.1) — đúng pipeline mà UI
plugin dùng (từ bản 20261118-110700 form chỉ còn Last step, đổi dấu luôn bật).
Mode `maxmin` trong Core nay là alias của logic tách mặc định (như `last`),
đã kiểm parity qua Check 5; các mode `specific`/`governing` vẫn còn trong
Core nhưng không còn trên UI và chưa kiểm parity.

## Tách MAX/MIN mặc định (không có control UI)

Quy tắc user chốt 18/11, áp dụng cho mọi case khi đóng băng ở Last step
(cả app Python và plugin C#, cùng một logic):

- Case có dòng Max/Min do SAP báo cáo: so sánh 2 vector từng joint, đủ 6
  thành phần, dung sai |Max−Min| > 1e-6 × max(1, |Max|, |Min|). Khác nhau ở
  bất kỳ joint/thành phần nào → tách thành `<tên>_MAX` + `<tên>_MIN`
  (Max trước Min sau), tạo thêm combo Envelope `<tên>_ENV`
  (MAX 1.0 + MIN 1.0) đặt TRƯỚC các combo gốc; các combo gốc dùng case đó
  được viết lại sang `_ENV` (giữ nguyên SF). `_ENV` được tạo ngay cả khi
  không combo gốc nào dùng tới case đó; tên `_ENV` trùng thì thêm
  `_2`, `_3`... Max = Min thì giữ 1 pattern tên gốc (lấy dòng Max).
  Case chỉ có dòng Step thì lấy step cuối, không tách. Joint thiếu 1 phía
  khi tách thì lấy phía còn lại bù vào + ghi warning.
- Mỗi case tách/giữ đều ghi 1 dòng vào file `.log` (chênh lệch Max-Min lớn
  nhất + kết luận + danh sách combo gốc đã viết lại). Vector `_MAX`/`_MIN`
  là các dòng envelope do SAP báo cáo, có thể không đồng thời.
- Logic nằm ở `StepSelect.cs` (phân tích tách) + `Pipeline.cs` (combo
  `_ENV` + viết lại combo gốc); phía Python tương ứng là
  `step_select.py` + `app.py:build_f2k_model`.

## Nạp plugin trong SAP2000 v26

Tools > Add/Show Plugins... → Browse tới `Sap2Safe.Plugin.dll` → Add →
chạy từ menu Tools. Cần copy cả 2 DLL (`Sap2Safe.Plugin.dll` +
`Sap2Safe.Core.dll`) vào cùng một thư mục. Chi tiết từng bước test:
xem `HUONG_DAN_TEST_PLUGIN.md`.

## Điểm đã xác minh bằng chữ ký thật (CSiAPIv1.dll v2.7.0.0)

Chi tiết đầy đủ trong `Sap2Safe.Plugin/API_DUMP.md`. Những điểm quan trọng:

- `eItemTypeElm.ObjectElm == 0` — code Python cũ truyền số `1` theo enum cũ
  (trong CSiAPIv1 v2.7 thì `1` = Element); plugin dùng `eItemTypeElm.ObjectElm`,
  tuyệt đối không truyền literal `1`.
- `GetPresentUnits()` trả `eUnits` trực tiếp, mã 1–16 (kết hợp lực+dài).
- `cLoadCases.GetNameList` bắt buộc có tham số lọc `eLoadCaseType` — plugin
  lặp 17 loại rồi gộp, loại trùng.
- `GetSelfWTMultiplier` tồn tại (tên .NET có `WT` hoa).
- `cCombo` KHÔNG có enum loại combo trong DLL — loại combo lấy bằng
  `GetTypeOAPI(name, ref int)`; ánh xạ int→tên (0 Linear Add, 1 Envelope,
  2 Absolute Add, 3 SRSS, 4 Range Add) theo tài liệu CSI OAPI, **chưa xác
  minh bằng runtime** — bắt buộc kiểm trên SAP thật (xem hướng dẫn test).
- Tên thật là `GetTypeOAPI` (Python cũ dùng `GetType`/`RespCombo.GetType`
  không tồn tại); `cAnalysisResultsSetup` có đủ getter để snapshot/restore
  lựa chọn case/combo (`SapStateGuard`).

## Giới hạn — CHƯA kiểm chứng (cần máy Windows + SAP2000 v26 + SAFE)

- Chạy thật trong SAP: form non-modal, đọc model/Z/case/combo,
  `JointReact("", ObjectElm)`, restore lựa chọn Results.Setup, xuất file.
- Ánh xạ int loại combo (mục trên).
- Import `.F2K`/`.sf` vào SAFE 22.5.1 và đối chiếu số với app Python.
- Hiển thị WinForms thực tế (layout 5 groupbox, không tràn/cắt).
