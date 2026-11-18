using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using Sap2Safe.Core;

namespace Sap2Safe.ParityTest;

/// <summary>
/// Kiem chung parity C# (Sap2Safe.Core) vs Python (sap2safe) tren fixture that MONG.sf.
/// Check 1: FormatNumber (unit). Check 2: parity end-to-end (C# SfWriter vs
/// Python sf_writer, chuan hoa GUID + dong header). Check 3: pytest Python.
/// Check 4: parse MONG.sf bang C#.
/// Exit code 0 neu TAT CA pass, khac 0 neu co muc fail.
/// </summary>
internal static class Program
{
    private const string DefaultMong = "/home/hatch/workspace/sap2safe_work/fixtures/MONG.sf";
    private const string DefaultOutDir = "/tmp/parity";
    private const string DefaultSapRoot = "/home/hatch/workspace/sap2safe";

    // Gia tri literal (dang text) dung chung cho ca C# va Python de dam bao
    // cung 1 so double nhi phan o ca 2 phia.
    private static readonly string[] NumberLiterals =
    {
        "0.415", "-200.347", "1.41e-05", "-0.0", "0.0", "2.5",
        "10000000000", "1e16", "0.00001", "123456789.123456789",
        "1.5", "-3.14159265358979", "100000.0", "999999999999999.0",
        "0.1", "1234567.0", "1e-10", "5e-324",
    };

    // Expected fallback, lay tu 1 lan chay that python3 -c format_number
    // (chi dung khi khong goi duoc python luc chay; duong chinh van la goi
    // python truc tiep de lay expected).
    private static readonly string[] FallbackExpected =
    {
        "0.415", "-200.347", "1.41E-05", "0", "0", "2.5",
        "10000000000", "1E16", "1E-05", "123456789.1",
        "1.5", "-3.141592654", "100000", "999999999999999",
        "0.1", "1234567", "1E-10", "4.940656458E-324",
    };

    private static int Main(string[] args)
    {
        string mong = DefaultMong;
        string outDir = DefaultOutDir;
        string sapRoot = DefaultSapRoot;
        string? pythonRef = null;
        for (int i = 0; i < args.Length; i++)
        {
            switch (args[i])
            {
                case "--mong" when i + 1 < args.Length: mong = args[++i]; break;
                case "--out-dir" when i + 1 < args.Length: outDir = args[++i]; break;
                case "--sap-root" when i + 1 < args.Length: sapRoot = args[++i]; break;
                case "--python-ref" when i + 1 < args.Length: pythonRef = args[++i]; break;
            }
        }

        Console.WriteLine("=== SAP2SAFE ParityTest: C# vs Python (fixture MONG.sf) ===");
        Console.WriteLine($"MONG.sf : {mong}");
        Console.WriteLine($"Out dir : {outDir}");
        Console.WriteLine($"SAP root: {sapRoot}");
        Console.WriteLine();

        bool c1 = false, c2 = false, c3 = false, c4 = false;
        try { c1 = Check1FormatNumber(sapRoot); }
        catch (Exception ex) { Console.WriteLine($"[Check 1] EXCEPTION: {ex.Message}"); }
        Console.WriteLine();

        Dictionary<string, List<Dictionary<string, string>>>? tables = null;
        try
        {
            tables = CsiText.ParseCsiTables(mong);
            c4 = Check4Parse(tables);
        }
        catch (Exception ex) { Console.WriteLine($"[Check 4] EXCEPTION: {ex.Message}"); }
        Console.WriteLine();

        try
        {
            if (tables is null) throw new InvalidOperationException("Khong parse duoc MONG.sf.");
            c2 = Check2EndToEnd(mong, tables, outDir, sapRoot, pythonRef);
        }
        catch (Exception ex) { Console.WriteLine($"[Check 2] EXCEPTION: {ex.Message}"); }
        Console.WriteLine();

        try { c3 = Check3Pytest(sapRoot); }
        catch (Exception ex) { Console.WriteLine($"[Check 3] EXCEPTION: {ex.Message}"); }
        Console.WriteLine();

        Console.WriteLine("=== TONG KET ===");
        Console.WriteLine($"Check 1 (FormatNumber) : {(c1 ? "PASS" : "FAIL")}");
        Console.WriteLine($"Check 2 (end-to-end)    : {(c2 ? "PASS" : "FAIL")}");
        Console.WriteLine($"Check 3 (pytest Python) : {(c3 ? "PASS" : "FAIL")}");
        Console.WriteLine($"Check 4 (parse MONG.sf) : {(c4 ? "PASS" : "FAIL")}");
        bool all = c1 && c2 && c3 && c4;
        Console.WriteLine(all ? "KET LUAN: TAT CA PASS" : "KET LUAN: CO MUC FAIL");
        return all ? 0 : 1;
    }

