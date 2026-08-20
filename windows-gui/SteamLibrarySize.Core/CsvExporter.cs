namespace SteamLibrarySize.Core;

public static class CsvExporter
{
    public static void Write(TextWriter writer, IEnumerable<AppSize> apps)
    {
        writer.WriteLine("appid,name,type,size_bytes");
        foreach (var a in apps)
            writer.WriteLine($"{a.AppId},{Quote(a.Name)},{Quote(a.Type)},{a.SizeBytes}");
    }

    private static string Quote(string field) =>
        field.IndexOfAny([',', '"', '\n', '\r']) < 0 ? field : $"\"{field.Replace("\"", "\"\"")}\"";
}
