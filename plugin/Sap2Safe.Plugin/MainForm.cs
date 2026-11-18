using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using CSiAPIv1;
using Sap2Safe.Core;

namespace Sap2Safe.Plugin;

/// <summary>
/// Form chính SAP2SAFE — non-modal (Show, không ShowDialog), 5 bước như app.py:
/// (1) thông tin model, (2) chọn level Z, (3) chọn output + step, (4) tham số xuất,
/// (5) preview + xuất .F2K + .sf + .log. KHÔNG dùng Excel.
/// Mọi số nhập tay đều parse bằng CultureInfo.InvariantCulture.
/// </summary>
public sealed class MainForm : Form
{
    private readonly cSapModel _sapModel;
    private readonly cPluginCallback _callback;
    private readonly SapReader _reader;

    private bool _finishCalled;
    private int _finishCode;

    // Dữ liệu model đọc 1 lần khi mở form (đơn vị đã đổi về kN, m).
    private List<SapOutput> _outputs = new();
    private Dictionary<string, PatternInfo> _patternInfo = new(StringComparer.Ordinal);
    private List<double> _zLevels = new();
    private List<Joint> _jointsAtZ = new();
    private List<Reaction>? _cachedReactions;
    private double? _listedZ;
    private double _listedTol = 0.005;
    private string _unitsLabel = "";
    private string? _modelPath;

    // Kết quả build gần nhất (để preview / xuất dùng chung).
    private BuildResult? _lastBuild;
    private double _lastZ;
    private double _lastTol;

    // Controls
    private Label _lblModelInfo = null!;
    private ComboBox _cmbZ = null!;
    private TextBox _txtZ = null!;
    private TextBox _txtTol = null!;
    private Label _lblJoints = null!;
    private ListBox _lbCases = null!;
    private ListBox _lbCombos = null!;
    private RadioButton _rbLast = null!;
    private RadioButton _rbSpecific = null!;
    private RadioButton _rbGoverning = null!;
    private RadioButton _rbMaxMin = null!;
    private TextBox _txtStepType = null!;
    private TextBox _txtStepNum = null!;
    private CheckBox _chkFlip = null!;
    private TextBox _txtSafeVersion = null!;
    private TextBox _txtOutDir = null!;
    private DataGridView _grid = null!;
    private Label _lblTotals = null!;

    public MainForm(cSapModel sapModel, cPluginCallback callback)
    {
        _sapModel = sapModel ?? throw new ArgumentNullException(nameof(sapModel));
        _callback = callback ?? throw new ArgumentNullException(nameof(callback));
        _reader = new SapReader(sapModel);

        string stamp = PluginInfo.BuildTimestamp;
        Text = string.IsNullOrEmpty(stamp)
            ? "SAP2SAFE v0.1 — SAP2000 -> SAFE (.F2K/.sf)"
            : $"SAP2SAFE v0.1 — SAP2000 -> SAFE (.F2K/.sf) (build {stamp})";
        Width = 1000;
        Height = 920;
        StartPosition = FormStartPosition.CenterScreen;
        AutoScroll = true;

        BuildUi();
        FormClosed += MainForm_FormClosed;
        Load += MainForm_Load;
    }

    // -- vòng đời plugin -------------------------------------------------

    private void MainForm_FormClosed(object? sender, FormClosedEventArgs e)
    {
        FinishPlugin(_finishCode);
    }

    /// <summary>Gọi PluginCallback.Finish ĐÚNG 1 lần khi form đóng (nút Đóng hay nút X đều vậy).</summary>
    private void FinishPlugin(int code)
    {
        if (_finishCalled)
        {
            return;
        }
        _finishCalled = true;
        try
        {
            _callback.Finish(code);
        }
        catch
        {
            // SAP có thể đã đóng callback; không làm gì thêm.
        }
    }

