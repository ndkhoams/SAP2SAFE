using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;

namespace Sap2Safe.Core;

/// <summary>Sort key khớp Python: tên số (kể cả âm) xếp trước theo giá trị số, tên không số xếp sau theo Ordinal.</summary>
internal sealed class JointNameComparer : IComparer<string>
{
    public static readonly JointNameComparer Instance = new JointNameComparer();

    public static bool TryNumeric(string name, out long value)
    {
        value = 0;
        if (string.IsNullOrEmpty(name))
        {
            return false;
        }
        string digits = name.StartsWith("-", StringComparison.Ordinal) ? name.Substring(1) : name;
        if (digits.Length == 0)
        {
            return false;
        }
        foreach (char c in digits)
        {
            if (c < '0' || c > '9')
            {
                return false;
            }
        }
        return long.TryParse(name, NumberStyles.Integer, CultureInfo.InvariantCulture, out value);
    }

    public int Compare(string? x, string? y)
    {
        string a = x ?? "";
        string b = y ?? "";
        bool aNum = TryNumeric(a, out long av);
        bool bNum = TryNumeric(b, out long bv);
        if (aNum && bNum)
        {
            return av.CompareTo(bv);
        }
        if (aNum)
        {
            return -1;
        }
        if (bNum)
        {
            return 1;
        }
        return string.CompareOrdinal(a, b);
    }
}

public sealed class WriteCounts
{
    public int Points;
    public int Patterns;
    public int Cases;
    public int Combos;
    public int PointLoads;
    public string Path { get; set; } = "";
}

public static class SfWriter
{
    public static readonly string[] ExpectedTables = {
        "JOINT ASSIGNMENTS - RESTRAINTS",
        "JOINT LOADS ASSIGNMENTS - FORCE",
        "LOAD CASE DEFINITIONS - LINEAR STATIC",
        "LOAD COMBINATION DEFINITIONS",
        "LOAD PATTERN DEFINITIONS",
        "POINT OBJECT CONNECTIVITY",
        "PROGRAM CONTROL",
    };

    private static readonly Dictionary<string, string> SapDesignTypeToSafe =
        new Dictionary<string, string>
        {
            { "Dead", "Dead" },
            { "Super Dead", "Super Dead" },
            { "Live", "Live" },
            { "Wind", "Wind" },
            { "Quake", "Seismic" },
            { "Seismic", "Seismic" },
            { "Other", "Other" },
        };

    public static string SafePatternType(string? sapDesignType)
    {
        string key = (sapDesignType ?? "").Trim();
        return SapDesignTypeToSafe.TryGetValue(key, out string? mapped) ? mapped : "Other";
    }

    private static string Guid() => System.Guid.NewGuid().ToString();

    private static string CaseSortKey(string name) => name.Replace("+", "\uffff");

    public static string HeaderLine(string path)
    {
        var now = DateTime.Now;
        int hour = now.Hour % 12;
        if (hour == 0)
        {
            hour = 12;
        }
        string ampm = now.Hour < 12 ? "am" : "pm";
        string baseName = Path.GetFileName(path);
        return string.Format(
            CultureInfo.InvariantCulture,
            "File {0} was saved on {1}/{2:00}/{3:00} at {4}:{5:00}:{6:00} {7}",
            baseName, now.Year, now.Month, now.Day, hour, now.Minute, now.Second, ampm);
    }

