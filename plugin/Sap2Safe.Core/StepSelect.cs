using System;
using System.Collections.Generic;
using System.Globalization;

namespace Sap2Safe.Core;

public static class StepSelect
{
    public static readonly string[] StepModes = { "last", "specific", "governing", "maxmin" };

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
    internal static string PythonGFormat(double value)
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

    public static (List<FrozenLoad> Frozen, List<string> Warnings) FreezeReactions(
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
        var frozen = new List<FrozenLoad>();
        var warnings = new List<string>();

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

            if (mode == "maxmin")
            {
                FreezeMaxMin(outputName, jointOrder, byJoint, stepOrder, jointsMap, frozen, warnings);
                continue;
            }

            // chosen_step: joint -> step_key, theo thứ tự joint xuất hiện.
            var chosenOrder = new List<string>();
            var chosenStep = new Dictionary<string, (string StepType, double StepNum)>();

            if (mode == "last")
            {
                foreach (string joint in jointOrder)
                {
                    var keys = stepOrder[joint];
                    var best = keys[0];
                    for (int k = 1; k < keys.Count; k++)
                    {
                        if (keys[k].StepNum > best.StepNum)
                        {
                            best = keys[k];
                        }
                    }
                    chosenStep[joint] = best;
                    chosenOrder.Add(joint);
                }
            }
            else if (mode == "specific")
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

        return (frozen, warnings);
    }

    private static void FreezeMaxMin(
        string outputName,
        List<string> jointOrder,
        Dictionary<string, Dictionary<(string StepType, double StepNum), Reaction>> byJoint,
        Dictionary<string, List<(string StepType, double StepNum)>> stepOrder,
        Dictionary<string, (double X, double Y)> joints,
        List<FrozenLoad> frozen,
        List<string> warnings)
    {
        warnings.Add(
            $"{outputName}: tách MAX/MIN — các thành phần cực đại có thể ở các step khác nhau, vector này KHÔNG đồng thời (xem HUONG_DAN_TEST.md).");
        var suffixes = new[] { "_MAX", "_MIN" };
        for (int s = 0; s < suffixes.Length; s++)
        {
            string suffix = suffixes[s];
            bool pickMax = s == 0;
            foreach (string joint in jointOrder)
            {
                if (!joints.TryGetValue(joint, out var xy))
                {
                    continue;
                }
                var vals = new List<Reaction>();
                foreach (var key in stepOrder[joint])
                {
                    vals.Add(byJoint[joint][key]);
                }
                double Pick(Func<Reaction, double> get)
                {
                    double best = get(vals[0]);
                    for (int k = 1; k < vals.Count; k++)
                    {
                        double v = get(vals[k]);
                        if (pickMax ? v > best : v < best)
                        {
                            best = v;
                        }
                    }
                    return best;
                }
                frozen.Add(new FrozenLoad
                {
                    Joint = joint,
                    X = xy.X,
                    Y = xy.Y,
                    Pattern = outputName + suffix,
                    Fx = Pick(v => v.F1),
                    Fy = Pick(v => v.F2),
                    Fz = Pick(v => v.F3),
                    Mx = Pick(v => v.M1),
                    My = Pick(v => v.M2),
                    Mz = Pick(v => v.M3),
                    SourceStep = suffix.Substring(1) + " từng thành phần",
                });
            }
        }
    }
}
