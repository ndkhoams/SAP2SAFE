using System;
using System.Collections.Generic;
using System.Linq;
using CSiAPIv1;
using Sap2Safe.Core;

namespace Sap2Safe.Plugin;

/// <summary>Lỗi gọi API SAP (ret != 0 hoặc không có dữ liệu). Ghi rõ tên hàm + mã lỗi.</summary>
public sealed class SapApiException : Exception
{
    public SapApiException(string message) : base(message)
    {
    }
}

/// <summary>
/// Đọc model SAP2000 in-process qua <c>cSapModel</c>.
/// Mọi giá trị trả về đã đổi sang hệ nội bộ kN, m, kN-m (qua <see cref="Core.Units"/>).
/// Chữ ký API dùng ở đây đã xác minh bằng reflection từ CSiAPIv1.dll — xem API_DUMP.md.
/// </summary>
public sealed class SapReader
{
    private readonly cSapModel _model;
    private double _forceFactor;
    private double _lengthFactor;
    private bool _unitsLoaded;
    private List<(string Name, double X, double Y, double Z)>? _pointsCache;

    /// <summary>Ghi chú không nghiêm trọng trong lần đọc gần nhất (vd SelfWTMultiplier đọc lỗi).</summary>
    public List<string> Notes { get; } = new();

    public SapReader(cSapModel model)
    {
        _model = model ?? throw new ArgumentNullException(nameof(model));
    }

    public cSapModel Model => _model;

    private static void Check(int ret, string action)
    {
        if (ret != 0)
        {
            throw new SapApiException($"{action} thất bại (mã lỗi SAP trả về: {ret}).");
        }
    }

    private static int SafeCount(int n, Array? arr)
    {
        if (arr is null)
        {
            return 0;
        }
        return Math.Min(n, arr.Length);
    }

    // -- đơn vị ---------------------------------------------------------

    /// <summary>Đơn vị hiện tại của model. GetPresentUnits() trả eUnits trực tiếp (xem API_DUMP.md).</summary>
    public (double ForceToKn, double LengthToM) GetUnits()
    {
        eUnits units = _model.GetPresentUnits();
        var factors = Units.FactorsByEUnits((int)units);
        _forceFactor = factors.ForceToKn;
        _lengthFactor = factors.LengthToM;
        _unitsLoaded = true;
        return factors;
    }

    public string GetUnitsName()
    {
        return _model.GetPresentUnits().ToString();
    }

    public double ForceFactor
    {
        get { EnsureUnits(); return _forceFactor; }
    }

    public double LengthFactor
    {
        get { EnsureUnits(); return _lengthFactor; }
    }

    private void EnsureUnits()
    {
        if (!_unitsLoaded)
        {
            GetUnits();
        }
    }

    /// <summary>Đường dẫn đầy đủ file .sdb đang mở (null nếu chưa lưu / không lấy được).</summary>
    public string? GetModelFilePath()
    {
        try
        {
            string path = _model.GetModelFilename(true);
            return string.IsNullOrWhiteSpace(path) ? null : path;
        }
        catch
        {
            return null;
        }
    }

    /// <summary>Thư mục chứa file .sdb (null nếu không lấy được).</summary>
    public string? GetModelDirectory()
    {
        try
        {
            string dir = _model.GetModelFilepath();
            return string.IsNullOrWhiteSpace(dir) ? null : dir;
        }
        catch
        {
            return null;
        }
    }

    // -- load pattern / case / combo -------------------------------------

    private static string PatternDesignType(eLoadPatternType type)
    {
        // Khớp _PATTERN_TYPE_MAP trong sap_reader.py; các loại còn lại -> Other.
        switch (type)
        {
            case eLoadPatternType.Dead: return "Dead";
            case eLoadPatternType.SuperDead: return "Super Dead";
            case eLoadPatternType.Live: return "Live";
            case eLoadPatternType.Quake: return "Quake";
            case eLoadPatternType.Wind: return "Wind";
            default: return "Other";
        }
    }

    public List<PatternDef> ListLoadPatterns()
    {
        int n = 0;
        string[]? names = null;
        Check(_model.LoadPatterns.GetNameList(ref n, ref names), "Đọc danh sách load pattern");
        var list = new List<PatternDef>();
        int count = SafeCount(n, names);
        for (int i = 0; i < count; i++)
        {
            string name = names![i];
            if (name is null)
            {
                continue;
            }
            eLoadPatternType ptype = eLoadPatternType.Other;
            int ret = _model.LoadPatterns.GetLoadType(name, ref ptype);
            string designType = ret == 0 ? PatternDesignType(ptype) : "Other";
            double selfWt = 0;
            ret = _model.LoadPatterns.GetSelfWTMultiplier(name, ref selfWt);
            if (ret != 0)
            {
                // Hàm tồn tại (đã xác minh bằng dump) nhưng model này đọc lỗi:
                // không throw — mặc định 0 như sap_reader.py, ghi chú lại.
                selfWt = 0;
                Notes.Add($"Pattern {name}: không đọc được Self Weight Multiplier (mã {ret}) — mặc định 0.");
            }
            list.Add(new PatternDef { Name = name, Type = designType, SelfWtMult = selfWt });
        }
        return list;
    }