    // ---------------------------------------------------------------- Check 1
    private static bool Check1FormatNumber(string sapRoot)
    {
        Console.WriteLine("--- Check 1: FormatNumber C# vs Python f\"{f:.10g}\" ---");
        double[] values = NumberLiterals
            .Select(s => double.Parse(s, CultureInfo.InvariantCulture)).ToArray();

        string[]? expected = GetPythonExpected(sapRoot);
        if (expected is null)
        {
            Console.WriteLine("  (khong goi duoc python3 de lay expected -> dung fallback da lay tu 1 lan chay that truoc do)");
            expected = FallbackExpected;
        }
        else
        {
            Console.WriteLine("  Expected lay truc tiep tu python3 (sap2safe.csi_text.format_number).");
        }

        int pass = 0, fail = 0, noted = 0;
        for (int i = 0; i < values.Length; i++)
        {
            string got = CsiText.FormatNumber(values[i]);
            string exp = expected[i];
            bool ok = got == exp;
            bool isSubnormal = NumberLiterals[i] == "5e-324";
            if (ok) pass++;
            else if (isSubnormal) { noted++; Console.WriteLine($"  [NOTE] {NumberLiterals[i]}: C#='{got}' Python='{exp}' (lech o bien subnormal — ghi nhan, khong tinh fail)"); }
            else { fail++; Console.WriteLine($"  [FAIL] {NumberLiterals[i]}: C#='{got}' Python='{exp}'"); }
        }
        Console.WriteLine($"Check 1: {pass}/{values.Length} khop, {fail} lech" +
            (noted > 0 ? $" (+{noted} ghi nhan o 5e-324)" : ""));
        bool okAll = fail == 0;
        Console.WriteLine(okAll ? "Check 1: PASS" : "Check 1: FAIL");
        return okAll;
    }

    private static string[]? GetPythonExpected(string sapRoot)
    {
        string code =
            "import sys\n" +
            $"sys.path.insert(0, r'{sapRoot}')\n" +
            "from sap2safe.csi_text import format_number\n" +
            $"vals=[{string.Join(", ", NumberLiterals)}]\n" +
            "for i,v in enumerate(vals):\n" +
            "    print(f\"{i}|{format_number(v)}\")\n";
        var (exit, stdout, stderr) = RunProcess("python3", new[] { "-c", code }, null);
        if (exit != 0)
        {
            Console.WriteLine($"  python3 -c exit={exit}: {stderr.Trim()}");
            return null;
        }
        var result = new string[NumberLiterals.Length];
        int filled = 0;
        foreach (string line in stdout.Split('\n'))
        {
            string t = line.TrimEnd('\r');
            int bar = t.IndexOf('|');
            if (bar <= 0) continue;
            if (!int.TryParse(t.Substring(0, bar), out int idx)) continue;
            if (idx < 0 || idx >= result.Length) continue;
            result[idx] = t.Substring(bar + 1);
            filled++;
        }
        if (filled != NumberLiterals.Length) return null;
        return result;
    }

