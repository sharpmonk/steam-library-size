using SteamKit2;
using SteamLibrarySize.Core;
using Xunit;

namespace SteamLibrarySize.Core.Tests;

public class PackageInfoParserTests
{
    private const uint MagicV27 = 0x06565527;
    private const uint MagicV28 = 0x06565528;

    private static byte[] PackageBlob(uint pkgId, uint[] appIds, uint[] depotIds)
    {
        var pkg = new KeyValue(pkgId.ToString());
        var appids = new KeyValue("appids");
        for (int i = 0; i < appIds.Length; i++)
            appids.Children.Add(new KeyValue(i.ToString(), appIds[i].ToString()));
        pkg.Children.Add(appids);
        if (depotIds.Length > 0)
        {
            var depotids = new KeyValue("depotids");
            for (int i = 0; i < depotIds.Length; i++)
                depotids.Children.Add(new KeyValue(i.ToString(), depotIds[i].ToString()));
            pkg.Children.Add(depotids);
        }
        using var ms = new MemoryStream();
        pkg.SaveToStream(ms, asBinary: true);
        return ms.ToArray();
    }

    private static byte[] Fixture(uint magic, params (uint pkgId, uint[] appIds, uint[] depotIds)[] packages)
    {
        using var ms = new MemoryStream();
        using var w = new BinaryWriter(ms);
        w.Write(magic);
        w.Write(1u);                        // universe
        int headerSkip = magic == MagicV27 ? 24 : 32;
        foreach (var (pkgId, appIds, depotIds) in packages)
        {
            w.Write(pkgId);
            w.Write(new byte[headerSkip]);  // sha1 + changenumber (+ token in v28)
            w.Write(PackageBlob(pkgId, appIds, depotIds));
        }
        w.Write(0xFFFFFFFFu);               // terminator
        return ms.ToArray();
    }

    [Fact]
    public void ReadsAppIdsAndDepotIdsFromV27()
    {
        var bytes = Fixture(MagicV27,
            (10u, new uint[] { 220, 440 }, new uint[] { 221, 441 }),
            (20u, new uint[] { 440, 570 }, new uint[] { 441, 571 }));
        var grants = PackageInfoParser.ReadLicenses(new MemoryStream(bytes));
        Assert.Equal(new HashSet<uint> { 220, 440, 570 }, grants.AppIds);
        Assert.Equal(new HashSet<uint> { 221, 441, 571 }, grants.DepotIds);
    }

    [Fact]
    public void ReadsAppIdsAndDepotIdsFromV28()
    {
        var bytes = Fixture(MagicV28, (10u, new uint[] { 220 }, new uint[] { 221 }));
        var grants = PackageInfoParser.ReadLicenses(new MemoryStream(bytes));
        Assert.Equal(new HashSet<uint> { 220 }, grants.AppIds);
        Assert.Equal(new HashSet<uint> { 221 }, grants.DepotIds);
    }

    [Fact]
    public void PackageWithoutDepotidsIsHandled()
    {
        var bytes = Fixture(MagicV28, (10u, new uint[] { 220 }, Array.Empty<uint>()));
        var grants = PackageInfoParser.ReadLicenses(new MemoryStream(bytes));
        Assert.Equal(new HashSet<uint> { 220 }, grants.AppIds);
        Assert.Empty(grants.DepotIds);
    }

    [Fact]
    public void UnknownMagicThrows()
    {
        var bytes = Fixture(0x06565529, (10u, new uint[] { 220 }, new uint[] { 221 }));
        var ex = Assert.Throws<UnsupportedFormatException>(
            () => PackageInfoParser.ReadLicenses(new MemoryStream(bytes)));
        Assert.Equal(0x06565529u, ex.Magic);
        Assert.Contains("github.com/sharpmonk/steam-library-size/issues", ex.Message);
    }

    [Fact]
    public void TruncatedFileStopsCleanly()
    {
        var full = Fixture(MagicV28, (10u, new uint[] { 220 }, new uint[] { 221 }));
        var truncated = full[..^4];         // drop the terminator
        var grants = PackageInfoParser.ReadLicenses(new MemoryStream(truncated));
        Assert.Equal(new HashSet<uint> { 220 }, grants.AppIds);
        Assert.Equal(new HashSet<uint> { 221 }, grants.DepotIds);
    }

    // Guarded by File.Exists rather than [SkippableFact]: on this SDK/VSTest
    // combo, Xunit.SkippableFact 1.5.61 (the latest published version) makes
    // `dotnet test` exit non-zero ("Result reported for unknown test case" /
    // "VSTestTask task returned false but did not log an error") even though
    // the underlying xunit run reports the test itself as passed. See the
    // task report for the exact repro. A plain guarded Fact avoids the
    // broken adapter path while still skipping cleanly when the file (or a
    // different machine without it) is absent.
    [Fact]
    public void ParsesRealPackageInfoIfPresent()
    {
        var path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            ".local/share/Steam/appcache/packageinfo.vdf");
        if (!File.Exists(path)) return;
        var grants = PackageInfoParser.ReadLicenses(path);
        Assert.True(grants.AppIds.Count > 100, $"expected hundreds of appids, got {grants.AppIds.Count}");
        Assert.True(grants.DepotIds.Count > 100, $"expected hundreds of depotids, got {grants.DepotIds.Count}");
    }
}