    // eLoadCaseType 1..17 — khớp LOAD_CASE_TYPES trong sap_reader.py (đã xác minh bằng dump).
    private static readonly string[] LoadCaseTypeNames =
    {
        "Linear Static", "Nonlinear Static", "Modal", "Response Spectrum",
        "Linear History", "Nonlinear History", "Linear Dynamic", "Nonlinear Dynamic",
        "Moving Load", "Buckling", "Steady State", "Power Spectral Density",
        "Linear Static MultiStep", "HyperStatic", "External Results",
        "Staged Construction", "Nonlinear Static MultiStep",
    };

    private static bool IsNonlinearCaseType(int type)
    {
        return type == 2 || type == 6 || type == 8 || type == 16 || type == 17;
    }

    public static string LoadCaseTypeName(int type)
    {
        if (type >= 1 && type <= LoadCaseTypeNames.Length)
        {
            return LoadCaseTypeNames[type - 1];
        }
        return "Unknown";
    }

    public List<SapOutput> ListLoadCases()
    {
        var seen = new HashSet<string>(StringComparer.Ordinal);
        var list = new List<SapOutput>();
        // GetNameList BẮT BUỘC có tham số lọc eLoadCaseType (không có overload không lọc):
        // gọi lặp 17 loại rồi gộp, loại trùng tên.
        for (int t = 1; t <= 17; t++)
        {
            var filter = (eLoadCaseType)t;
            int n = 0;
            string[]? names = null;
            Check(_model.LoadCases.GetNameList(ref n, ref names, filter),
                $"Đọc danh sách load case loại {LoadCaseTypeName(t)}");
            int count = SafeCount(n, names);
            for (int i = 0; i < count; i++)
            {
                string name = names![i];
                if (name is null || !seen.Add(name))
                {
                    continue;
                }
                eLoadCaseType caseType = filter;
                int subType = 0;
                Check(_model.LoadCases.GetTypeOAPI(name, ref caseType, ref subType),
                    $"Đọc loại load case {name}");
                list.Add(new SapOutput
                {
                    Name = name,
                    Kind = "case",
                    CaseType = (int)caseType,
                    IsNonlinear = IsNonlinearCaseType((int)caseType),
                });
            }
        }
        return list;
    }

    /// <summary>
    /// Ánh xạ mã int loại combo -> chuỗi SAFE.
    /// CẢNH BÁO: DLL không chứa enum loại combo nên ánh xạ này theo tài liệu CSI OAPI
    /// (0 Linear Add, 1 Envelope, 2 Absolute Add, 3 SRSS, 4 Range Add) — CHƯA xác minh
    /// bằng runtime; kiểm chứng trên SAP thật (xem HUONG_DAN_TEST_PLUGIN.md).
    /// </summary>
    public static string ComboTypeName(int comboType)
    {
        switch (comboType)
        {
            case 0: return "Linear Add";
            case 1: return "Envelope";
            case 2: return "Absolute Add";
            case 3: return "SRSS";
            case 4: return "Range Add";
            default: return "Linear Add";
        }
    }

    public List<SapOutput> ListCombos()
    {
        int n = 0;
        string[]? names = null;
        Check(_model.RespCombo.GetNameList(ref n, ref names), "Đọc danh sách load combo");
        var list = new List<SapOutput>();
        int count = SafeCount(n, names);
        for (int i = 0; i < count; i++)
        {
            string name = names![i];
            if (name is null)
            {
                continue;
            }
            int comboType = 0;
            Check(_model.RespCombo.GetTypeOAPI(name, ref comboType),
                $"Đọc loại combo {name}");
            int m = 0;
            eCNameType[]? cnameTypes = null;
            string[]? cname = null;
            double[]? sf = null;
            Check(_model.RespCombo.GetCaseList(name, ref m, ref cnameTypes, ref cname, ref sf),
                $"Đọc thành phần combo {name}");
            var output = new SapOutput
            {
                Name = name,
                Kind = "combo",
                ComboType = ComboTypeName(comboType),
            };
            int items = Math.Min(SafeCount(m, cname), SafeCount(m, sf));
            for (int j = 0; j < items; j++)
            {
                // Thành phần có thể là case (LoadCase=0) hoặc combo lồng nhau (LoadCombo=1);
                // Pipeline.ClosureOutputs tự mở rộng cả hai theo tên nên giữ nguyên như Python.
                output.Components.Add(new ComboItem(cname![j] ?? "", sf![j]));
            }
            list.Add(output);
        }
        return list;
    }

