using System;
using System.Collections.Generic;
using System.Globalization;

namespace Sap2Safe.Core;

/// <summary>
/// Kết quả phân tích tách MAX/MIN của 1 case (output).
/// Pipeline dùng thông tin này để tạo combo _ENV và viết lại combo gốc.
/// EnvName: tên combo _ENV trong file xuất (đã xử lý trùng) — Pipeline điền.
/// OnlySide: "Max" nếu chỉ có dòng Max, "Min" nếu chỉ có dòng Min.
/// </summary>
public sealed class SplitInfo
{
    public string Output { get; set; } = "";
    public bool HasMaxMin;
    public bool Split;
    public double MaxDiff;
    public string? MaxJoint;
    public string? MaxComponent;
    public string? OnlySide;
    public List<string> FilledJoints { get; } = new();
    public string? EnvName;
}

public sealed class FreezeResult
{
    public List<FrozenLoad> Frozen { get; } = new();
    public List<string> Warnings { get; } = new();
    public Dictionary<string, SplitInfo> Splits { get; } = new();
}

public static class StepSelect
{
    public static readonly string[] StepModes = { "last", "specific", "governing", "maxmin" };

    /// <summary>Dung sai so sánh Max/Min: khác nhau nếu |a-b| &gt; 1e-6 * max(1, |a|, |b|).</summary>
    public const double SplitTolRel = 1e-6;

    private static readonly string[] ComponentLabels = { "F1", "F2", "F3", "M1", "M2", "M3" };

    private static double ComponentValue(Reaction r, int index)
    {
        switch (index)
        {
            case 0: return r.F1;
            case 1: return r.F2;
            case 2: return r.F3;
            case 3: return r.M1;
            case 4: return r.M2;
            default: return r.M3;
        }
    }

    private static bool Differs(double a, double b)
    {
        return Math.Abs(a - b) > SplitTolRel * Math.Max(1.0, Math.Max(Math.Abs(a), Math.Abs(b)));
    }

    /// <summary>Repr của float theo Python: số nguyên thành "N.0", còn lại "R" với 'e' thường.</summary>
    internal static string PythonFloatRepr(double value)
    {
        if (double.IsNaN(value))
        {
            return "nan";
        }
        if (double.IsPositiveInfinity(value))
        {
            return "inf";
        }
        if (double.IsNegativeInfinity(value))
        {
            return "-inf";
        }
        if (value == 0.0)
        {
            return 1.0 / value < 0 ? "-0.0" : "0.0";
        }
        if (value == Math.Truncate(value))
        {
            string intPart;
            if (Math.Abs(value) <= 9e18)
            {
                intPart = ((long)value).ToString(CultureInfo.InvariantCulture);
            }
            else
            {
                intPart = value.ToString("F0", CultureInfo.InvariantCulture);
            }
            return intPart + ".0";
        }
        return value.ToString("R", CultureInfo.InvariantCulture).Replace("E", "e");
    }

    /// <summary>Format :g của Python (6 chữ số có nghĩa), vd 1.0 -&gt; "1".</summary>
    public static string PythonGFormat(double value)
    {
        if (double.IsNaN(value))
        {
            return "nan";
        }
        if (double.IsPositiveInfinity(value))
        {
            return "inf";
        }
        if (double.IsNegativeInfinity(value))
        {
            return "-inf";
        }
        return value.ToString("G6", CultureInfo.InvariantCulture).Replace("E", "e");
    }

