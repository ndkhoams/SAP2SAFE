using System.Collections.Generic;

namespace Sap2Safe.Core;

public sealed class Joint
{
    public string Name { get; set; } = "";
    public double X;
    public double Y;
    public double Z;
    public bool Restrained;
    public bool[]? Restraint;
}

public sealed class Reaction
{
    public string Joint { get; set; } = "";
    public string OutputName { get; set; } = "";
    public string OutputKind { get; set; } = "";
    public string StepType { get; set; } = "";
    public double StepNum;
    public double F1;
    public double F2;
    public double F3;
    public double M1;
    public double M2;
    public double M3;
}

public sealed class ComboItem
{
    public string Case { get; set; } = "";
    public double Sf;

    public ComboItem()
    {
    }

    public ComboItem(string c, double sf)
    {
        Case = c;
        Sf = sf;
    }
}

public sealed class SapOutput
{
    public string Name { get; set; } = "";
    public string Kind { get; set; } = "";
    public int? CaseType;
    public bool IsNonlinear;
    public string? ComboType;
    public List<ComboItem> Components { get; } = new();
}

public sealed class FrozenLoad
{
    public string Joint { get; set; } = "";
    public double X;
    public double Y;
    public string Pattern { get; set; } = "";
    public double Fx;
    public double Fy;
    public double Fz;
    public double Mx;
    public double My;
    public double Mz;
    public string SourceStep { get; set; } = "";
}

public sealed class PatternDef
{
    public string Name { get; set; } = "";
    public string Type { get; set; } = "Other";
    public double SelfWtMult;
}

public sealed class CaseDef
{
    public string Name { get; set; } = "";
    public string Type { get; set; } = "Linear Static";
}

public sealed class ComboDef
{
    public string Name { get; set; } = "";
    public string Type { get; set; } = "Linear Add";
    public List<ComboItem> Items { get; } = new();
}

public sealed class PointDef
{
    public string Name { get; set; } = "";
    public double X;
    public double Y;
    public bool[]? Restraint;
}

public sealed class PointLoad
{
    public string Point { get; set; } = "";
    public string Pattern { get; set; } = "";
    public double Fx;
    public double Fy;
    public double Fz;
    public double Mx;
    public double My;
    public double Mz;
}

public sealed class F2kModel
{
    public List<PatternDef> Patterns { get; } = new();
    public List<CaseDef> Cases { get; } = new();
    public List<ComboDef> Combos { get; } = new();
    public List<PointDef> Points { get; } = new();
    public List<PointLoad> PointLoads { get; } = new();
    public string SafeVersion { get; set; } = "22.5.1";
    public string Units { get; set; } = "kN, m, C";
}
