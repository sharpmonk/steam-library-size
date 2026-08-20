using Microsoft.Win32;

namespace SteamLibrarySize.Core;

public static class SteamPathLocator
{
    public static bool IsValidSteamDir(string dir) =>
        File.Exists(Path.Combine(dir, "appcache", "packageinfo.vdf"));

    public static IReadOnlyList<string> Candidates()
    {
        var cands = new List<string>();
        if (!OperatingSystem.IsWindows()) return cands;
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam");
            if (key?.GetValue("SteamPath") is string regPath && regPath.Length > 0)
                cands.Add(Path.GetFullPath(regPath));
        }
        catch (Exception) { /* registry unreadable: fall through to defaults */ }
        foreach (var env in new[] { "ProgramFiles(x86)", "ProgramFiles" })
        {
            var basePath = Environment.GetEnvironmentVariable(env);
            if (!string.IsNullOrEmpty(basePath)) cands.Add(Path.Combine(basePath, "Steam"));
        }
        return cands;
    }

    public static string? FindSteamDir() => Candidates().FirstOrDefault(IsValidSteamDir);
}