    public static FreezeResult FreezeReactions(
        List<Reaction> rows,
        string mode = "last",
        (string StepType, double StepNum)? specific = null,
        Dictionary<string, (double X, double Y)>? joints = null)
    {
        bool modeOk = false;
        foreach (string m in StepModes)
        {
            if (m == mode)
            {
                modeOk = true;
                break;
            }
        }
        if (!modeOk)
        {
            throw new ArgumentException(
                $"Step mode không hỗ trợ: '{mode}' (chọn trong ('last', 'specific', 'governing', 'maxmin'))");
        }
        var jointsMap = joints ?? new Dictionary<string, (double X, double Y)>();
        var result = new FreezeResult();
        var frozen = result.Frozen;
        var warnings = result.Warnings;
        var splits = result.Splits;

        // Gom theo output_name, giữ thứ tự xuất hiện đầu tiên.
        var outputOrder = new List<string>();
        var grouped = new Dictionary<string, List<Reaction>>();
        foreach (var r in rows)
        {
            if (!grouped.TryGetValue(r.OutputName, out var list))
            {
                list = new List<Reaction>();
                grouped[r.OutputName] = list;
                outputOrder.Add(r.OutputName);
            }
            list.Add(r);
        }

        foreach (string outputName in outputOrder)
        {
            var outRows = grouped[outputName];
            // Gom theo joint -> {step_key: Reaction}, giữ thứ tự xuất hiện.
            var jointOrder = new List<string>();
            var byJoint = new Dictionary<string, Dictionary<(string StepType, double StepNum), Reaction>>();
            var stepOrder = new Dictionary<string, List<(string StepType, double StepNum)>>();
            foreach (var r in outRows)
            {
                if (!byJoint.TryGetValue(r.Joint, out var steps))
                {
                    steps = new Dictionary<(string, double), Reaction>();
                    byJoint[r.Joint] = steps;
                    stepOrder[r.Joint] = new List<(string, double)>();
                    jointOrder.Add(r.Joint);
                }
                var key = (r.StepType ?? "", r.StepNum);
                if (!steps.ContainsKey(key))
                {
                    stepOrder[r.Joint].Add(key);
                }
                steps[key] = r;
            }

            if (mode == "last" || mode == "maxmin")
            {
                splits[outputName] = FreezeLastOrMaxMin(
                    outputName, jointOrder, byJoint, stepOrder, jointsMap, frozen, warnings);
                continue;
            }

            splits[outputName] = new SplitInfo { Output = outputName };

            // chosen_step: joint -> step_key, theo thứ tự joint xuất hiện.
            var chosenOrder = new List<string>();
            var chosenStep = new Dictionary<string, (string StepType, double StepNum)>();

            if (mode == "specific")
            {
                if (specific is null)
                {
                    throw new ArgumentException("Mode 'specific' cần tham số specific=(StepType, StepNum)");
                }
                var wanted = specific.Value;
                foreach (string joint in jointOrder)
                {
                    var steps = byJoint[joint];
                    if (!steps.ContainsKey(wanted))
                    {
                        warnings.Add(
                            $"{outputName} / {joint}: không có step ('{wanted.StepType}', {PythonFloatRepr(wanted.StepNum)}), bỏ qua joint này.");
                        continue;
                    }
                    chosenStep[joint] = wanted;
                    chosenOrder.Add(joint);
                }
            }
            else if (mode == "governing")
            {
                double bestAbs = 0.0;
                string? bestJoint = null;
                (string StepType, double StepNum) bestKey = default;
                bool hasBest = false;
                foreach (string joint in jointOrder)
                {
                    foreach (var key in stepOrder[joint])
                    {
                        var r = byJoint[joint][key];
                        double a = Math.Abs(r.F3);
                        if (!hasBest || a > bestAbs)
                        {
                            hasBest = true;
                            bestAbs = a;
                            bestJoint = joint;
                            bestKey = key;
                        }
                    }
                }
                if (!hasBest)
                {
                    continue;
                }
                var govStep = bestKey;
                warnings.Add(
                    $"{outputName}: governing step = {govStep.StepType switch { "" => "Step", var s => s }} {PythonFloatRepr(govStep.StepNum)} (max |F3| tại joint {bestJoint}).");
                foreach (string joint in jointOrder)
                {
                    if (byJoint[joint].ContainsKey(govStep))
                    {
                        chosenStep[joint] = govStep;
                        chosenOrder.Add(joint);
                    }
                }
            }

            foreach (string joint in chosenOrder)
            {
                var step = chosenStep[joint];
                if (!jointsMap.TryGetValue(joint, out var xy))
                {
                    warnings.Add($"{outputName} / {joint}: không có tọa độ, bỏ qua.");
                    continue;
                }
                var r = byJoint[joint][step];
                string stepType = string.IsNullOrEmpty(r.StepType) ? "Step" : r.StepType;
                frozen.Add(new FrozenLoad
                {
                    Joint = joint,
                    X = xy.X,
                    Y = xy.Y,
                    Pattern = outputName,
                    Fx = r.F1,
                    Fy = r.F2,
                    Fz = r.F3,
                    Mx = r.M1,
                    My = r.M2,
                    Mz = r.M3,
                    SourceStep = $"{stepType} {PythonGFormat(r.StepNum)}",
                });
            }
        }

        return result;
    }

