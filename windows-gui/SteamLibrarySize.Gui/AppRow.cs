namespace SteamLibrarySize.Gui;

public sealed record AppRow(uint AppId, string Name, string Type, long SizeBytes)
{
    public double SizeGb => SizeBytes / (1024.0 * 1024 * 1024);
    public static AppRow From(SteamLibrarySize.Core.AppSize a) => new(a.AppId, a.Name, a.Type, a.SizeBytes);
}
