using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace Sap2Safe.Core;

public static class CsiText
{
    private static readonly Regex KvRegex = new Regex(
        "(?:\"([^\"]+)\"|([A-Za-z0-9_?]+))\\s*=\\s*(?:\"((?:[^\"\\\\]|\\\\.)*)\"|([^\\s]+))",
        RegexOptions.Compiled);

    private static readonly Regex TableRegex = new Regex(
        "^TABLE:\\s+\"(.*)\"\\s*$",
        RegexOptions.Compiled);

    private static readonly Regex KeyNeedsQuoteRegex = new Regex(
        "[\\s=]",
        RegexOptions.Compiled);

    private static readonly Regex ValueNeedsQuoteRegex = new Regex(
        "[\\s,=]",
        RegexOptions.Compiled);

    public static string FormatNumber(double value)
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
        if (value == Math.Truncate(value) && Math.Abs(value) < 1e15)
        {
            return ((long)value).ToString(CultureInfo.InvariantCulture);
        }
        string text = value.ToString("G10", CultureInfo.InvariantCulture);
        return text.Replace("e", "E").Replace("E+", "E");
    }

    public static string FormatNumber(int value)
    {
        return value.ToString(CultureInfo.InvariantCulture);
    }

    public static string FormatKey(string key)
    {
        if (KeyNeedsQuoteRegex.IsMatch(key))
        {
            return "\"" + key + "\"";
        }
        return key;
    }

    public static string FormatValue(object? value)
    {
        if (value is bool b)
        {
            return b ? "Yes" : "No";
        }
        if (value is int i)
        {
            return FormatNumber(i);
        }
        if (value is long l)
        {
            return l.ToString(CultureInfo.InvariantCulture);
        }
        if (value is double d)
        {
            return FormatNumber(d);
        }
        if (value is float f)
        {
            return FormatNumber((double)f);
        }
        if (value is decimal dec)
        {
            return dec.ToString(CultureInfo.InvariantCulture);
        }
        if (value is null)
        {
            return "None";
        }
        string text = value.ToString() ?? "";
        if (text == "" || ValueNeedsQuoteRegex.IsMatch(text))
        {
            return "\"" + text + "\"";
        }
        return text;
    }

    public static string FormatKvLine(IEnumerable<KeyValuePair<string, object?>> fields)
    {
        var parts = new List<string>();
        foreach (var kv in fields)
        {
            if (kv.Value is null)
            {
                continue;
            }
            parts.Add(FormatKey(kv.Key) + "=" + FormatValue(kv.Value));
        }
        return "   " + string.Join("   ", parts);
    }

    public static Dictionary<string, string> ParseKvLine(string line)
    {
        var result = new Dictionary<string, string>();
        foreach (Match m in KvRegex.Matches(line))
        {
            string key = m.Groups[1].Success ? m.Groups[1].Value : m.Groups[2].Value;
            string value = m.Groups[3].Success ? m.Groups[3].Value : m.Groups[4].Value;
            result[key] = value;
        }
        return result;
    }

    public static List<string> JoinLogicalLines(IEnumerable<string> rawLines)
    {
        var output = new List<string>();
        string buf = "";
        foreach (string raw in rawLines)
        {
            string line = raw.TrimEnd('\n');
            if (buf.Length > 0)
            {
                buf += line.TrimStart();
            }
            else
            {
                buf = line;
            }
            if (buf.TrimEnd().EndsWith(" _", StringComparison.Ordinal))
            {
                buf = buf.TrimEnd();
                buf = buf.Substring(0, buf.Length - 2) + "   ";
                continue;
            }
            output.Add(buf);
            buf = "";
        }
        if (buf.Length > 0)
        {
            output.Add(buf);
        }
        return output;
    }

    public static Dictionary<string, List<Dictionary<string, string>>> ParseCsiTables(string path)
    {
        var encoding = new UTF8Encoding(false, false);
        string[] rawLines = File.ReadAllLines(path, encoding);
        List<string> lines = JoinLogicalLines(rawLines);
        var tables = new Dictionary<string, List<Dictionary<string, string>>>();
        string? current = null;
        foreach (string line in lines)
        {
            string stripped = line.Trim();
            if (stripped.Length == 0)
            {
                continue;
            }
            if (stripped.StartsWith("File ", StringComparison.Ordinal)
                && stripped.Contains("was saved on"))
            {
                continue;
            }
            Match m = TableRegex.Match(stripped);
            if (m.Success)
            {
                current = m.Groups[1].Value;
                if (!tables.ContainsKey(current))
                {
                    tables[current] = new List<Dictionary<string, string>>();
                }
                continue;
            }
            if (current is null)
            {
                continue;
            }
            if (line.StartsWith("   ", StringComparison.Ordinal))
            {
                var row = ParseKvLine(stripped);
                if (row.Count > 0)
                {
                    tables[current].Add(row);
                }
            }
        }
        return tables;
    }

    public static void WriteCsiTables(string path, string headerLine, IEnumerable<(string Name, List<string> Rows)> tables)
    {
        var output = new List<string> { headerLine, " " };
        foreach (var (name, rows) in tables)
        {
            output.Add("TABLE:  \"" + name + "\"");
            output.AddRange(rows);
            output.Add(" ");
        }
        File.WriteAllText(path, string.Join("\n", output), new UTF8Encoding(false));
    }
}