    private static Reaction? PickTypedRow(
        Dictionary<(string StepType, double StepNum), Reaction> steps,
        List<(string StepType, double StepNum)> order, string want)
    {
        Reaction? best = null;
        double bestNum = 0.0;
        foreach (var key in order)
        {
            if (key.StepType.Trim().ToLowerInvariant() != want)
            {
                continue;
            }
            if (best is null || key.StepNum > bestNum)
            {
                best = steps[key];
                bestNum = key.StepNum;
            }
        }
        return best;
    }

    private static Reaction? LastStepRow(
        Dictionary<(string StepType, double StepNum), Reaction> steps,
        List<(string StepType, double StepNum)> order)
    {
        Reaction? best = null;
        double bestNum = 0.0;
        foreach (var key in order)
        {
            if (best is null || key.StepNum > bestNum)
            {
                best = steps[key];
                bestNum = key.StepNum;
            }
        }
        return best;
    }

    private static FrozenLoad MakeLoad(
        string pattern, string joint, (double X, double Y) xy, Reaction r)
    {
        string stepType = string.IsNullOrEmpty(r.StepType) ? "Step" : r.StepType;
        return new FrozenLoad
        {
            Joint = joint,
            X = xy.X,
            Y = xy.Y,
            Pattern = pattern,
            Fx = r.F1,
            Fy = r.F2,
            Fz = r.F3,
            Mx = r.M1,
            My = r.M2,
            Mz = r.M3,
            SourceStep = $"{stepType} {PythonGFormat(r.StepNum)}",
        };
    }

