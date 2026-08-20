using SteamLibrarySize.Core;
using Xunit;

namespace SteamLibrarySize.Core.Tests;

public class LibraryTotalsTests
{
    private static readonly AppSize[] Apps =
    [
        new(1, "Game A", "game", 100),
        new(2, "Game B", "game", 50),
        new(3, "DLC A", "dlc", 10),
        new(4, "Tool A", "tool", 5),
        new(5, "Demo A", "demo", 2),
    ];

    [Fact]
    public void SplitsByType()
    {
        var t = LibraryTotals.Compute(Apps);
        Assert.Equal((2, 1, 2), (t.GameCount, t.DlcCount, t.OtherCount));
        Assert.Equal((150L, 10L, 7L), (t.GameBytes, t.DlcBytes, t.OtherBytes));
    }

    [Fact]
    public void TotalRespectsDlcToggle()
    {
        var t = LibraryTotals.Compute(Apps);
        Assert.Equal(150, t.TotalBytes(includeDlc: false));
        Assert.Equal(160, t.TotalBytes(includeDlc: true));
    }

    [Fact]
    public void HeadlineFormatsGbAndTib()
    {
        var t = LibraryTotals.Compute([new(1, "Big", "game", 6_875_000_000_000)]);
        Assert.Equal("1 game — 6,402.8 GB (6.25 TiB)", t.Headline(includeDlc: false));
    }
}