    // -- hình học --------------------------------------------------------

    /// <summary>Tất cả PointObj (bỏ joint tên bắt đầu "~" — joint mesh nội bộ), tọa độ đã đổi sang m.</summary>
    private List<(string Name, double X, double Y, double Z)> GetAllPoints()
    {
        if (_pointsCache != null)
        {
            return _pointsCache;
        }
        EnsureUnits();
        int n = 0;
        string[]? names = null;
        Check(_model.PointObj.GetNameList(ref n, ref names), "Đọc danh sách joint");
        var points = new List<(string, double, double, double)>();
        int count = SafeCount(n, names);
        for (int i = 0; i < count; i++)
        {
            string name = names![i];
            if (name is null || name.StartsWith("~", StringComparison.Ordinal))
            {
                continue;
            }
            double x = 0, y = 0, z = 0;
            Check(_model.PointObj.GetCoordCartesian(name, ref x, ref y, ref z, "Global"),
                $"Đọc tọa độ joint {name}");
            points.Add((name, x * _lengthFactor, y * _lengthFactor, z * _lengthFactor));
        }
        _pointsCache = points;
        return points;
    }

    public int GetJointCount()
    {
        return GetAllPoints().Count;
    }

    /// <summary>Các cao độ Z có joint (gom nhóm theo tol), sắp tăng dần.</summary>
    public List<double> ListZLevels(double tol = 0.005)
    {
        var levels = new List<double>();
        foreach (var p in GetAllPoints())
        {
            bool found = false;
            foreach (double lv in levels)
            {
                if (Math.Abs(p.Z - lv) <= tol)
                {
                    found = true;
                    break;
                }
            }
            if (!found)
            {
                levels.Add(p.Z);
            }
        }
        levels.Sort();
        return levels;
    }

    private bool[]? ReadRestraint(string name)
    {
        bool[] value = new bool[6];
        int ret = _model.PointObj.GetRestraint(name, ref value);
        if (ret != 0 || value is null || value.Length < 6)
        {
            return null;
        }
        return value.Take(6).ToArray();
    }

    /// <summary>
    /// Z có nhiều joint có gối nhất (gợi ý mặc định cho combobox Z).
    /// Một lần duyệt duy nhất qua mọi joint để không gọi API lặp lại theo từng level.
    /// </summary>
    public double? GetSuggestedZ(double tol = 0.005)
    {
        var levels = new List<(double Z, int RestrainedCount)>();
        foreach (var p in GetAllPoints())
        {
            bool[]? restraint = ReadRestraint(p.Name);
            bool restrained = restraint != null && restraint.Any(v => v);
            int idx = -1;
            for (int i = 0; i < levels.Count; i++)
            {
                if (Math.Abs(p.Z - levels[i].Z) <= tol)
                {
                    idx = i;
                    break;
                }
            }
            if (idx < 0)
            {
                levels.Add((p.Z, restrained ? 1 : 0));
            }
            else if (restrained)
            {
                levels[idx] = (levels[idx].Z, levels[idx].RestrainedCount + 1);
            }
        }
        if (levels.Count == 0)
        {
            return null;
        }
        levels.Sort((a, b) => a.Z.CompareTo(b.Z));
        double bestZ = levels[0].Z;
        int bestCount = levels[0].RestrainedCount;
        foreach (var lv in levels)
        {
            if (lv.RestrainedCount > bestCount)
            {
                bestCount = lv.RestrainedCount;
                bestZ = lv.Z;
            }
        }
        return bestZ;
    }

    /// <summary>Các joint tại cao độ Z (tọa độ m). Restraint null nếu API lỗi — Pipeline mặc định Yes cả 6 + warning.</summary>
    public List<Joint> GetJointsAtZ(double z, double tol = 0.005)
    {
        var joints = new List<Joint>();
        foreach (var p in GetAllPoints())
        {
            if (Math.Abs(p.Z - z) > tol)
            {
                continue;
            }
            bool[]? restraint = ReadRestraint(p.Name);
            bool restrained = restraint != null && restraint.Any(v => v);
            joints.Add(new Joint
            {
                Name = p.Name,
                X = p.X,
                Y = p.Y,
                Z = p.Z,
                Restrained = restrained,
                Restraint = restraint,
            });
        }
        return joints;
    }

    // -- phản lực --------------------------------------------------------