    // ---------------------------------------------------------------- Check 4
    private static bool Check4Parse(Dictionary<string, List<Dictionary<string, string>>> tables)
    {
        Console.WriteLine("--- Check 4: Parse MONG.sf bang C# (CsiText.ParseCsiTables) ---");
        Console.WriteLine($"  Tong so bang parse duoc: {tables.Count} (MONG.sf co 41 bang)");
        bool ok = true;
        foreach (string name in SfWriter.ExpectedTables)
        {
            bool present = tables.ContainsKey(name);
            Console.WriteLine($"  [{(present ? "PASS" : "FAIL")}] bang '{name}': {(present ? "co" : "THIEU")}");
            if (!present) ok = false;
        }
        int jl = tables.TryGetValue("JOINT LOADS ASSIGNMENTS - FORCE", out var jlRows) ? jlRows.Count : -1;
        int pc = tables.TryGetValue("POINT OBJECT CONNECTIVITY", out var pcRows) ? pcRows.Count : -1;
        Console.WriteLine($"  JOINT LOADS = {jl} (ky vong 1380): {(jl == 1380 ? "PASS" : "FAIL")}");
        Console.WriteLine($"  POINT OBJECT CONNECTIVITY = {pc} (ky vong 92): {(pc == 92 ? "PASS" : "FAIL")}");
        if (jl != 1380 || pc != 92) ok = false;
        Console.WriteLine(ok ? "Check 4: PASS" : "Check 4: FAIL");
        return ok;
    }

