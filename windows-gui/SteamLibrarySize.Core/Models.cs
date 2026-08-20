namespace SteamLibrarySize.Core;

public sealed record AppSize(uint AppId, string Name, string Type, long SizeBytes);

public sealed record FetchResult(IReadOnlyList<AppSize> Apps, IReadOnlyList<uint> SkippedAppIds);