    public static List<(string Name, List<string> Rows)> BuildTables(F2kModel model)
    {
        var tables = new List<(string, List<string>)>();

        // (1) JOINT ASSIGNMENTS - RESTRAINTS
        var rows = new List<string>();
        foreach (var p in model.Points.OrderBy(p => p.Name, JointNameComparer.Instance))
        {
            bool[] r = p.Restraint ?? new[] { true, true, true, true, true, true };
            rows.Add(CsiText.FormatKvLine(new KeyValuePair<string, object?>[]
            {
                new KeyValuePair<string, object?>("UniqueName", p.Name),
                new KeyValuePair<string, object?>("UX", r[0]),
                new KeyValuePair<string, object?>("UY", r[1]),
                new KeyValuePair<string, object?>("UZ", r[2]),
                new KeyValuePair<string, object?>("RX", r[3]),
                new KeyValuePair<string, object?>("RY", r[4]),
                new KeyValuePair<string, object?>("RZ", r[5]),
            }));
        }
        tables.Add(("JOINT ASSIGNMENTS - RESTRAINTS", rows));

        // (2) JOINT LOADS ASSIGNMENTS - FORCE
        var patternOrder = new List<string>();
        foreach (var p in model.Patterns)
        {
            patternOrder.Add(p.Name);
        }
        var orderIndex = new Dictionary<string, int>();
        for (int i = 0; i < patternOrder.Count; i++)
        {
            orderIndex[patternOrder[i]] = i;
        }
        var loads = model.PointLoads
            .OrderBy(ld => orderIndex.TryGetValue(ld.Pattern, out int idx) ? idx : 999)
            .ThenBy(ld => ld.Point, JointNameComparer.Instance)
            .ToList();
        rows = new List<string>();
        foreach (var ld in loads)
        {
            rows.Add(CsiText.FormatKvLine(new KeyValuePair<string, object?>[]
            {
                new KeyValuePair<string, object?>("UniqueName", ld.Point),
                new KeyValuePair<string, object?>("Load Pattern", ld.Pattern),
                new KeyValuePair<string, object?>("FX", ld.Fx),
                new KeyValuePair<string, object?>("FY", ld.Fy),
                new KeyValuePair<string, object?>("FZ", ld.Fz),
                new KeyValuePair<string, object?>("MX", ld.Mx),
                new KeyValuePair<string, object?>("MY", ld.My),
                new KeyValuePair<string, object?>("MZ", ld.Mz),
                new KeyValuePair<string, object?>("X Dimension", 0),
                new KeyValuePair<string, object?>("Y Dimension", 0),
                new KeyValuePair<string, object?>("GUID", Guid()),
            }));
        }
        tables.Add(("JOINT LOADS ASSIGNMENTS - FORCE", rows));

        // (3) LOAD CASE DEFINITIONS - LINEAR STATIC
        rows = new List<string>();
        foreach (var c in model.Cases.OrderBy(c => CaseSortKey(c.Name), StringComparer.Ordinal))
        {
            string name = c.Name;
            rows.Add(CsiText.FormatKvLine(new KeyValuePair<string, object?>[]
            {
                new KeyValuePair<string, object?>("Name", name),
                new KeyValuePair<string, object?>("Exclude Group", "None"),
                new KeyValuePair<string, object?>("Initial Condition", "Nonlinear Case"),
                new KeyValuePair<string, object?>("Nonlinear Case", "None"),
                new KeyValuePair<string, object?>("Load Type", "Load"),
                new KeyValuePair<string, object?>("Load Name", name),
                new KeyValuePair<string, object?>("Load SF", 1),
                new KeyValuePair<string, object?>("Design Type", "Program Determined"),
                new KeyValuePair<string, object?>("GUID", Guid()),
            }));
            rows.Add(CsiText.FormatKvLine(new KeyValuePair<string, object?>[]
            {
                new KeyValuePair<string, object?>("Name", name),
                new KeyValuePair<string, object?>("Load Type", "Load"),
                new KeyValuePair<string, object?>("Load Name", name + "_ABOVE"),
                new KeyValuePair<string, object?>("Load SF", 1),
            }));
        }
        tables.Add(("LOAD CASE DEFINITIONS - LINEAR STATIC", rows));

        // (4) LOAD COMBINATION DEFINITIONS
        rows = new List<string>();
        foreach (var combo in model.Combos)
        {
            if (combo.Items.Count == 0)
            {
                continue;
            }
            var first = combo.Items[0];
            rows.Add(CsiText.FormatKvLine(new KeyValuePair<string, object?>[]
            {
                new KeyValuePair<string, object?>("Name", combo.Name),
                new KeyValuePair<string, object?>("Type", combo.Type ?? "Linear Add"),
                new KeyValuePair<string, object?>("Is Auto", "No"),
                new KeyValuePair<string, object?>("Load Name", first.Case),
                new KeyValuePair<string, object?>("SF", first.Sf),
                new KeyValuePair<string, object?>("GUID", Guid()),
            }));
            for (int i = 1; i < combo.Items.Count; i++)
            {
                var item = combo.Items[i];
                rows.Add(CsiText.FormatKvLine(new KeyValuePair<string, object?>[]
                {
                    new KeyValuePair<string, object?>("Name", combo.Name),
                    new KeyValuePair<string, object?>("Load Name", item.Case),
                    new KeyValuePair<string, object?>("SF", item.Sf),
                }));
            }
        }
        tables.Add(("LOAD COMBINATION DEFINITIONS", rows));

        // (5) LOAD PATTERN DEFINITIONS
        rows = new List<string>();
        foreach (var p in model.Patterns)
        {
            rows.Add(CsiText.FormatKvLine(new KeyValuePair<string, object?>[]
            {
                new KeyValuePair<string, object?>("Name", p.Name),
                new KeyValuePair<string, object?>("Is Auto Load", "No"),
                new KeyValuePair<string, object?>("Type", p.Type ?? "Other"),
                new KeyValuePair<string, object?>("Self Weight Multiplier", p.SelfWtMult),
                new KeyValuePair<string, object?>("GUID", Guid()),
            }));
            rows.Add(CsiText.FormatKvLine(new KeyValuePair<string, object?>[]
            {
                new KeyValuePair<string, object?>("Name", p.Name + "_ABOVE"),
                new KeyValuePair<string, object?>("Is Auto Load", "No"),
                new KeyValuePair<string, object?>("Type", p.Type ?? "Other"),
                new KeyValuePair<string, object?>("Self Weight Multiplier", 0),
                new KeyValuePair<string, object?>("GUID", Guid()),
            }));
        }
        tables.Add(("LOAD PATTERN DEFINITIONS", rows));

        // (6) POINT OBJECT CONNECTIVITY
        rows = new List<string>();
        foreach (var p in model.Points.OrderBy(p => p.Name, JointNameComparer.Instance))
        {
            rows.Add(CsiText.FormatKvLine(new KeyValuePair<string, object?>[]
            {
                new KeyValuePair<string, object?>("UniqueName", p.Name),
                new KeyValuePair<string, object?>("Is Auto Point", "No"),
                new KeyValuePair<string, object?>("IsSpecial", "Yes"),
                new KeyValuePair<string, object?>("X", p.X),
                new KeyValuePair<string, object?>("Y", p.Y),
                new KeyValuePair<string, object?>("Z", 0),
                new KeyValuePair<string, object?>("GUID", Guid()),
            }));
        }
        tables.Add(("POINT OBJECT CONNECTIVITY", rows));

        // (7) PROGRAM CONTROL
        rows = new List<string>
        {
            CsiText.FormatKvLine(new KeyValuePair<string, object?>[]
            {
                new KeyValuePair<string, object?>("ProgramName", "SAFE"),
                new KeyValuePair<string, object?>("Version", model.SafeVersion),
                new KeyValuePair<string, object?>("CurrUnits", "kN, m, C"),
                new KeyValuePair<string, object?>("CompBmCode", "AISC 360-16"),
                new KeyValuePair<string, object?>("ConcFrmCode", "ACI 318-14"),
                new KeyValuePair<string, object?>("ConcSlbCode", "ACI 318-14"),
            }),
        };
        tables.Add(("PROGRAM CONTROL", rows));

        return tables;
    }

    public static WriteCounts WriteSf(string path, F2kModel model)
    {
        CsiText.WriteCsiTables(path, HeaderLine(path), BuildTables(model));
        return new WriteCounts
        {
            Points = model.Points.Count,
            Patterns = model.Patterns.Count,
            Cases = model.Cases.Count,
            Combos = model.Combos.Count,
            PointLoads = model.PointLoads.Count,
            Path = path,
        };
    }

    public static WriteCounts WriteF2k(string path, F2kModel model)
    {
        return WriteSf(path, model);
    }

    public static List<string> BuildLines(F2kModel model)
    {
        var lines = new List<string> { HeaderLine("SAP2SAFE.f2k"), " " };
        foreach (var (name, rows) in BuildTables(model))
        {
            lines.Add("TABLE:  \"" + name + "\"");
            lines.AddRange(rows);
            lines.Add(" ");
        }
        return lines;
    }
}