    private void MainForm_Load(object? sender, EventArgs e)
    {
        try
        {
            ReadModel();
        }
        catch (Exception ex)
        {
            _finishCode = 1; // lỗi nghiêm trọng: không đọc được model
            _lblModelInfo.Text = "Không đọc được model SAP: " + ex.Message;
            MessageBox.Show(
                "Không đọc được model SAP:\n" + ex.Message +
                "\n\nForm vẫn mở để đóng bình thường; kiểm tra lại model trong SAP rồi mở lại plugin.",
                "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    // -- đọc model 1 lần khi mở form -------------------------------------

    private void ReadModel()
    {
        var (forceToKn, lengthToM) = _reader.GetUnits();
        _unitsLabel = _reader.GetUnitsName() + $" (lực ×{forceToKn.ToString(CultureInfo.InvariantCulture)} -> kN, dài ×{lengthToM.ToString(CultureInfo.InvariantCulture)} -> m)";
        _modelPath = _reader.GetModelFilePath();

        var patterns = _reader.ListLoadPatterns();
        _patternInfo = patterns.ToDictionary(
            p => p.Name,
            p => new PatternInfo { DesignType = p.Type, SelfWtMult = p.SelfWtMult },
            StringComparer.Ordinal);

        var cases = _reader.ListLoadCases();
        var combos = _reader.ListCombos();
        _outputs = cases.Concat(combos).ToList();

        _zLevels = _reader.ListZLevels();
        double? suggestedZ = _reader.GetSuggestedZ();
        int jointCount = _reader.GetJointCount();

        _cmbZ.Items.Clear();
        foreach (double z in _zLevels)
        {
            _cmbZ.Items.Add(z.ToString("F3", CultureInfo.InvariantCulture));
        }
        if (_zLevels.Count > 0)
        {
            if (suggestedZ.HasValue)
            {
                _cmbZ.Text = suggestedZ.Value.ToString("F3", CultureInfo.InvariantCulture);
            }
            else
            {
                _cmbZ.SelectedIndex = 0;
            }
        }

        _lbCases.Items.Clear();
        _lbCombos.Items.Clear();
        foreach (var o in cases)
        {
            _lbCases.Items.Add(o.Name);
        }
        foreach (var o in combos)
        {
            string label = o.ComboType is null ? o.Name : $"{o.Name}  [{o.ComboType}]";
            _lbCombos.Items.Add(label);
        }

        string outDir = _reader.GetModelDirectory()
            ?? Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
        _txtOutDir.Text = outDir;

        var sb = new StringBuilder();
        sb.AppendLine("Model: " + (_modelPath ?? "(chưa lưu file .sdb)"));
        sb.AppendLine("Đơn vị hiện tại: " + _unitsLabel);
        sb.AppendLine($"Pattern: {patterns.Count} | Case: {cases.Count} | Combo: {combos.Count} | " +
                      $"Joint: {jointCount} | Cao độ Z: {_zLevels.Count}" +
                      (suggestedZ.HasValue
                          ? $" | Gợi ý Z = {suggestedZ.Value.ToString("F3", CultureInfo.InvariantCulture)} m (nhiều joint có gối nhất)"
                          : ""));
        if (_reader.Notes.Count > 0)
        {
            sb.AppendLine("Ghi chú: " + string.Join(" ", _reader.Notes));
        }
        _lblModelInfo.Text = sb.ToString().TrimEnd();
    }

    // -- parse số: LUÔN InvariantCulture ---------------------------------

    private static bool TryParseDouble(string text, out double value)
    {
        return double.TryParse(
            (text ?? "").Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out value);
    }

    private bool TryGetZTol(out double z, out double tol)
    {
        z = 0;
        tol = 0.005;
        if (!TryParseDouble(_txtTol.Text, out tol) || tol <= 0)
        {
            MessageBox.Show("tol phải là số dương (mặc định 0.005).",
                "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return false;
        }
        string zText = _txtZ.Text.Trim();
        if (zText.Length > 0)
        {
            if (!TryParseDouble(zText, out z))
            {
                MessageBox.Show("Z nhập tay phải là số (dùng dấu chấm thập phân, vd 3.12).",
                    "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return false;
            }
            return true;
        }
        if (!string.IsNullOrEmpty(_cmbZ.Text) && TryParseDouble(_cmbZ.Text, out z))
        {
            return true;
        }
        MessageBox.Show("Chưa chọn cao độ Z (chọn trong danh sách hoặc nhập tay).",
            "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        return false;
    }

    private List<string> SelectedOutputs()
    {
        var names = new List<string>();
        foreach (int i in _lbCases.SelectedIndices)
        {
            names.Add(_lbCases.Items[i].ToString()!);
        }
        // ListBox combo hiển thị "Tên  [Loại]" — lấy lại tên gốc theo thứ tự.
        var combos = _outputs.Where(o => o.Kind == "combo").ToList();
        foreach (int i in _lbCombos.SelectedIndices)
        {
            if (i >= 0 && i < combos.Count)
            {
                names.Add(combos[i].Name);
            }
        }
        return names;
    }

    // -- bước 2: liệt kê joint + đọc phản lực ----------------------------

    private void BtnListJoints_Click(object? sender, EventArgs e)
    {
        if (!TryGetZTol(out double z, out double tol))
        {
            return;
        }
        try
        {
            _jointsAtZ = _reader.GetJointsAtZ(z, tol);
            _listedZ = z;
            _listedTol = tol;
            int nRestrained = _jointsAtZ.Count(j => j.Restrained);
            _lblJoints.Text = $"Z = {z.ToString("F3", CultureInfo.InvariantCulture)} m: " +
                              $"{_jointsAtZ.Count} joint (trong đó {nRestrained} joint có gối).";
            if (_jointsAtZ.Count == 0)
            {
                MessageBox.Show("Không có joint nào tại Z này.",
                    "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            // Đọc phản lực cho TẤT CẢ case (không phải combo) ngay ở bước này,
            // cache lại — như app.py _list_joints ở chế độ COM. Đổi lựa chọn
            // case/combo sau đó không cần đọc lại.
            var casesOnly = _outputs.Where(o => o.Kind == "case").ToList();
            if (casesOnly.Count == 0)
            {
                _cachedReactions = new List<Reaction>();
                MessageBox.Show("Model không có load case nào nên chưa có phản lực để đọc.",
                    "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            using (new SapStateGuard(_sapModel, _outputs))
            {
                _cachedReactions = _reader.GetJointReactions(casesOnly);
            }
            _lblJoints.Text += $" Đã đọc {_cachedReactions.Count} dòng phản lực cho {casesOnly.Count} case.";
        }
        catch (Exception ex)
        {
            MessageBox.Show("Liệt kê joint thất bại:\n" + ex.Message,
                "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    // -- build model chung cho Preview + Xuất ----------------------------

    private BuildResult? BuildModel()
    {
        var selected = SelectedOutputs();
        if (selected.Count == 0)
        {
            MessageBox.Show("Chưa chọn output nào (case hoặc combo).",
                "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return null;
        }
        if (!TryGetZTol(out double z, out double tol))
        {
            return null;
        }
        if (_jointsAtZ.Count == 0 || !_listedZ.HasValue)
        {
            MessageBox.Show("Chưa liệt kê joint tại Z — bấm 'Liệt kê joint tại Z' trước.",
                "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return null;
        }
        if (Math.Abs(z - _listedZ.Value) > tol)
        {
            MessageBox.Show("Z đã đổi sau khi liệt kê joint — bấm 'Liệt kê joint tại Z' lại.",
                "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return null;
        }
        if (_cachedReactions is null || _cachedReactions.Count == 0)
        {
            MessageBox.Show("Chưa có phản lực — bấm 'Liệt kê joint tại Z' trước.",
                "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return null;
        }

        string stepMode = "last";
        if (_rbSpecific.Checked)
        {
            stepMode = "specific";
        }
        else if (_rbGoverning.Checked)
        {
            stepMode = "governing";
        }
        else if (_rbMaxMin.Checked)
        {
            stepMode = "maxmin";
        }
        (string StepType, double StepNum)? specific = null;
        if (stepMode == "specific")
        {
            if (!TryParseDouble(_txtStepNum.Text, out double stepNum))
            {
                MessageBox.Show("StepNum phải là số (dùng dấu chấm thập phân).",
                    "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return null;
            }
            string stepType = _txtStepType.Text.Trim();
            specific = (stepType.Length == 0 ? "Step" : stepType, stepNum);
        }

        string safeVersion = _txtSafeVersion.Text.Trim();
        if (safeVersion.Length == 0)
        {
            safeVersion = "22.5.1";
        }

        var jointsXyz = new Dictionary<string, (double X, double Y, double Z)>(StringComparer.Ordinal);
        var jointsRestraint = new Dictionary<string, bool[]>(StringComparer.Ordinal);
        foreach (var j in _jointsAtZ)
        {
            jointsXyz[j.Name] = (j.X, j.Y, j.Z);
            if (j.Restraint != null)
            {
                jointsRestraint[j.Name] = j.Restraint;
            }
        }

        try
        {
            var result = Pipeline.BuildF2kModel(
                _cachedReactions, jointsXyz, _outputs, selected,
                jointsRestraint, _patternInfo, stepMode, specific,
                _chkFlip.Checked, safeVersion);
            _lastBuild = result;
            _lastZ = z;
            _lastTol = tol;
            return result;
        }
        catch (Exception ex)
        {
            MessageBox.Show("Build model thất bại:\n" + ex.Message,
                "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return null;
        }
    }

    private void BtnPreview_Click(object? sender, EventArgs e)
    {
        var result = BuildModel();
        if (result is null)
        {
            return;
        }
        var model = result.Model;
        var pointsByName = model.Points.ToDictionary(p => p.Name, StringComparer.Ordinal);
        _grid.Rows.Clear();
        foreach (var ld in model.PointLoads)
        {
            pointsByName.TryGetValue(ld.Point, out var pt);
            _grid.Rows.Add(
                ld.Point,
                pt is null ? "" : pt.X.ToString("F3", CultureInfo.InvariantCulture),
                pt is null ? "" : pt.Y.ToString("F3", CultureInfo.InvariantCulture),
                ld.Pattern,
                ld.Fx.ToString("F1", CultureInfo.InvariantCulture),
                ld.Fy.ToString("F1", CultureInfo.InvariantCulture),
                ld.Fz.ToString("F1", CultureInfo.InvariantCulture),
                ld.Mx.ToString("F1", CultureInfo.InvariantCulture),
                ld.My.ToString("F1", CultureInfo.InvariantCulture),
                ld.Mz.ToString("F1", CultureInfo.InvariantCulture));
        }
        var totals = new Dictionary<string, double>(StringComparer.Ordinal);
        foreach (var ld in model.PointLoads)
        {
            totals[ld.Pattern] = totals.TryGetValue(ld.Pattern, out double cur) ? cur + ld.Fz : ld.Fz;
        }
        _lblTotals.Text = string.Join("  |  ", totals.Select(kv =>
            $"ΣFZ {kv.Key} = {kv.Value.ToString("F1", CultureInfo.InvariantCulture)} kN"));
        if (result.Warnings.Count > 0)
        {
            MessageBox.Show("Cảnh báo:\n" + string.Join("\n", result.Warnings),
                "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }

    private void BtnExport_Click(object? sender, EventArgs e)
    {
        var result = BuildModel();
        if (result is null)
        {
            return;
        }
        string outDir = _txtOutDir.Text.Trim();
        if (outDir.Length == 0)
        {
            outDir = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
        }
        try
        {
            Directory.CreateDirectory(outDir);
            string basePath = Path.Combine(
                outDir, "SAP2SAFE_Z" + _lastZ.ToString("F2", CultureInfo.InvariantCulture));
            var countsF2k = SfWriter.WriteF2k(basePath + ".f2k", result.Model);
            SfWriter.WriteSf(basePath + ".sf", result.Model);
            WriteLog(basePath + ".log", result);
            string msg = $"Đã xuất:\n{basePath}.f2k\n{basePath}.sf (cùng nội dung)\n{basePath}.log\n\n" +
                         $"{countsF2k.Points} point, {countsF2k.Patterns} pattern, " +
                         $"{countsF2k.Cases} case, {countsF2k.Combos} combo.";
            if (result.Warnings.Count > 0)
            {
                msg += "\n\nCảnh báo:\n" + string.Join("\n", result.Warnings);
            }
            MessageBox.Show(msg, "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show("Ghi file thất bại:\n" + ex.Message,
                "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    /// <summary>File .log kèm theo — port đơn giản từ report.py (log text thuần tiếng Việt).</summary>
    private void WriteLog(string path, BuildResult result)
    {
        var info = result.Info;
        var model = result.Model;
        var lines = new List<string>
        {
            $"SAP2SAFE v{PluginInfo.Version} (build {PluginInfo.BuildTimestamp}) — LOG xuat file",
            new string('=', 60),
            $"Model: {_modelPath ?? "(chua luu file .sdb)"}",
            $"Level Z = {_lastZ.ToString(CultureInfo.InvariantCulture)} m (tol {_lastTol.ToString(CultureInfo.InvariantCulture)} m)",
            $"Don vi: {info.Units} (don vi goc SAP: {_unitsLabel})",
            $"SAFE version (PROGRAM CONTROL): {info.SafeVersion}",
            $"Doi dau phan luc -> tai SAFE: {(info.FlipSign ? "BAT" : "TAT")}",
            $"So joint: {model.Points.Count} | pattern: {model.Patterns.Count} | " +
            $"case: {model.Cases.Count} | combo: {model.Combos.Count} | point load: {model.PointLoads.Count}",
            "",
            "Ghi chu (theo file MONG.sf that):",
            "  - SelfWtMult lay tu SAP (SW=1, con lai 0); tai SW trong SAFE la",
            "    tai diem da dong bang, tu trong san SAFE (neu co) tinh rieng.",
            "  - Moi case gom pattern goc + pattern _ABOVE; _ABOVE co 0 dong",
            "    joint load (chi pattern goc co tai).",
            "  - Combo copy y het dinh nghia SAP; combo chua case nonlinear thi",
            "    SAFE cong tuyen tinh cac vector da dong bang, khong phai chay",
            "    lai phi tuyen.",
            "  - File chi gom points + restraints + loads (khong co slab/area/",
            "    spring) — giong MONG.sf; import vao model SAFE da co san.",
        };
        foreach (string note in info.Notes)
        {
            lines.Add("  - " + note);
        }
        lines.Add("");
        lines.Add("Bang map ten (SAP -> SAFE):");
        foreach (var kv in info.NameMap)
        {
            lines.Add($"  {kv.Key} -> {kv.Value}");
        }
        lines.Add("");
        lines.Add("Nguon tung pattern:");
        foreach (string src in info.Sources)
        {
            lines.Add("  " + src);
        }
        lines.Add("");
        lines.Add("Tong kiem tra theo tung pattern (FZ SAFE phai = -F3 SAP):");
        var sumsSafe = new Dictionary<string, double>(StringComparer.Ordinal);
        foreach (var ld in info.Loads)
        {
            sumsSafe[ld.Pattern] = sumsSafe.TryGetValue(ld.Pattern, out double cur) ? cur + ld.Fz : ld.Fz;
        }
        bool okAll = true;
        var allPatterns = new SortedSet<string>(StringComparer.Ordinal);
        foreach (string p in sumsSafe.Keys)
        {
            allPatterns.Add(p);
        }
        foreach (string p in info.SapSums.Keys)
        {
            allPatterns.Add(p);
        }
        foreach (string pattern in allPatterns)
        {
            double fz = sumsSafe.TryGetValue(pattern, out double v1) ? v1 : 0;
            double f3 = info.SapSums.TryGetValue(pattern, out double v2) ? v2 : 0;
            bool ok = Math.Abs(fz + f3) < 1e-6;
            okAll = okAll && ok;
            lines.Add($"  {pattern}: sum FZ SAFE = {fz.ToString("F3", CultureInfo.InvariantCulture)} kN | " +
                      $"sum F3 SAP = {f3.ToString("F3", CultureInfo.InvariantCulture)} kN | " +
                      (ok ? "KHOP" : "LECH!"));
        }
        lines.Add("");
        lines.Add("Ket luan tong kiem tra: " + (okAll ? "KHOP" : "CO LECH — KIEM TRA LAI TRUOC KHI IMPORT"));
        if (info.Warnings.Count > 0)
        {
            lines.Add("");
            lines.Add("Canh bao:");
            foreach (string w in info.Warnings)
            {
                lines.Add("  ! " + w);
            }
        }
        File.WriteAllText(path, string.Join("\n", lines) + "\n", new UTF8Encoding(false));
    }

    // -- giao diện (dựng bằng code, không dùng designer) -----------------

    private void BuildUi()
    {
        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            AutoSize = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            Padding = new Padding(8),
        };
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        Controls.Add(root);

        // (1) Thông tin model
        var g1 = new GroupBox { Text = "1. Thông tin model", Dock = DockStyle.Fill, AutoSize = true };
        _lblModelInfo = new Label { Text = "Đang đọc model...", Dock = DockStyle.Fill, AutoSize = true };
        g1.Controls.Add(_lblModelInfo);
        root.Controls.Add(g1);

        // (2) Chọn level Z
        var g2 = new GroupBox { Text = "2. Chọn level (cao độ Z)", Dock = DockStyle.Fill, AutoSize = true };
        var t2 = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 7, AutoSize = true, Padding = new Padding(6) };
        t2.Controls.Add(new Label { Text = "Z có joint:", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 0);
        _cmbZ = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 120, Anchor = AnchorStyles.Left };
        t2.Controls.Add(_cmbZ, 1, 0);
        t2.Controls.Add(new Label { Text = "hoặc nhập Z (m):", AutoSize = true, Anchor = AnchorStyles.Left }, 2, 0);
        _txtZ = new TextBox { Width = 100, Anchor = AnchorStyles.Left };
        t2.Controls.Add(_txtZ, 3, 0);
        t2.Controls.Add(new Label { Text = "tol (m):", AutoSize = true, Anchor = AnchorStyles.Left }, 4, 0);
        _txtTol = new TextBox { Text = "0.005", Width = 70, Anchor = AnchorStyles.Left };
        t2.Controls.Add(_txtTol, 5, 0);
        var btnList = new Button { Text = "Liệt kê joint tại Z", AutoSize = true, Anchor = AnchorStyles.Left };
        btnList.Click += BtnListJoints_Click;
        t2.Controls.Add(btnList, 6, 0);
        _lblJoints = new Label { Text = "", AutoSize = true, Dock = DockStyle.Fill };
        t2.Controls.Add(_lblJoints, 0, 1);
        t2.SetColumnSpan(_lblJoints, 7);
        g2.Controls.Add(t2);
        root.Controls.Add(g2);

        // (3) Chọn output + step
        var g3 = new GroupBox { Text = "3. Chọn output + step đóng băng", Dock = DockStyle.Fill, AutoSize = true };
        var t3 = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, AutoSize = true, Padding = new Padding(6) };
        t3.Controls.Add(new Label { Text = "Load Cases (chọn nhiều):", AutoSize = true }, 0, 0);
        t3.Controls.Add(new Label { Text = "Load Combos (chọn nhiều):", AutoSize = true }, 1, 0);
        _lbCases = new ListBox { SelectionMode = SelectionMode.MultiExtended, Height = 130, Dock = DockStyle.Fill };
        t3.Controls.Add(_lbCases, 0, 1);
        _lbCombos = new ListBox { SelectionMode = SelectionMode.MultiExtended, Height = 130, Dock = DockStyle.Fill };
        t3.Controls.Add(_lbCombos, 1, 1);
        var pnlStep = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, FlowDirection = FlowDirection.TopDown };
        _rbLast = new RadioButton { Text = "Last step (mặc định)", Checked = true, AutoSize = true };
        _rbSpecific = new RadioButton { Text = "Step cụ thể", AutoSize = true };
        _rbGoverning = new RadioButton { Text = "Governing step (max |F3|)", AutoSize = true };
        _rbMaxMin = new RadioButton { Text = "Tách MAX-MIN (chỉ Envelope/RS)", AutoSize = true };
        pnlStep.Controls.Add(_rbLast);
        pnlStep.Controls.Add(_rbSpecific);
        pnlStep.Controls.Add(_rbGoverning);
        pnlStep.Controls.Add(_rbMaxMin);
        t3.Controls.Add(pnlStep, 0, 2);
        var pnlStepNum = new TableLayoutPanel { ColumnCount = 2, AutoSize = true, Dock = DockStyle.Fill };
        pnlStepNum.Controls.Add(new Label { Text = "StepType:", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 0);
        _txtStepType = new TextBox { Text = "Step", Width = 100, Anchor = AnchorStyles.Left };
        pnlStepNum.Controls.Add(_txtStepType, 1, 0);
        pnlStepNum.Controls.Add(new Label { Text = "StepNum:", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 1);
        _txtStepNum = new TextBox { Text = "1", Width = 100, Anchor = AnchorStyles.Left };
        pnlStepNum.Controls.Add(_txtStepNum, 1, 1);
        t3.Controls.Add(pnlStepNum, 1, 2);
        _chkFlip = new CheckBox { Text = "Đổi dấu phản lực -> tải SAFE (mặc định BẬT)", Checked = true, AutoSize = true, Dock = DockStyle.Fill };
        t3.Controls.Add(_chkFlip, 0, 3);
        t3.SetColumnSpan(_chkFlip, 2);
        g3.Controls.Add(t3);
        root.Controls.Add(g3);

        // (4) Tham số xuất
        var g4 = new GroupBox { Text = "4. Tham số xuất", Dock = DockStyle.Fill, AutoSize = true };
        var t4 = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 5, AutoSize = true, Padding = new Padding(6) };
        t4.Controls.Add(new Label { Text = "SAFE version:", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 0);
        _txtSafeVersion = new TextBox { Text = "22.5.1", Width = 80, Anchor = AnchorStyles.Left };
        t4.Controls.Add(_txtSafeVersion, 1, 0);
        t4.Controls.Add(new Label { Text = "Thư mục xuất:", AutoSize = true, Anchor = AnchorStyles.Left }, 2, 0);
        _txtOutDir = new TextBox { Dock = DockStyle.Fill, Anchor = AnchorStyles.Left | AnchorStyles.Right };
        t4.Controls.Add(_txtOutDir, 3, 0);
        var btnBrowse = new Button { Text = "Chọn...", AutoSize = true, Anchor = AnchorStyles.Left };
        btnBrowse.Click += BtnBrowseOutDir_Click;
        t4.Controls.Add(btnBrowse, 4, 0);
        var lblNote = new Label
        {
            Text = "File xuất chỉ gồm points + restraints + loads (như MONG.sf) — không sinh sàn; import vào model SAFE đã có sẵn.",
            AutoSize = true, ForeColor = System.Drawing.Color.Gray, Dock = DockStyle.Fill,
        };
        t4.Controls.Add(lblNote, 0, 1);
        t4.SetColumnSpan(lblNote, 5);
        g4.Controls.Add(t4);
        root.Controls.Add(g4);

        // (5) Preview + xuất
        var g5 = new GroupBox { Text = "5. Preview + xuất file", Dock = DockStyle.Fill, AutoSize = true };
        var t5 = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, AutoSize = true, Padding = new Padding(6) };
        _grid = new DataGridView
        {
            ReadOnly = true,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
            AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
            Height = 260,
            Dock = DockStyle.Fill,
        };
        foreach (string col in new[] { "Joint", "X", "Y", "Pattern", "FX", "FY", "FZ", "MX", "MY", "MZ" })
        {
            _grid.Columns.Add(col, col);
        }
        t5.Controls.Add(_grid, 0, 0);
        _lblTotals = new Label { Text = "", AutoSize = true, Dock = DockStyle.Fill };
        t5.Controls.Add(_lblTotals, 0, 1);
        var pnlBtns = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true };
        var btnPreview = new Button { Text = "Xem preview", AutoSize = true };
        btnPreview.Click += BtnPreview_Click;
        pnlBtns.Controls.Add(btnPreview);
        var btnExport = new Button { Text = "Xuất .F2K + .sf (+ .log)", AutoSize = true };
        btnExport.Click += BtnExport_Click;
        pnlBtns.Controls.Add(btnExport);
        var btnClose = new Button { Text = "Đóng", AutoSize = true };
        btnClose.Click += BtnClose_Click;
        pnlBtns.Controls.Add(btnClose);
        t5.Controls.Add(pnlBtns, 0, 2);
        g5.Controls.Add(t5);
        root.Controls.Add(g5);
    }

    private void BtnBrowseOutDir_Click(object? sender, EventArgs e)
    {
        using var dlg = new FolderBrowserDialog
        {
            Description = "Chọn thư mục xuất file .F2K/.sf/.log",
            SelectedPath = _txtOutDir.Text,
        };
        if (dlg.ShowDialog(this) == DialogResult.OK)
        {
            _txtOutDir.Text = dlg.SelectedPath;
        }
    }

    private void BtnClose_Click(object? sender, EventArgs e)
    {
        Close();
    }
}