    /// <summary>
    /// Logic "last" + tách MAX/MIN mặc định (mode "maxmin" là alias).
    /// Không có dòng Max/Min nào: hành vi "last" cũ (StepNum lớn nhất).
    /// Có dòng Max/Min: so sánh 2 vector từng joint; khác nhau -&gt; tách
    /// _MAX/_MIN; giống nhau -&gt; 1 pattern tên gốc từ dòng Max.
    /// </summary>
    private static SplitInfo FreezeLastOrMaxMin(
        string outputName,
        List<string> jointOrder,
        Dictionary<string, Dictionary<(string StepType, double StepNum), Reaction>> byJoint,
        Dictionary<string, List<(string StepType, double StepNum)>> stepOrder,
        Dictionary<string, (double X, double Y)> joints,
        List<FrozenLoad> frozen,
        List<string> warnings)
    {
        var info = new SplitInfo { Output = outputName };

        // Bước 1: dòng Max/Min/last-step từng joint.
        var perJoint = new Dictionary<string, (Reaction? Max, Reaction? Min, Reaction? Last)>();
        bool hasMaxMin = false;
        bool hasMaxAny = false;
        bool hasMinAny = false;
        foreach (string joint in jointOrder)
        {
            var steps = byJoint[joint];
            var order = stepOrder[joint];
            var maxRow = PickTypedRow(steps, order, "max");
            var minRow = PickTypedRow(steps, order, "min");
            var lastRow = LastStepRow(steps, order);
            if (maxRow is not null || minRow is not null)
            {
                hasMaxMin = true;
            }
            if (maxRow is not null)
            {
                hasMaxAny = true;
            }
            if (minRow is not null)
            {
                hasMinAny = true;
            }
            perJoint[joint] = (maxRow, minRow, lastRow);
        }
        info.HasMaxMin = hasMaxMin;
        if (hasMaxAny && !hasMinAny)
        {
            info.OnlySide = "Max";
        }
        else if (hasMinAny && !hasMaxAny)
        {
            info.OnlySide = "Min";
        }

        if (!hasMaxMin)
        {
            // Hành vi "last" cũ, không tách.
            foreach (string joint in jointOrder)
            {
                if (!joints.TryGetValue(joint, out var xy))
                {
                    warnings.Add($"{outputName} / {joint}: không có tọa độ, bỏ qua.");
                    continue;
                }
                var r = LastStepRow(byJoint[joint], stepOrder[joint])!;
                frozen.Add(MakeLoad(outputName, joint, xy, r));
            }
            return info;
        }

        // Bước 2: so sánh Max/Min ở các joint có đủ 2 phía.
        bool split = false;
        foreach (string joint in jointOrder)
        {
            var (maxRow, minRow, _) = perJoint[joint];
            if (maxRow is null || minRow is null)
            {
                continue;
            }
            for (int c = 0; c < 6; c++)
            {
                double a = ComponentValue(maxRow, c);
                double b = ComponentValue(minRow, c);
                if (Differs(a, b))
                {
                    split = true;
                    double d = Math.Abs(a - b);
                    if (d > info.MaxDiff)
                    {
                        info.MaxDiff = d;
                        info.MaxJoint = joint;
                        info.MaxComponent = ComponentLabels[c];
                    }
                }
            }
        }
        info.Split = split;

        if (!split)
        {
            // Giống nhau hết: 1 pattern tên gốc, lấy dòng Max (thiếu Max
            // thì lấy dòng Min, thiếu cả 2 thì lấy step cuối).
            foreach (string joint in jointOrder)
            {
                if (!joints.TryGetValue(joint, out var xy))
                {
                    warnings.Add($"{outputName} / {joint}: không có tọa độ, bỏ qua.");
                    continue;
                }
                var (maxRow, minRow, lastRow) = perJoint[joint];
                var r = maxRow ?? minRow ?? lastRow!;
                frozen.Add(MakeLoad(outputName, joint, xy, r));
            }
            return info;
        }

        // Bước 3: tách — _MAX trước, _MIN sau. Joint thiếu 1 phía thì lấy
        // phía còn lại bù vào (ghi warning); joint chỉ có dòng Step thì lấy
        // step cuối bù cho cả 2 phía (ghi warning).
        warnings.Add(
            $"{outputName}: tách MAX/MIN — Max khác Min (chênh lệch lớn nhất " +
            $"{PythonGFormat(info.MaxDiff)} ở {info.MaxComponent}, joint {info.MaxJoint}); " +
            "vector _MAX/_MIN là các dòng envelope do SAP báo cáo, có thể " +
            "không đồng thời.");
        var suffixes = new[] { ("_MAX", "max", "Min"), ("_MIN", "min", "Max") };
        foreach (var (suffix, want, other) in suffixes)
        {
            foreach (string joint in jointOrder)
            {
                if (!joints.TryGetValue(joint, out var xy))
                {
                    warnings.Add($"{outputName} / {joint}: không có tọa độ, bỏ qua.");
                    continue;
                }
                var (maxRow, minRow, lastRow) = perJoint[joint];
                Reaction? own = want == "max" ? maxRow : minRow;
                Reaction? alt = want == "max" ? minRow : maxRow;
                Reaction r;
                if (own is not null)
                {
                    r = own;
                }
                else if (alt is not null)
                {
                    r = alt;
                    info.FilledJoints.Add(joint);
                    warnings.Add(
                        $"{outputName} / {joint}: thiếu dòng {Capitalize(want)} — " +
                        $"dùng dòng {other} bù vào khi tách MAX/MIN.");
                }
                else
                {
                    r = lastRow!;
                    info.FilledJoints.Add(joint);
                    warnings.Add(
                        $"{outputName} / {joint}: không có dòng Max/Min — dùng " +
                        "step cuối bù vào khi tách MAX/MIN.");
                }
                frozen.Add(MakeLoad(outputName + suffix, joint, xy, r));
            }
        }
        return info;
    }

    private static string Capitalize(string s)
    {
        if (string.IsNullOrEmpty(s))
        {
            return s;
        }
        return char.ToUpperInvariant(s[0]) + s.Substring(1);
    }
}
