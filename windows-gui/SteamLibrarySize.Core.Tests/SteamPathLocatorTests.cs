using SteamLibrarySize.Core;
using Xunit;

namespace SteamLibrarySize.Core.Tests;

public class SteamPathLocatorTests
{
    [Fact]
    public void ValidDirRequiresPackageInfo()
    {
        var dir = Directory.CreateTempSubdirectory().FullName;
        Assert.False(SteamPathLocator.IsValidSteamDir(dir));
        Directory.CreateDirectory(Path.Combine(dir, "appcache"));
        File.WriteAllBytes(Path.Combine(dir, "appcache", "packageinfo.vdf"), [0x27]);
        Assert.True(SteamPathLocator.IsValidSteamDir(dir));
    }

    [Fact]
    public void MissingDirIsInvalid()
    {
        Assert.False(SteamPathLocator.IsValidSteamDir(@"C:\does\not\exist"));
    }

    [Fact]
    public void CandidatesNeverThrows()
    {
        // On Linux this is empty; on Windows it lists registry/ProgramFiles paths.
        var candidates = SteamPathLocator.Candidates();
        Assert.NotNull(candidates);
    }
}
