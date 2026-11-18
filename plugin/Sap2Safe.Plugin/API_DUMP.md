# API_DUMP — Chữ ký thật từ CSiAPIv1.dll (SAP2000 v26)

Dump bằng reflection (.NET 8, Assembly.LoadFrom + GetMethods/GetProperties) ngày 2026-11-18, từ file local `/home/hatch/workspace/user/files/CSiAPIv1.dll`.

- Assembly: `CSiAPIv1, Version=1.0.0.0, Culture=neutral, PublicKeyToken=8a93c9e72eabf762`
- FileVersion: **2.7.0.0** (khớp mô tả task) — ProductVersion 1.0.0.0
- Tất cả interface đều là `public interface` trong namespace `CSiAPIv1`; mọi hàm trả `System.Int32` (ret, 0 = OK) trừ khi ghi rõ khác.

> Lưu ý: dump này chỉ cho CHỮ KÝ (tên hàm, kiểu tham số). Ngữ nghĩa runtime (vd: `GetNameList` có lọc có trả đúng loại không, `JointReact("", ...)` có nghĩa là tất cả joint không, giá trị int của loại combo) KHÔNG suy ra được từ chữ ký — phải kiểm chứng trên SAP2000 v26 thật (xem HUONG_DAN_TEST_PLUGIN.md).


## cPluginContract

```
===== CSiAPIv1.cPluginContract  (IsInterface=True IsEnum=False IsClass=False) =====
  System.Void Main(ref CSiAPIv1.cSapModel SapModel, ref CSiAPIv1.cPluginCallback ISapPlugin)
  System.Int32 Info(ref System.String Text)

```

## cPluginCallback

```
===== CSiAPIv1.cPluginCallback  (IsInterface=True IsEnum=False IsClass=False) =====
  System.Int32 get_ErrorFlag()
  System.Void Finish(System.Int32 iVal)
  System.Boolean get_Finished()
  PROPERTY System.Int32 ErrorFlag {get=True set=False}
  PROPERTY System.Boolean Finished {get=True set=False}

```

## cSapModel — chỉ các member dùng trong plugin (đầy đủ trong dump thô /tmp/csi-dump/raw.txt)

```
  CSiAPIv1.eUnits GetDatabaseUnits()
  System.String GetModelFilename(System.Boolean IncludePath)
  System.String GetModelFilepath()
  System.Boolean GetModelIsLocked()
  System.String GetPresentCoordSystem()
  CSiAPIv1.eUnits GetPresentUnits()
  System.Int32 GetProgramInfo(ref System.String ProgramName, ref System.String ProgramVersion, ref System.String ProgramLevel)
  System.Int32 GetVersion(ref System.String Version, ref System.Double MyVersionNumber)
  CSiAPIv1.cLoadCases get_LoadCases()
  CSiAPIv1.cLoadPatterns get_LoadPatterns()
  CSiAPIv1.cPointObj get_PointObj()
  CSiAPIv1.cCombo get_RespCombo()
  CSiAPIv1.cAnalysisResults get_Results()
  System.Int32 GetDatabaseUnits_2(ref CSiAPIv1.eForce forceUnits, ref CSiAPIv1.eLength lengthUnits, ref CSiAPIv1.eTemperature temperatureUnits)
  System.Int32 GetPresentUnits_2(ref CSiAPIv1.eForce forceUnits, ref CSiAPIv1.eLength lengthUnits, ref CSiAPIv1.eTemperature temperatureUnits)
```

## cAnalysisResultsSetup