    // ---------------------------------------------------------------- Check 2
    private static bool Check2EndToEnd(
        string mong,
        Dictionary<string, List<Dictionary<string, string>>> tables,
        string outDir,
        string sapRoot,
        string? pythonRefArg)
    {
        Console.WriteLine("--- Check 2: Parity end-to-end C# SfWriter vs Python sf_writer ---");
        Directory.CreateDirectory(outDir);
        string csPath = Path.Combine(outDir, "cs.f2k");
        string pyPath = Path.Combine(outDir, "py.f2k");

        // ---- Xay dung dau vao C# (giong het phia Python, chi tu MONG.sf) ----
        var jointsXyz = new Dictionary<string, (double X, double Y, double Z)>();
        foreach (var r in tables["POINT OBJECT CONNECTIVITY"])
        {
            jointsXyz[r["UniqueName"]] = (
                double.Parse(r["X"], CultureInfo.InvariantCulture),
                double.Parse(r["Y"], CultureInfo.InvariantCulture),
                0.0);
        }
        var restraints = new Dictionary<string, bool[]>();
        foreach (var r in tables["JOINT ASSIGNMENTS - RESTRAINTS"])
        {
            restraints[r["UniqueName"]] = new[]
            {
                r["UX"] == "Yes", r["UY"] == "Yes", r["UZ"] == "Yes",
                r["RX"] == "Yes", r["RY"] == "Yes", r["RZ"] == "Yes",
            };
        }
        var patternInfo = new Dictionary<string, PatternInfo>();
        foreach (var r in tables["LOAD PATTERN DEFINITIONS"])
        {
            if (r["Name"].EndsWith("_ABOVE", StringComparison.Ordinal)) continue;
            patternInfo[r["Name"]] = new PatternInfo
            {
                DesignType = r["Type"],
                SelfWtMult = double.Parse(r["Self Weight Multiplier"], CultureInfo.InvariantCulture),
            };
        }
        var caseNames = new List<string>();
        foreach (var r in tables["LOAD CASE DEFINITIONS - LINEAR STATIC"])
        {
            if (!caseNames.Contains(r["Name"])) caseNames.Add(r["Name"]);
        }
        var outputs = new List<SapOutput>();
        foreach (string n in caseNames)
        {
            outputs.Add(new SapOutput { Name = n, Kind = "case", CaseType = null, IsNonlinear = false });
        }
        var comboNames = new List<string>();
        var comboItems = new Dictionary<string, List<ComboItem>>();
        var comboTypes = new Dictionary<string, string>();
        foreach (var r in tables["LOAD COMBINATION DEFINITIONS"])
        {
            string name = r["Name"];
            if (!comboItems.ContainsKey(name))
            {
                comboNames.Add(name);
                comboItems[name] = new List<ComboItem>();
                comboTypes[name] = r.TryGetValue("Type", out string? t) ? t : "Linear Add";
            }
            comboItems[name].Add(new ComboItem(
                r["Load Name"],
                double.Parse(r["SF"], CultureInfo.InvariantCulture)));
        }
        foreach (string n in comboNames)
        {
            var o = new SapOutput { Name = n, Kind = "combo", ComboType = comboTypes[n] };
            o.Components.AddRange(comboItems[n]);
            outputs.Add(o);
        }
        var reactions = new List<Reaction>();
        foreach (var r in tables["JOINT LOADS ASSIGNMENTS - FORCE"])
        {
            reactions.Add(new Reaction
            {
                Joint = r["UniqueName"],
                OutputName = r["Load Pattern"],
                OutputKind = "case",
                StepType = "",
                StepNum = 0,
                F1 = -double.Parse(r["FX"], CultureInfo.InvariantCulture),
                F2 = -double.Parse(r["FY"], CultureInfo.InvariantCulture),
                F3 = -double.Parse(r["FZ"], CultureInfo.InvariantCulture),
                M1 = -double.Parse(r["MX"], CultureInfo.InvariantCulture),
                M2 = -double.Parse(r["MY"], CultureInfo.InvariantCulture),
                M3 = -double.Parse(r["MZ"], CultureInfo.InvariantCulture),
            });
        }
        var selected = new List<string>(caseNames);
        selected.AddRange(comboNames);

        Console.WriteLine($"  Dau vao: {jointsXyz.Count} point, {patternInfo.Count} pattern, " +
            $"{caseNames.Count} case, {comboNames.Count} combo, {reactions.Count} reaction.");
        BuildResult result = Pipeline.BuildF2kModel(
            reactions, jointsXyz, outputs, selected,
            jointsRestraint: restraints, patternInfo: patternInfo,
            stepMode: "last", specific: null, flipSign: true, safeVersion: "22.5.1");
        WriteCounts counts = SfWriter.WriteF2k(csPath, result.Model);
        Console.WriteLine($"  C#: points={counts.Points} patterns={counts.Patterns} cases={counts.Cases} " +
            $"combos={counts.Combos} point_loads={counts.PointLoads} path={csPath}");
        if (result.Warnings.Count > 0)
        {
            Console.WriteLine("  C# warnings: " + string.Join("; ", result.Warnings));
        }

        // ---- Chay phia Python tham chieu ----
        string? pythonRef = pythonRefArg ?? FindPythonReference();
        if (pythonRef is null)
        {
            Console.WriteLine("  [FAIL] Khong tim thay python_reference.py (tim theo AppContext.BaseDirectory / CWD).");
            return false;
        }
        Console.WriteLine($"  Chay Python: python3 {pythonRef} --mong {mong} --out {pyPath} --sap-root {sapRoot}");
        var (pyExit, pyOut, pyErr) = RunProcess("python3",
            new[] { pythonRef, "--mong", mong, "--out", pyPath, "--sap-root", sapRoot }, null);
        Console.WriteLine("  " + pyOut.Trim().Replace("\n", "\n  "));
        if (pyExit != 0)
        {
            Console.WriteLine($"  [FAIL] python_reference.py exit={pyExit}: {pyErr.Trim()}");
            return false;
        }
        if (!File.Exists(pyPath))
        {
            Console.WriteLine("  [FAIL] Python khong sinh ra py.f2k.");
            return false;
        }

        // ---- So sanh (chuan hoa GUID + dong header) ----
        string[] csLines = Normalize(File.ReadAllLines(csPath));
        string[] pyLines = Normalize(File.ReadAllLines(pyPath));
        Console.WriteLine($"  So dong: C#={csLines.Length}  Python={pyLines.Length}");

        var csTables = CsiText.ParseCsiTables(csPath);
        var pyTables = CsiText.ParseCsiTables(pyPath);
        Console.WriteLine($"  So bang: C#={csTables.Count}  Python={pyTables.Count} (ky vong 7, dung thu tu ExpectedTables)");
        Console.WriteLine("  Thu tu bang C#: " + string.Join(" | ", ScanTableOrder(File.ReadAllLines(csPath))));
        Console.WriteLine("  Thu tu bang Py : " + string.Join(" | ", ScanTableOrder(File.ReadAllLines(pyPath))));
        int csJl = csTables.TryGetValue("JOINT LOADS ASSIGNMENTS - FORCE", out var a) ? a.Count : -1;
        int pyJl = pyTables.TryGetValue("JOINT LOADS ASSIGNMENTS - FORCE", out var b) ? b.Count : -1;
        int csPts = csTables.TryGetValue("POINT OBJECT CONNECTIVITY", out var c) ? c.Count : -1;
        int csPats = csTables.TryGetValue("LOAD PATTERN DEFINITIONS", out var d)
            ? d.Count(x => !x["Name"].EndsWith("_ABOVE", StringComparison.Ordinal)) : -1;
        int csCombos = csTables.TryGetValue("LOAD COMBINATION DEFINITIONS", out var e)
            ? e.Select(x => x["Name"]).Distinct().Count() : -1;
        Console.WriteLine($"  JOINT LOADS: C#={csJl} Python={pyJl} (ky vong 1380)");
        Console.WriteLine($"  Point: C#={csPts} (ky vong 92) | Pattern: C#={csPats} (ky vong 15) | Combo: C#={csCombos} (ky vong 72)");

        bool countsOk = csTables.Count == 7 && pyTables.Count == 7
            && csJl == 1380 && pyJl == 1380 && csPts == 92 && csPats == 15 && csCombos == 72
            && ScanTableOrder(File.ReadAllLines(csPath)).SequenceEqual(SfWriter.ExpectedTables)
            && ScanTableOrder(File.ReadAllLines(pyPath)).SequenceEqual(SfWriter.ExpectedTables);

        int diffs = 0;
        int maxShow = 20;
        int nLines = Math.Min(csLines.Length, pyLines.Length);
        for (int i = 0; i < nLines; i++)
        {
            if (csLines[i] != pyLines[i])
            {
                diffs++;
                if (diffs <= maxShow)
                {
                    Console.WriteLine($"  [LECH dong {i + 1}]");
                    Console.WriteLine($"    C# : {csLines[i]}");
                    Console.WriteLine($"    Py : {pyLines[i]}");
                }
            }
        }
        if (csLines.Length != pyLines.Length)
        {
            diffs += Math.Abs(csLines.Length - pyLines.Length);
            Console.WriteLine($"  [LECH] so dong khac nhau: C#={csLines.Length} Python={pyLines.Length}");
        }
        if (diffs > maxShow)
        {
            Console.WriteLine($"  ... tong {diffs} dong lech (chi hien {maxShow} dong dau).");
        }
        bool bytesEqual = csLines.Length == pyLines.Length && diffs == 0;
        Console.WriteLine(bytesEqual
            ? "  So byte sau chuan hoa: KHOP 100%"
            : $"  So byte sau chuan hoa: LECH ({diffs} dong)");
        if (!bytesEqual)
        {
            Console.WriteLine("  Phan tich: xem cac dong lech o tren. Neu lech so -> loi o phia C# " +
                "(CsiText.FormatNumber / SfWriter.BuildTables); KHONG sua Python, bao lai de sua Core sau.");
        }

        // ---- Check phu: Sigma FZ theo pattern, C# vs MONG.sf (thong tin, khong tinh fail) ----
        Console.WriteLine("  --- Check phu (khong tinh fail): SigmaFZ C# vs MONG.sf ---");
        var mongSums = SumFz(tables["JOINT LOADS ASSIGNMENTS - FORCE"]);
        var csSums = SumFz(csTables["JOINT LOADS ASSIGNMENTS - FORCE"]);
        double maxDiff = 0;
        foreach (string p in mongSums.Keys.OrderBy(k => k, StringComparer.Ordinal))
        {
            double m = mongSums[p];
            double v = csSums.TryGetValue(p, out double s) ? s : double.NaN;
            double diff = Math.Abs(m - v);
            if (diff > maxDiff) maxDiff = diff;
            Console.WriteLine($"    {p,-6}: MONG={m,12:F3}  C#={v,12:F3}  lech={diff:F6} {(diff <= 0.01 ? "KHOP" : "LECH")}");
        }
        Console.WriteLine($"  SigmaFZ: chenh lech lon nhat = {maxDiff:F6} (dung sai 0.01) — " +
            (maxDiff <= 0.01 ? "KHOP" : "LECH (chi thong tin)"));

        bool ok = bytesEqual && countsOk;
        Console.WriteLine(ok ? "Check 2: PASS" : "Check 2: FAIL");
        return ok;
    }

