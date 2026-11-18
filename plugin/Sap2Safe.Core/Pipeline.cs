using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Sap2Safe.Core;

public sealed class PatternInfo
{
    public string DesignType { get; set; } = "";
    public double SelfWtMult;
}

public sealed class BuildInfo
{
    public bool FlipSign;
    public Dictionary<string, string> NameMap { get; } = new();
    public List<string> Sources { get; } = new();
    public List<(string Pattern, double Fz)> Loads { get; } = new();
    public Dictionary<string, double> SapSums { get; } = new();
    public List<string> Warnings { get; } = new();
    public string SafeVersion { get; set; } = "22.5.1";
    public string Units { get; set; } = "kN, m, C";
    public List<string> Notes { get; } = new();
    public Dictionary<string, SplitInfo> Splits { get; } = new();
}

public sealed class BuildResult
{
    public F2kModel Model { get; set; } = new();
    public BuildInfo Info { get; set; } = new();
    public List<string> Warnings { get { return Info.Warnings; } }
}

public static class Pipeline
{
    public static (List<SapOutput> Included, List<string> Auto) ClosureOutputs(
        List<SapOutput> outputs, List<string> selected)
    {
        var byName = new Dictionary<string, SapOutput>();
        foreach (var o in outputs)
        {
            byName[o.Name] = o;
        }
        var included = new List<SapOutput>();
        var seen = new HashSet<string>();
        var queue = new List<string>(selected);
        var auto = new List<string>();
        while (queue.Count > 0)
        {
            string name = queue[0];
            queue.RemoveAt(0);
            if (seen.Contains(name) || !byName.ContainsKey(name))
            {
                continue;
            }
            seen.Add(name);
            var output = byName[name];
            included.Add(output);
            if (output.Kind == "combo")
            {
                foreach (var comp in output.Components)
                {
                    if (!seen.Contains(comp.Case) && byName.ContainsKey(comp.Case))
                    {
                        queue.Add(comp.Case);
                        if (!selected.Contains(comp.Case))
                        {
                            auto.Add(comp.Case);
                        }
                    }
                }
            }
        }
        return (included, auto);
    }

    /// <summary>
    /// Tên combo _ENV từ tên SAFE của case gốc, xử lý trùng + giới hạn 64 ký tự.
    /// Thử &lt;tên&gt;_ENV, rồi &lt;tên&gt;_ENV_2, &lt;tên&gt;_ENV_3... (port 1-1 từ Python).
    /// </summary>
    private static string MakeEnvComboName(string baseSafe, HashSet<string> used)
    {
        string Cand(string b, string suffix)
        {
            string name = b + suffix;
            if (name.Length > Mapping.MaxSafeNameLen)
            {
                name = b.Substring(0, Mapping.MaxSafeNameLen - suffix.Length) + suffix;
            }
            return name;
        }
        string candidate = Cand(baseSafe, "_ENV");
        int i = 2;
        while (used.Contains(candidate))
        {
            candidate = Cand(baseSafe, "_ENV_" + i.ToString(CultureInfo.InvariantCulture));
            i++;
        }
        return candidate;
    }