```
===== CSiAPIv1.cAnalysisResultsSetup  (IsInterface=True IsEnum=False IsClass=False) =====
  System.Int32 DeselectAllCasesAndCombosForOutput()
  System.Int32 GetCaseSelectedForOutput(System.String Name, ref System.Boolean Selected)
  System.Int32 GetComboSelectedForOutput(System.String Name, ref System.Boolean Selected)
  System.Int32 GetOptionBaseReactLoc(ref System.Double GX, ref System.Double GY, ref System.Double GZ)
  System.Int32 GetOptionBucklingMode(ref System.Int32 BuckModeStart, ref System.Int32 BuckModeEnd, ref System.Boolean BuckModeAll)
  System.Int32 GetOptionDirectHist(ref System.Int32 Value)
  System.Int32 GetOptionModalHist(ref System.Int32 Value)
  System.Int32 GetOptionModeShape(ref System.Int32 ModeShapeStart, ref System.Int32 ModeShapeEnd, ref System.Boolean ModeShapesAll)
  System.Int32 GetOptionMultiStepStatic(ref System.Int32 Value)
  System.Int32 GetOptionMultiValuedCombo(ref System.Int32 Value)
  System.Int32 GetOptionNLStatic(ref System.Int32 Value)
  System.Int32 SetCaseSelectedForOutput(System.String Name, System.Boolean Selected)
  System.Int32 SetComboSelectedForOutput(System.String Name, System.Boolean Selected)
  System.Int32 SetOptionBaseReactLoc(System.Double GX, System.Double GY, System.Double GZ)
  System.Int32 SetOptionBucklingMode(System.Int32 BuckModeStart, System.Int32 BuckModeEnd, System.Boolean BuckModeAll)
  System.Int32 SetOptionDirectHist(System.Int32 Value)
  System.Int32 SetOptionModalHist(System.Int32 Value)
  System.Int32 SetOptionModeShape(System.Int32 ModeShapeStart, System.Int32 ModeShapeEnd, System.Boolean ModeShapesAll)
  System.Int32 SetOptionMultiStepStatic(System.Int32 Value)
  System.Int32 SetOptionMultiValuedCombo(System.Int32 Value)
  System.Int32 SetOptionNLStatic(System.Int32 Value)
  System.Int32 GetOptionPSD(ref System.Int32 Value)
  System.Int32 GetOptionSteadyState(ref System.Int32 Value, ref System.Int32 SteadyStateOption)
  System.Int32 GetSectionCutSelectedForOutput(System.String Name, ref System.Boolean Selected)
  System.Int32 SelectAllSectionCutsForOutput(System.Boolean Selected)
  System.Int32 SetOptionPSD(System.Int32 Value)
  System.Int32 SetOptionSteadyState(System.Int32 Value, System.Int32 SteadyStateOption)
  System.Int32 SetSectionCutSelectedForOutput(System.String Name, System.Boolean Selected)

```

## cLoadPatterns

```
===== CSiAPIv1.cLoadPatterns  (IsInterface=True IsEnum=False IsClass=False) =====
  System.Int32 Add(System.String Name, CSiAPIv1.eLoadPatternType MyType, System.Double SelfWTMultiplier, System.Boolean AddAnalysisCase)
  CSiAPIv1.cAutoSeismic get_AutoSeismic()
  CSiAPIv1.cAutoWind get_AutoWind()
  System.Int32 ChangeName(System.String Name, System.String NewName)
  System.Int32 Count()
  System.Int32 Delete(System.String Name)
  System.Int32 GetAutoSeismicCode(System.String Name, ref System.String CodeName)
  System.Int32 GetAutoWindCode(System.String Name, ref System.String CodeName)
  System.Int32 GetLoadType(System.String Name, ref CSiAPIv1.eLoadPatternType MyType)
  System.Int32 GetNameList(ref System.Int32 NumberNames, ref System.String[] MyName)
  System.Int32 GetSelfWTMultiplier(System.String Name, ref System.Double SelfWTMultiplier)
  System.Int32 SetLoadType(System.String Name, CSiAPIv1.eLoadPatternType MyType)
  System.Int32 SetSelfWTMultiplier(System.String Name, System.Double SelfWTMultiplier)
  CSiAPIv1.cAutoSeastate get_AutoSeastate()
  System.Int32 GetAutoWaveCode(System.String Name, ref System.String CodeName)
  CSiAPIv1.cAutoWindBridge get_AutoWindBridge()
  PROPERTY CSiAPIv1.cAutoSeismic AutoSeismic {get=True set=False}
  PROPERTY CSiAPIv1.cAutoWind AutoWind {get=True set=False}
  PROPERTY CSiAPIv1.cAutoSeastate AutoSeastate {get=True set=False}
  PROPERTY CSiAPIv1.cAutoWindBridge AutoWindBridge {get=True set=False}

```

## cLoadCases