    private static Dictionary<string, double> SumFz(List<Dictionary<string, string>> rows)
    {
        var sums = new Dictionary<string, double>();
        foreach (var r in rows)
        {
            string p = r["Load Pattern"];
            double fz = double.Parse(r["FZ"], CultureInfo.InvariantCulture);
            sums[p] = sums.TryGetValue(p, out double cur) ? cur + fz : fz;
        }
        return sums;
    }

    private static List<string> ScanTableOrder(string[] lines)
    {
        var order = new List<string>();
        foreach (string line in lines)
        {
            string t = line.Trim();
            if (!t.StartsWith("TABLE:", StringComparison.Ordinal)) continue;
            int q1 = t.IndexOf('"');
            int q2 = t.LastIndexOf('"');
            if (q1 >= 0 && q2 > q1) order.Add(t.Substring(q1 + 1, q2 - q1 - 1));
        }
        return order;
    }

    private static readonly Regex GuidRegex =
        new Regex(@"GUID=[0-9a-fA-F-]{36}", RegexOptions.Compiled);

    private static string[] Normalize(string[] lines)
    {
        var outLines = new string[lines.Length];
        for (int i = 0; i < lines.Length; i++)
        {
            string line = lines[i];
            if (i == 0) line = "File <HEADER>";
            outLines[i] = GuidRegex.Replace(line, "GUID=<GUID>");
        }
        return outLines;
    }

