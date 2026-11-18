using System;
using System.Collections.Generic;
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

        var (frozen, warnings) = StepSelect.FreezeReactions(rows, stepMode, specific, jointsXy);
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

        var model = new F2kModel { SafeVersion = safeVersion };
        foreach (string p in patternNames)
        {
            string bas = BaseOf(p);
            if (infoMap.TryGetValue(bas, out var infoP))
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
        foreach (var output in selOutputs)
        {
            if (output.Kind != "combo")
            {
                string safeName;
                if (!nameMap.TryGetValue(output.Name, out safeName))
                {
                    safeName = output.Name;
                }
                sources.Add($"{safeName} <- case {output.Name} (frozen, {(output.IsNonlinear ? "nonlinear" : "linear")})");
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
                foreach (var item in items)
                {
                    string mapped;
                    if (!nameMap.TryGetValue(item.Case, out mapped))
                    {
                        mapped = item.Case;
                    }
                    comboDef.Items.Add(new ComboItem(mapped, item.Sf));
                }
            }
            else
            {
                comboDef.Items.Add(new ComboItem(comboSafeName, 1.0));
            }
            model.Combos.Add(comboDef);
            sources.Add($"{comboSafeName} <- combo {output.Name} ({note})");
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

        return new BuildResult { Model = model, Info = info };
    }
}