```
===== CSiAPIv1.cLoadCases  (IsInterface=True IsEnum=False IsClass=False) =====
  CSiAPIv1.cCaseBuckling get_Buckling()
  System.Int32 ChangeName(System.String Name, System.String NewName)
  System.Int32 Count(CSiAPIv1.eLoadCaseType CaseType)
  System.Int32 Delete(System.String Name)
  CSiAPIv1.cCaseDirectHistoryLinear get_DirHistLinear()
  CSiAPIv1.cCaseDirectHistoryNonlinear get_DirHistNonlinear()
  System.Int32 GetNameList(ref System.Int32 NumberNames, ref System.String[] MyName, CSiAPIv1.eLoadCaseType CaseType)
  System.Int32 GetTypeOAPI(System.String Name, ref CSiAPIv1.eLoadCaseType CaseType, ref System.Int32 SubType)
  CSiAPIv1.cCaseHyperStatic get_HyperStatic()
  CSiAPIv1.cCaseModalEigen get_ModalEigen()
  CSiAPIv1.cCaseModalRitz get_ModalRitz()
  CSiAPIv1.cCaseModalHistoryLinear get_ModHistLinear()
  CSiAPIv1.cCaseModalHistoryNonlinear get_ModHistNonlinear()
  CSiAPIv1.cCaseResponseSpectrum get_ResponseSpectrum()
  System.Int32 SetDesignType(System.String Name, System.Int32 DesignTypeOption, CSiAPIv1.eLoadPatternType DesignType)
  CSiAPIv1.cCaseStaticLinear get_StaticLinear()
  CSiAPIv1.cCaseStaticNonlinear get_StaticNonlinear()
  CSiAPIv1.cCaseStaticNonlinearStaged get_StaticNonlinearStaged()
  System.Int32 GetTypeOAPI_1(System.String Name, ref CSiAPIv1.eLoadCaseType CaseType, ref System.Int32 SubType, ref CSiAPIv1.eLoadPatternType DesignType, ref System.Int32 DesignTypeOption, ref System.Int32 Auto)
  CSiAPIv1.cCaseExternalResults get_ExternalResults()
  System.Int32 GetDesignAction(System.String Name, ref System.Int32 DesignActionOption, ref CSiAPIv1.eDesignActionType DesignAction)
  CSiAPIv1.cCaseMovingLoad get_Moving()
  CSiAPIv1.cCasePowerSpectralDensity get_PSD()
  System.Int32 SetDesignAction(System.String Name, System.Int32 DesignActionOption, CSiAPIv1.eDesignActionType DesignAction)
  CSiAPIv1.cCaseStaticLinearMultistep get_StaticLinearMultistep()
  CSiAPIv1.cCaseStaticNonlinearMultistep get_StaticNonlinearMultistep()
  CSiAPIv1.cCaseSteadyState get_SteadyState()
  System.Int32 GetScheduleName(System.String LoadName, ref System.String ScheduleName)
  System.Int32 SetScheduleName(System.String LoadName, System.String ScheduleName)
  System.Int32 GetTypeOAPI_2(System.String Name, ref CSiAPIv1.eLoadCaseType CaseType, ref System.Int32 SubType, ref CSiAPIv1.eLoadPatternType DesignType, ref System.Int32 DesignTypeOption, ref System.Int32 Auto)
  System.Int32 GetNameList_1(ref System.Int32 NumberNames, ref System.String[] MyName, CSiAPIv1.eLoadCaseType CaseType)
  PROPERTY CSiAPIv1.cCaseBuckling Buckling {get=True set=False}
  PROPERTY CSiAPIv1.cCaseDirectHistoryLinear DirHistLinear {get=True set=False}
  PROPERTY CSiAPIv1.cCaseDirectHistoryNonlinear DirHistNonlinear {get=True set=False}
  PROPERTY CSiAPIv1.cCaseHyperStatic HyperStatic {get=True set=False}
  PROPERTY CSiAPIv1.cCaseModalEigen ModalEigen {get=True set=False}
  PROPERTY CSiAPIv1.cCaseModalRitz ModalRitz {get=True set=False}
  PROPERTY CSiAPIv1.cCaseModalHistoryLinear ModHistLinear {get=True set=False}
  PROPERTY CSiAPIv1.cCaseModalHistoryNonlinear ModHistNonlinear {get=True set=False}
  PROPERTY CSiAPIv1.cCaseResponseSpectrum ResponseSpectrum {get=True set=False}
  PROPERTY CSiAPIv1.cCaseStaticLinear StaticLinear {get=True set=False}
  PROPERTY CSiAPIv1.cCaseStaticNonlinear StaticNonlinear {get=True set=False}
  PROPERTY CSiAPIv1.cCaseStaticNonlinearStaged StaticNonlinearStaged {get=True set=False}
  PROPERTY CSiAPIv1.cCaseExternalResults ExternalResults {get=True set=False}
  PROPERTY CSiAPIv1.cCaseMovingLoad Moving {get=True set=False}
  PROPERTY CSiAPIv1.cCasePowerSpectralDensity PSD {get=True set=False}
  PROPERTY CSiAPIv1.cCaseStaticLinearMultistep StaticLinearMultistep {get=True set=False}
  PROPERTY CSiAPIv1.cCaseStaticNonlinearMultistep StaticNonlinearMultistep {get=True set=False}
  PROPERTY CSiAPIv1.cCaseSteadyState SteadyState {get=True set=False}

```

