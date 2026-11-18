using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace Sap2Safe.Core;

public static class Mapping
{
    public const int MaxSafeNameLen = 64;

    private static readonly Regex NewlineRegex = new Regex(
        "[\\r\\n]+",
        RegexOptions.Compiled);

    public static string SanitizeName(string name, int maxLen = 64)
    {
        string cleaned = (name ?? "").Trim().Replace("=", "_");
        cleaned = NewlineRegex.Replace(cleaned, " ").Trim();
        if (cleaned.Length == 0)
        {
            cleaned = "LOAD";
        }
        string cut = cleaned.Length > maxLen ? cleaned.Substring(0, maxLen) : cleaned;
        return cut.Length == 0 ? "LOAD" : cut;
    }

    public static Dictionary<string, string> BuildNameMap(IEnumerable<SapOutput> outputs)
    {
        var mapping = new Dictionary<string, string>();
        var used = new HashSet<string>();
        foreach (var output in outputs)
        {
            string bas = SanitizeName(output.Name);
            string candidate = bas;
            int i = 2;
            while (used.Contains(candidate))
            {
                string suffix = "_" + i.ToString(System.Globalization.CultureInfo.InvariantCulture);
                int keep = MaxSafeNameLen - suffix.Length;
                string truncated = bas.Length > keep ? bas.Substring(0, keep) : bas;
                candidate = (truncated + suffix).TrimEnd('_');
                i++;
            }
            used.Add(candidate);
            mapping[output.Name] = candidate;
        }
        return mapping;
    }

    public static (string Mode, List<ComboItem> Items, string Note) DecideComboMapping(
        SapOutput output, Dictionary<string, SapOutput> outputsByName)
    {
        if (output.Kind == "case")
        {
            return ("standalone", new List<ComboItem> { new ComboItem(output.Name, 1.0) }, "case đơn — frozen");
        }
        foreach (var comp in output.Components)
        {
            if (!outputsByName.ContainsKey(comp.Case))
            {
                return (
                    "standalone",
                    new List<ComboItem> { new ComboItem(output.Name, 1.0) },
                    $"combo chứa {comp.Case} không có trong model — frozen để an toàn");
            }
        }
        bool hasNonlinear = false;
        foreach (var comp in output.Components)
        {
            var target = outputsByName[comp.Case];
            if (target.Kind == "case" && target.IsNonlinear)
            {
                hasNonlinear = true;
                break;
            }
        }
        string note = "copy y hệt định nghĩa SAP — SAFE tự tính từ case đã đóng băng";
        if (hasNonlinear)
        {
            note += " (CẢNH BÁO: combo chứa case nonlinear — SAFE cộng tuyến tính các vector đã đóng băng, không phải chạy lại phi tuyến)";
        }
        var items = new List<ComboItem>();
        foreach (var comp in output.Components)
        {
            items.Add(new ComboItem(comp.Case, comp.Sf));
        }
        return ("rebuild", items, note);
    }

    public static List<FrozenLoad> ApplySignFlip(IEnumerable<FrozenLoad> loads, bool flip = true)
    {
        var source = new List<FrozenLoad>(loads);
        if (!flip)
        {
            return source;
        }
        var flipped = new List<FrozenLoad>();
        foreach (var ld in source)
        {
            flipped.Add(new FrozenLoad
            {
                Joint = ld.Joint,
                X = ld.X,
                Y = ld.Y,
                Pattern = ld.Pattern,
                Fx = -ld.Fx,
                Fy = -ld.Fy,
                Fz = -ld.Fz,
                Mx = -ld.Mx,
                My = -ld.My,
                Mz = -ld.Mz,
                SourceStep = ld.SourceStep,
            });
        }
        return flipped;
    }
}
