using System;
using System.Reflection;
using System.Windows.Forms;
using CSiAPIv1;

namespace Sap2Safe.Plugin;

/// <summary>Thông tin phiên bản plugin — đọc lúc chạy, không hardcode vào source.</summary>
public static class PluginInfo
{
    public const string Version = "0.1";

    /// <summary>Timestamp build (giờ UTC+7, yyyyMMdd-HHmmss) lấy từ AssemblyMetadata
    /// do MSBuild đóng dấu lúc build; chuỗi rỗng nếu metadata không có (vd build tay).</summary>
    public static string BuildTimestamp
    {
        get
        {
            foreach (var attr in typeof(PluginInfo).Assembly.GetCustomAttributes<AssemblyMetadataAttribute>())
            {
                if (attr.Key == "PluginBuildTimestamp")
                {
                    return attr.Value ?? "";
                }
            }
            return "";
        }
    }
}

/// <summary>
/// Điểm vào plugin SAP2000. SAP tìm class tên <c>cPlugin</c> implement
/// <c>cPluginContract</c> (xem API_DUMP.md: Main trả void, Info trả int).
/// </summary>
public class cPlugin : cPluginContract
{
    public int Info(ref string Text)
    {
        Text = "SAP2SAFE v0.1 — Chuyen 1 level SAP2000 sang SAFE (.F2K/.sf), ke ca load case Nonlinear Static";
        return 0;
    }

    public void Main(ref cSapModel SapModel, ref cPluginCallback PluginCallback)
    {
        try
        {
            // Non-modal: Show() rồi return ngay — TUYỆT ĐỐI không ShowDialog (SAP treo).
            // Form giữ reference tới callback và tự gọi Finish(0/1) đúng 1 lần khi đóng,
            // vì đối tượng cPlugin này có thể bị hủy giữa các lần bấm menu.
            var form = new MainForm(SapModel, PluginCallback);
            form.Show();
        }
        catch (Exception ex)
        {
            try
            {
                MessageBox.Show(
                    "SAP2SAFE gặp lỗi khi mở form:\n" + ex.Message,
                    "SAP2SAFE", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            catch
            {
                // Không để exception từ MessageBox văng ra SAP.
            }
            try
            {
                PluginCallback.Finish(1);
            }
            catch
            {
                // Không để exception từ Finish văng ra SAP.
            }
        }
    }
}