## cCombo

```
===== CSiAPIv1.cCombo  (IsInterface=True IsEnum=False IsClass=False) =====
  System.Int32 Add(System.String Name, System.Int32 ComboType)
  System.Int32 AddDesignDefaultCombos(System.Boolean DesignSteel, System.Boolean DesignConcrete, System.Boolean DesignAluminum, System.Boolean DesignColdFormed)
  System.Int32 Delete(System.String Name)
  System.Int32 DeleteCase(System.String Name, CSiAPIv1.eCNameType CNameType, System.String CName)
  System.Int32 GetCaseList(System.String Name, ref System.Int32 NumberItems, ref CSiAPIv1.eCNameType[] CNameType, ref System.String[] CName, ref System.Double[] SF)
  System.Int32 GetNameList(ref System.Int32 NumberNames, ref System.String[] MyName)
  System.Int32 SetCaseList(System.String Name, ref CSiAPIv1.eCNameType CNameType, System.String CName, System.Double SF)
  System.Int32 GetTypeOAPI(System.String name, ref System.Int32 ComboType)
  System.Int32 GetCaseList_1(System.String Name, ref System.Int32 NumberItems, ref CSiAPIv1.eCNameType[] CNameType, ref System.String[] CName, ref System.Int32[] ModeNumber, ref System.Double[] SF)
  System.Int32 SetCaseList_1(System.String Name, ref CSiAPIv1.eCNameType CNameType, System.String CName, System.Int32 ModeNumber, System.Double SF)
  System.Int32 ChangeName(System.String Name, System.String NewName)
  System.Int32 Count()
  System.Int32 CountCase(System.String Name, ref System.Int32 Count)
  System.Int32 GetDesignType(System.String Name, ref System.Int32 ComboDesignType)
  System.Int32 GetNote(System.String Name, ref System.String Note)
  System.Int32 SetNote(System.String Name, System.String Note)
  System.Int32 SetType(System.String Name, System.Int32 ComboType)
  System.Int32 SetTypeOAPI(System.String Name, System.Int32 ComboType)
  System.Int32 GetTypeCombo(System.String Name, ref System.Int32 ComboType)

```

## cAnalysisResults.JointReact

```
System.Int32 JointReact(System.String Name, CSiAPIv1.eItemTypeElm ItemTypeElm, ref System.Int32 NumberResults, ref System.String[] Obj, ref System.String[] Elm, ref System.String[] LoadCase, ref System.String[] StepType, ref System.Double[] StepNum, ref System.Double[] F1, ref System.Double[] F2, ref System.Double[] F3, ref System.Double[] M1, ref System.Double[] M2, ref System.Double[] M3)
```

## cPointObj — các hàm dùng trong plugin

```
System.Int32 GetCoordCartesian(System.String Name, ref System.Double X, ref System.Double Y, ref System.Double Z, System.String CSys)
System.Int32 GetNameList(ref System.Int32 NumberNames, ref System.String[] MyName)
System.Int32 GetRestraint(System.String Name, ref System.Boolean[] Value)
System.Int32 GetAllPoints(ref System.Int32 NumberNames, ref System.String[] MyName, ref System.Double[] X, ref System.Double[] Y, ref System.Double[] Z, System.String csys)
```

## eUnits

