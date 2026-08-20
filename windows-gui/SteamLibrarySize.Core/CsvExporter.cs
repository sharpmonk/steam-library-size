using System.Globalization;

namespace SteamLibrarySize.Core;

public static class CsvExporter
{
    public static void Write(TextWriter writer, IEnumerable<AppSize> apps)
    {
        var ic = CultureInfo.InvariantCulture;
        writer.WriteLine("appid,name,type,size_bytes");
        foreach (var a in apps)
            writer.WriteLine($"{a.AppId.ToString(ic)},{Quote(a.Name)},{Quote(a.Type)},{a.SizeBytes.ToString(ic)}");
    }

    private static string Quote(string field) =>
        field.IndexOfAny([',', '"', '\n', '\r']) < 0 ? field : $"\"{field.Replace("\"", "\"\"")}\"";
}
