using System;
using System.Collections.Generic;

namespace Sap2Safe.Core;

public static class Units
{
    // eUnits kết hợp đã verify (GetPresentUnits trả trực tiếp):
    // mã -> (tên đơn vị lực, tên đơn vị dài)
    private static readonly Dictionary<int, (string Force, string Length)> EUnitsMap =
        new Dictionary<int, (string, string)>
        {
            { 1, ("lb", "in") },
            { 2, ("lb", "ft") },
            { 3, ("kip", "in") },
            { 4, ("kip", "ft") },
            { 5, ("kN", "mm") },
            { 6, ("kN", "m") },
            { 7, ("kgf", "mm") },
            { 8, ("kgf", "m") },
            { 9, ("N", "mm") },
            { 10, ("N", "m") },
            { 11, ("Ton", "mm") },
            { 12, ("Ton", "m") },
            { 13, ("kN", "cm") },
            { 14, ("kgf", "cm") },
            { 15, ("N", "cm") },
            { 16, ("Ton", "cm") },
        };

    private static readonly Dictionary<string, double> ForceToKn =
        new Dictionary<string, double>
        {
            { "N", 0.001 },
            { "kN", 1.0 },
            { "kgf", 0.00980665 },
            { "tonf", 9.80665 },
            { "Ton", 9.80665 },
            { "kip", 4.448221615 },
            { "lb", 0.004448221615 },
        };

    private static readonly Dictionary<string, double> LengthToM =
        new Dictionary<string, double>
        {
            { "m", 1.0 },
            { "mm", 0.001 },
            { "cm", 0.01 },
            { "ft", 0.3048 },
            { "in", 0.0254 },
        };

    public static double ForceFactorByName(string unit)
    {
        if (unit is null || !ForceToKn.TryGetValue(unit, out double factor))
        {
            throw new ArgumentException($"Đơn vị lực không hỗ trợ: '{unit}'");
        }
        return factor;
    }

    public static double LengthFactorByName(string unit)
    {
        if (unit is null || !LengthToM.TryGetValue(unit, out double factor))
        {
            throw new ArgumentException($"Đơn vị dài không hỗ trợ: '{unit}'");
        }
        return factor;
    }

    public static double ForceFactorByEUnits(int eUnits)
    {
        return FactorsByEUnits(eUnits).ForceToKn;
    }

    public static double LengthFactorByEUnits(int eUnits)
    {
        return FactorsByEUnits(eUnits).LengthToM;
    }

    public static double MomentFactorByEUnits(int eUnits)
    {
        var (force, length) = FactorsByEUnits(eUnits);
        return force * length;
    }

    public static (double ForceToKn, double LengthToM) FactorsByEUnits(int eUnits)
    {
        if (!EUnitsMap.TryGetValue(eUnits, out var pair))
        {
            throw new ArgumentException($"Mã eUnits không rõ: {eUnits} (hợp lệ 1–16, đối chiếu GetPresentUnits)");
        }
        return (ForceToKn[pair.Force], LengthToM[pair.Length]);
    }
}