```
===== CSiAPIv1.eUnits  (IsInterface=False IsEnum=True IsClass=False) =====
  lb_in_F = 1
  lb_ft_F = 2
  kip_in_F = 3
  kip_ft_F = 4
  kN_mm_C = 5
  kN_m_C = 6
  kgf_mm_C = 7
  kgf_m_C = 8
  N_mm_C = 9
  N_m_C = 10
  Ton_mm_C = 11
  Ton_m_C = 12
  kN_cm_C = 13
  kgf_cm_C = 14
  N_cm_C = 15
  Ton_cm_C = 16

```

## eLoadCaseType

```
===== CSiAPIv1.eLoadCaseType  (IsInterface=False IsEnum=True IsClass=False) =====
  LinearStatic = 1
  NonlinearStatic = 2
  Modal = 3
  ResponseSpectrum = 4
  LinearHistory = 5
  NonlinearHistory = 6
  LinearDynamic = 7
  NonlinearDynamic = 8
  MovingLoad = 9
  Buckling = 10
  SteadyState = 11
  PowerSpectralDensity = 12
  LinearStaticMultiStep = 13
  HyperStatic = 14
  ExternalResults = 15
  StagedConstruction = 16
  NonlinearStaticMultiStep = 17

```

## eItemTypeElm

```
===== CSiAPIv1.eItemTypeElm  (IsInterface=False IsEnum=True IsClass=False) =====
  ObjectElm = 0
  Element = 1
  GroupElm = 2
  SelectionElm = 3

```

## eLoadPatternType

```
===== CSiAPIv1.eLoadPatternType  (IsInterface=False IsEnum=True IsClass=False) =====
  Dead = 1
  SuperDead = 2
  Live = 3
  ReduceLive = 4
  Quake = 5
  Wind = 6
  Snow = 7
  Other = 8
  Move = 9
  Temperature = 10
  Rooflive = 11
  Notional = 12
  PatternLive = 13
  Wave = 14
  Braking = 15
  Centrifugal = 16
  Friction = 17
  Ice = 18
  WindOnLiveLoad = 19
  HorizontalEarthPressure = 20
  VerticalEarthPressure = 21
  EarthSurcharge = 22
  DownDrag = 23
  VehicleCollision = 24
  VesselCollision = 25
  TemperatureGradient = 26
  Settlement = 27
  Shrinkage = 28
  Creep = 29
  WaterloadPressure = 30
  LiveLoadSurcharge = 31
  LockedInForces = 32
  PedestrianLL = 33
  Prestress = 34
  Hyperstatic = 35
  Bouyancy = 36
  StreamFlow = 37
  Impact = 38
  Construction = 39
  DeadWearing = 40
  DeadWater = 41
  DeadManufacture = 42
  EarthHydrostatic = 43
  PassiveEarthPressure = 44
  ActiveEarthPressure = 45
  PedestrianLLReduced = 46
  SnowHighAltitude = 47
  EuroLm1Char = 48
  EuroLm1Freq = 49
  EuroLm2 = 50
  EuroLm3 = 51
  EuroLm4 = 52
  SeaState = 53
  Permit = 54
  MoveFatigue = 55
  MoveFatiguePermit = 56
  MoveDeflection = 57
  MoveTrain = 58
  PrestressTransfer = 59
  PatternAuto = 60
  QuakeDrift = 61
  QuakeVerticalOnly = 62

```

## eCNameType

```
===== CSiAPIv1.eCNameType  (IsInterface=False IsEnum=True IsClass=False) =====
  LoadCase = 0
  LoadCombo = 1

!!!! KHONG TIM THAY TYPE: CSiAPIv1.cSapObject
```

## ĐIỂM KHÁC SO VỚI MÔ TẢ TRONG TASK / CODE PYTHON CŨ (quan trọng)

1. **cCombo KHÔNG có enum loại combo trong DLL.** Không tồn tại type `eComboType`
   (đã grep toàn bộ assembly). Loại combo lấy bằng `GetTypeOAPI(name, ref int ComboType)`
   (còn có `GetTypeCombo(name, ref int)` — cùng kiểu trả int; plugin dùng `GetTypeOAPI`
   cho nhất quán với `cLoadCases.GetTypeOAPI`). Ánh xạ int -> chuỗi trong `SapReader`
   (0 Linear Add, 1 Envelope, 2 Absolute Add, 3 SRSS, 4 Range Add) lấy theo **tài liệu
   CSI OAPI, KHÔNG xác minh được từ DLL** — bắt buộc kiểm chứng trên SAP thật
   (combo Envelope phải hiện đúng "Envelope" trong form).