    /// <summary>
    /// Đọc JointReact cho từng output (case; combo cũng hỗ trợ nhưng Pipeline chỉ đóng băng case).
    /// Name "" = tất cả joint; ItemTypeElm = ObjectElm (== 0, đã xác minh — TUYỆT ĐỐI không truyền literal 1).
    /// Lực đổi sang kN, mô men sang kN-m. 0 dòng -> throw với gợi ý chưa chạy phân tích.
    /// </summary>
    public List<Reaction> GetJointReactions(IEnumerable<SapOutput> outputs)
    {
        EnsureUnits();
        double momentFactor = _forceFactor * _lengthFactor;
        var reactions = new List<Reaction>();
        foreach (var output in outputs)
        {
            Check(_model.Results.Setup.DeselectAllCasesAndCombosForOutput(),
                "Bỏ chọn output trước khi đọc phản lực");
            if (output.Kind == "combo")
            {
                Check(_model.Results.Setup.SetComboSelectedForOutput(output.Name, true),
                    $"Chọn combo {output.Name} để đọc phản lực");
            }
            else
            {
                Check(_model.Results.Setup.SetCaseSelectedForOutput(output.Name, true),
                    $"Chọn case {output.Name} để đọc phản lực");
            }

            int n = 0;
            string[]? obj = null, elm = null, loadCase = null, stepType = null;
            double[]? stepNum = null, f1 = null, f2 = null, f3 = null, m1 = null, m2 = null, m3 = null;
            int ret = _model.Results.JointReact(
                "", eItemTypeElm.ObjectElm,
                ref n, ref obj, ref elm, ref loadCase, ref stepType, ref stepNum,
                ref f1, ref f2, ref f3, ref m1, ref m2, ref m3);
            Check(ret, $"Đọc phản lực của {output.Name}");

            // Mảng null/thiếu phần tử -> coi như không có dữ liệu, không index mù.
            int count = n;
            foreach (Array? arr in new Array?[] { obj, loadCase, stepType, stepNum, f1, f2, f3, m1, m2, m3 })
            {
                if (arr is null)
                {
                    count = 0;
                    break;
                }
                count = Math.Min(count, arr.Length);
            }
            if (count <= 0)
            {
                throw new SapApiException(
                    $"Không có phản lực cho {output.Name} — có thể chưa chạy phân tích " +
                    "(Run Analysis) hoặc output chưa được chọn để xuất kết quả.");
            }
            for (int i = 0; i < count; i++)
            {
                reactions.Add(new Reaction
                {
                    Joint = obj![i] ?? "",
                    OutputName = loadCase![i] ?? output.Name,
                    OutputKind = output.Kind,
                    StepType = stepType![i] ?? "",
                    StepNum = stepNum![i],
                    F1 = f1![i] * _forceFactor,
                    F2 = f2![i] * _forceFactor,
                    F3 = f3![i] * _forceFactor,
                    M1 = m1![i] * momentFactor,
                    M2 = m2![i] * momentFactor,
                    M3 = m3![i] * momentFactor,
                });
            }
        }
        return reactions;
    }
}

/// <summary>
/// Giữ nguyên lựa chọn case/combo đang chọn để xuất kết quả trong Results.Setup:
/// snapshot lúc tạo (nhờ getter GetCaseSelectedForOutput / GetComboSelectedForOutput —
/// đã xác minh tồn tại trong DLL, xem API_DUMP.md), restore lúc Dispose.
/// Dùng bọc mọi lần đọc phản lực: <c>using (new SapStateGuard(...)) { ... }</c>.
/// </summary>
public sealed class SapStateGuard : IDisposable
{
    private readonly cSapModel _model;
    private readonly List<string> _cases = new();
    private readonly List<string> _combos = new();
    private bool _disposed;

    public SapStateGuard(cSapModel model, IEnumerable<SapOutput> outputs)
    {
        _model = model ?? throw new ArgumentNullException(nameof(model));
        foreach (var o in outputs)
        {
            bool selected = false;
            int ret;
            if (o.Kind == "combo")
            {
                ret = model.Results.Setup.GetComboSelectedForOutput(o.Name, ref selected);
                if (ret == 0 && selected)
                {
                    _combos.Add(o.Name);
                }
            }
            else
            {
                ret = model.Results.Setup.GetCaseSelectedForOutput(o.Name, ref selected);
                if (ret == 0 && selected)
                {
                    _cases.Add(o.Name);
                }
            }
        }
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }
        _disposed = true;
        try
        {
            _model.Results.Setup.DeselectAllCasesAndCombosForOutput();
        }
        catch
        {
            // Restore là best-effort: không để lỗi restore che lỗi chính.
        }
        foreach (string name in _cases)
        {
            try
            {
                _model.Results.Setup.SetCaseSelectedForOutput(name, true);
            }
            catch
            {
            }
        }
        foreach (string name in _combos)
        {
            try
            {
                _model.Results.Setup.SetComboSelectedForOutput(name, true);
            }
            catch
            {
            }
        }
    }
}