    public static BuildResult BuildF2kModel(
        List<Reaction> reactions,
        Dictionary<string, (double X, double Y, double Z)> jointsXyz,
        List<SapOutput> outputs,
        List<string> selected,
        Dictionary<string, bool[]>? jointsRestraint = null,
        Dictionary<string, PatternInfo>? patternInfo = null,
        string stepMode = "last",
        (string StepType, double StepNum)? specific = null,
        bool flipSign = true,
        string safeVersion = "22.5.1")
    {
        var restraintMap = jointsRestraint ?? new Dictionary<string, bool[]>();
        var infoMap = patternInfo ?? new Dictionary<string, PatternInfo>();

        var (selOutputs, auto) = ClosureOutputs(outputs, selected);
        var selNames = new HashSet<string>();
        foreach (var o in selOutputs)
        {
            selNames.Add(o.Name);
        }
        var outputsByName = new Dictionary<string, SapOutput>();
        foreach (var o in outputs)
        {
            outputsByName[o.Name] = o;
        }

        var rows = new List<Reaction>();
        foreach (var r in reactions)
        {
            if (selNames.Contains(r.OutputName) && r.OutputKind == "case")
            {
                rows.Add(r);
            }
        }
        var jointsXy = new Dictionary<string, (double X, double Y)>();
        foreach (var kv in jointsXyz)
        {
            jointsXy[kv.Key] = (kv.Value.X, kv.Value.Y);
        }

        var freezeResult = StepSelect.FreezeReactions(rows, stepMode, specific, jointsXy);
        var frozen = freezeResult.Frozen;
        var warnings = freezeResult.Warnings;
        var splits = freezeResult.Splits;
        if (frozen.Count == 0)
        {
            throw new InvalidOperationException(
                "Không có phản lực nào sau khi đóng băng — kiểm tra lại output đã chọn và joint tại level.");
        }
        if (auto.Count > 0)
        {
            warnings.Add($"Tự động thêm thành phần của combo đã chọn: {string.Join(", ", auto)}.");
        }

        var sapSums = new Dictionary<string, double>();
        foreach (var ld in frozen)
        {
            if (sapSums.TryGetValue(ld.Pattern, out double cur))
            {
                sapSums[ld.Pattern] = cur + ld.Fz;
            }
            else
            {
                sapSums[ld.Pattern] = ld.Fz;
            }
        }

        var nameMap = Mapping.BuildNameMap(selOutputs);

        string SafePattern(string pattern)
        {
            foreach (string suffix in new[] { "_MAX", "_MIN" })
            {
                if (pattern.EndsWith(suffix, StringComparison.Ordinal))
                {
                    string bas = pattern.Substring(0, pattern.Length - suffix.Length);
                    return (nameMap.TryGetValue(bas, out string? mapped) ? mapped : bas) + suffix;
                }
            }
            return nameMap.TryGetValue(pattern, out string? m) ? m : pattern;
        }

        string BaseOf(string pattern)
        {
            foreach (string suffix in new[] { "_MAX", "_MIN" })
            {
                if (pattern.EndsWith(suffix, StringComparison.Ordinal))
                {
                    return pattern.Substring(0, pattern.Length - suffix.Length);
                }
            }
            return pattern;
        }

        var flipped = Mapping.ApplySignFlip(frozen, flipSign);
        foreach (var ld in flipped)
        {
            ld.Pattern = SafePattern(ld.Pattern);
        }
        var remappedSums = new Dictionary<string, double>();
        foreach (var kv in sapSums)
        {
            remappedSums[SafePattern(kv.Key)] = kv.Value;
        }
        sapSums = remappedSums;

        var patternNames = new List<string>();
        foreach (var ld in flipped)
        {
            if (!patternNames.Contains(ld.Pattern))
            {
                patternNames.Add(ld.Pattern);
            }
        }

        // -- Tách MAX/MIN mặc định: combo _ENV + viết lại combo gốc ----------
        // Tên SAFE -> tên gốc (để tra pattern_info theo tên gốc, đúng cả khi
        // name_map đổi tên do sanitize/trùng).
        var safeToOrig = new Dictionary<string, string>();
        foreach (var kv in nameMap)
        {
            safeToOrig[kv.Value] = kv.Key;
        }

        string OrigOfSafePattern(string pattern)
        {
            string bas = BaseOf(pattern);
            return safeToOrig.TryGetValue(bas, out string? orig) ? orig : bas;
        }

        // Tên combo _ENV cho các case vừa tách (tên GỐC -> tên _ENV trong file).
        var splitEnv = new Dictionary<string, string>();
        var usedEnvNames = new HashSet<string>(nameMap.Values);
        foreach (string p in patternNames)
        {
            usedEnvNames.Add(p);
        }
        foreach (var output in selOutputs)
        {
            if (output.Kind == "combo")
            {
                continue;
            }
            if (!splits.TryGetValue(output.Name, out var sp) || !sp.Split)
            {
                continue;
            }
            string env = MakeEnvComboName(nameMap[output.Name], usedEnvNames);
            usedEnvNames.Add(env);
            splitEnv[output.Name] = env;
            sp.EnvName = env;
        }

        // Ghi chú tách MAX/MIN vào .log (qua info.Notes).
        var notes = new List<string>();
        foreach (var output in selOutputs)
        {
            if (output.Kind == "combo")
            {
                continue;
            }
            if (!splits.TryGetValue(output.Name, out var sp) || !sp.HasMaxMin)
            {
                continue;
            }
            string safeName = nameMap[output.Name];
            if (sp.Split)
            {
                string maxSafe = SafePattern(output.Name + "_MAX");
                string minSafe = SafePattern(output.Name + "_MIN");
                notes.Add(
                    $"Tách MAX/MIN mặc định: case {output.Name} — chênh lệch Max-Min " +
                    $"lớn nhất {StepSelect.PythonGFormat(sp.MaxDiff)} ({sp.MaxComponent}, joint " +
                    $"{sp.MaxJoint}) → tách thành {maxSafe} + {minSafe}, tạo " +
                    $"combo Envelope {splitEnv[output.Name]} (Max/Min là các dòng " +
                    "envelope do SAP báo cáo, có thể không đồng thời).");
            }
            else if (sp.OnlySide is not null)
            {
                string other = sp.OnlySide == "Max" ? "Min" : "Max";
                notes.Add(
                    $"Tách MAX/MIN mặc định: case {output.Name} — chỉ có dòng " +
                    $"{sp.OnlySide} (không có dòng {other}) → giữ 1 pattern " +
                    $"tên gốc {safeName}.");
            }
            else
            {
                notes.Add(
                    $"Tách MAX/MIN mặc định: case {output.Name} — Max = Min (chênh " +
                    $"lệch lớn nhất {StepSelect.PythonGFormat(sp.MaxDiff)}) → giữ 1 pattern tên gốc " +
                    $"{safeName}.");
            }
        }

        var model = new F2kModel { SafeVersion = safeVersion };
        foreach (string p in patternNames)
        {
            string orig = OrigOfSafePattern(p);
            if (infoMap.TryGetValue(orig, out var infoP))
            {
                model.Patterns.Add(new PatternDef
                {
                    Name = p,
                    Type = SfWriter.SafePatternType(infoP.DesignType),
                    SelfWtMult = infoP.SelfWtMult,
                });
            }
            else
            {
                model.Patterns.Add(new PatternDef
                {
                    Name = p,
                    Type = "Other",
                    SelfWtMult = 0,
                });
            }
        }
        foreach (string p in patternNames)
        {
            model.Cases.Add(new CaseDef { Name = p, Type = "Linear Static" });
        }

        var sources = new List<string>();
        // Combo _ENV tự sinh đặt TRƯỚC các combo gốc.
        foreach (var output in selOutputs)
        {
            if (output.Kind == "combo")
            {
                continue;
            }
            if (!splits.TryGetValue(output.Name, out var sp) || !sp.Split)
            {
                continue;
            }
            string env = splitEnv[output.Name];
            string maxSafe = SafePattern(output.Name + "_MAX");
            string minSafe = SafePattern(output.Name + "_MIN");
            var envDef = new ComboDef { Name = env, Type = "Envelope" };
            envDef.Items.Add(new ComboItem(maxSafe, 1.0));
            envDef.Items.Add(new ComboItem(minSafe, 1.0));
            model.Combos.Add(envDef);
            sources.Add($"{env} <- combo Envelope tự sinh từ case {output.Name} " +
                $"({maxSafe} 1.0 + {minSafe} 1.0)");
        }
        var rewrittenCombos = new List<string>();
        foreach (var output in selOutputs)
        {
            if (output.Kind != "combo")
            {
                string safeName;
                if (!nameMap.TryGetValue(output.Name, out safeName))
                {
                    safeName = output.Name;
                }
                if (splits.TryGetValue(output.Name, out var sp) && sp.Split)
                {
                    string maxSafe = SafePattern(output.Name + "_MAX");
                    string minSafe = SafePattern(output.Name + "_MIN");
                    sources.Add($"{maxSafe} + {minSafe} <- case {output.Name} (frozen, " +
                        $"{(output.IsNonlinear ? "nonlinear" : "linear")}; tách MAX/MIN, " +
                        $"chênh lệch lớn nhất {StepSelect.PythonGFormat(sp.MaxDiff)})");
                }
                else
                {
                    sources.Add($"{safeName} <- case {output.Name} (frozen, {(output.IsNonlinear ? "nonlinear" : "linear")})");
                }
                continue;
            }
            string comboSafeName;
            if (!nameMap.TryGetValue(output.Name, out comboSafeName))
            {
                comboSafeName = output.Name;
            }
            var (mode, items, note) = Mapping.DecideComboMapping(output, outputsByName);
            var comboDef = new ComboDef
            {
                Name = comboSafeName,
                Type = string.IsNullOrEmpty(output.ComboType) ? "Linear Add" : output.ComboType!,
            };
            if (mode == "rebuild")
            {
                var rewrites = new List<string>();
                foreach (var item in items)
                {
                    string mapped;
                    bool isSplitCase = splitEnv.TryGetValue(item.Case, out string? envName)
                        && outputsByName.TryGetValue(item.Case, out var target)
                        && target.Kind == "case";
                    if (isSplitCase)
                    {
                        comboDef.Items.Add(new ComboItem(envName!, item.Sf));
                        rewrites.Add($"{item.Case} -> {envName}");
                    }
                    else
                    {
                        if (!nameMap.TryGetValue(item.Case, out mapped))
                        {
                            mapped = item.Case;
                        }
                        comboDef.Items.Add(new ComboItem(mapped, item.Sf));
                    }
                }
                if (rewrites.Count > 0)
                {
                    rewrittenCombos.Add($"{comboSafeName} ({string.Join(", ", rewrites)})");
                    note = note + "; viết lại: " + string.Join(", ", rewrites);
                }
            }
            else
            {
                comboDef.Items.Add(new ComboItem(comboSafeName, 1.0));
            }
            model.Combos.Add(comboDef);
            sources.Add($"{comboSafeName} <- combo {output.Name} ({note})");
        }
        if (rewrittenCombos.Count > 0)
        {
            notes.Add("Combo gốc viết lại sang combo _ENV: " +
                string.Join("; ", rewrittenCombos) + ".");
        }

        var sortedJointNames = jointsXyz.Keys.OrderBy(n => n, JointNameComparer.Instance).ToList();
        foreach (string name in sortedJointNames)
        {
            var (x, y, _) = jointsXyz[name];
            bool[]? restraint = restraintMap.TryGetValue(name, out var r) ? r : null;
            if (restraint is null)
            {
                warnings.Add($"Joint {name}: không có thông tin gối — mặc định Yes cả 6 DOF.");
            }
            model.Points.Add(new PointDef { Name = name, X = x, Y = y, Restraint = restraint });
        }

        foreach (var ld in flipped)
        {
            model.PointLoads.Add(new PointLoad
            {
                Point = ld.Joint,
                Pattern = ld.Pattern,
                Fx = ld.Fx,
                Fy = ld.Fy,
                Fz = ld.Fz,
                Mx = ld.Mx,
                My = ld.My,
                Mz = ld.Mz,
            });
        }

        var info = new BuildInfo
        {
            FlipSign = flipSign,
            SafeVersion = safeVersion,
            Units = "kN, m, C",
        };
        foreach (var kv in nameMap)
        {
            info.NameMap[kv.Key] = kv.Value;
        }
        info.Sources.AddRange(sources);
        foreach (var ld in flipped)
        {
            info.Loads.Add((ld.Pattern, ld.Fz));
        }
        foreach (var kv in sapSums)
        {
            info.SapSums[kv.Key] = kv.Value;
        }
        info.Warnings.AddRange(warnings);
        info.Notes.AddRange(notes);
        foreach (var kv in splits)
        {
            info.Splits[kv.Key] = kv.Value;
        }

        return new BuildResult { Model = model, Info = info };
    }
}