2. **Python `RespCombo.GetType(name, 0)` KHÔNG tồn tại trong DLL .NET.** Tên thật là
   `GetTypeOAPI`. Tương tự `LoadCases.GetType` -> `GetTypeOAPI(name, ref eLoadCaseType, ref int SubType)`.
3. **`cLoadCases.GetNameList` BẮT BUỘC có tham số lọc `eLoadCaseType`** — không có
   overload không lọc. Plugin gọi lặp 17 giá trị rồi gộp, loại trùng tên (đúng như task).
   (Có thêm `GetNameList_1` cùng chữ ký — không dùng.)
4. **`eItemTypeElm.ObjectElm == 0` — ĐÃ XÁC MINH (bẫy đúng như task cảnh báo).**
   Python cũ truyền `ITEM_OBJECT_ELM = 1` — giá trị 1 trong enum này là `Element`,
   KHÔNG phải joint object. Plugin dùng `eItemTypeElm.ObjectElm`, tuyệt đối không literal.
5. **`GetSelfWTMultiplier` TỒN TẠI** — `cLoadPatterns.GetSelfWTMultiplier(name, ref double)`,
   đúng tên có `WT` hoa. Ghi chú "chưa xác minh" trong `sap_reader.py` nay đã xác minh xong.
6. **`cPointObj.GetCoordCartesian` có thêm tham số `CSys` (string)** — chữ ký thật:
   `GetCoordCartesian(name, ref X, ref Y, ref Z, string CSys)`; plugin truyền `"Global"`.
   Python COM chỉ truyền 3 số (COM cho phép bỏ tham số) nên không thấy tham số này.
7. **`cPointObj.GetRestraint(name, ref bool[] Value)`** — mảng phải tạo trước với 6 phần tử
   (`new bool[6]`); plugin kiểm tra `ret == 0` và độ dài mảng trước khi đọc.
8. **`cAnalysisResultsSetup` CÓ getter snapshot** — `GetCaseSelectedForOutput(name, ref bool)` /
   `GetComboSelectedForOutput(name, ref bool)` đều tồn tại. `SapStateGuard` snapshot +
   restore đầy đủ được; KHÔNG có giới hạn như task dự phòng.
9. **`cSapModel.GetPresentUnits()` trả `eUnits` TRỰC TIẾP, không tham số ref** — khớp task
   và khớp `Core.Units.FactorsByEUnits` (mã 1–16; tên enum vd `kN_m_C = 6`).
   `GetModelFilename(bool)` / `GetModelFilepath()` trả `string` trực tiếp (không mã ret).
10. **`cPluginContract.Info` trả `int`** (`Int32 Info(ref string Text)`), `Main` trả `void`
    (`Void Main(ref cSapModel SapModel, ref cPluginCallback ISapPlugin)`).
    `cPluginCallback.Finish(int)` + thuộc tính `Finished`/`ErrorFlag` có sẵn.
11. **Type `CSiAPIv1.cSapObject` KHÔNG tồn tại trong DLL này** (chỉ liên quan tới code
    Python dùng ProgID `CSI.SAP2000.API.SapObject` để attach từ ngoài; plugin in-process
    không cần).
12. **`cCombo.GetCaseList` có thêm mảng `eCNameType[]`** so với Python (đúng như task dự báo);
    `eCNameType`: `LoadCase = 0`, `LoadCombo = 1`.
13. **`eLoadPatternType` có 62 giá trị** (Dead=1, SuperDead=2, Live=3, ReduceLive=4,
    Quake=5, Wind=6, Snow=7, Other=8, ...). Map của plugin khớp Python cho 1/2/3/5/6;
    các loại còn lại -> "Other".
14. **`eLoadCaseType` 1–17 khớp đúng bảng `LOAD_CASE_TYPES` trong `sap_reader.py`**
    (LinearStatic=1 ... NonlinearStaticMultiStep=17); tập nonlinear {2,6,8,16,17} giữ nguyên.
15. **AssemblyVersion 1.0.0.0, FileVersion 2.7.0.0** — FileVersion khớp mô tả task (2.7.0.0).

## Dump thô đầy đủ

File dump thô (1795 dòng, mọi type/method/enum trong DLL) lưu tạm tại `/tmp/csi-dump/raw.txt`
(không push). File này chỉ trích các chữ ký plugin dùng + toàn bộ 5 enum liên quan.