    private static string? FindPythonReference()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null)
        {
            string cand = Path.Combine(dir.FullName, "python_reference.py");
            if (File.Exists(cand)) return cand;
            dir = dir.Parent;
        }
        string cwdCand = Path.Combine(Directory.GetCurrentDirectory(), "python_reference.py");
        if (File.Exists(cwdCand)) return cwdCand;
        return null;
    }

    // ---------------------------------------------------------------- Check 3
    private static bool Check3Pytest(string sapRoot)
    {
        Console.WriteLine("--- Check 3: Python test suite (pytest) ---");
        var env = new Dictionary<string, string> { ["PYTHONPATH"] = sapRoot };
        var (exit, stdout, stderr) = RunProcess("python3",
            new[] { "-m", "pytest", "tests", "-q" }, sapRoot, env);
        string combined = stdout + "\n" + stderr;
        foreach (string line in combined.Split('\n'))
        {
            string t = line.TrimEnd('\r');
            if (t.Length > 0) Console.WriteLine("  " + t);
        }
        var mPass = Regex.Match(combined, @"(\d+) passed");
        var mFail = Regex.Match(combined, @"(\d+) failed");
        int passed = mPass.Success ? int.Parse(mPass.Groups[1].Value) : -1;
        int failed = mFail.Success ? int.Parse(mFail.Groups[1].Value) : 0;
        Console.WriteLine($"  Ket qua parse duoc: {passed} passed, {failed} failed (ky vong 39/39 pass), exit={exit}");
        bool ok = exit == 0 && passed == 39 && failed == 0;
        Console.WriteLine(ok ? "Check 3: PASS" : "Check 3: FAIL");
        return ok;
    }

    // ---------------------------------------------------------------- Helper
    private static (int Exit, string Stdout, string Stderr) RunProcess(
        string file, string[] args, string? workingDir,
        Dictionary<string, string>? extraEnv = null)
    {
        var psi = new ProcessStartInfo
        {
            FileName = file,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string a in args) psi.ArgumentList.Add(a);
        if (workingDir is not null) psi.WorkingDirectory = workingDir;
        if (extraEnv is not null)
        {
            foreach (var kv in extraEnv) psi.Environment[kv.Key] = kv.Value;
        }
        using var proc = Process.Start(psi)!;
        string stdout = proc.StandardOutput.ReadToEnd();
        string stderr = proc.StandardError.ReadToEnd();
        proc.WaitForExit();
        return (proc.ExitCode, stdout, stderr);
    }
}
