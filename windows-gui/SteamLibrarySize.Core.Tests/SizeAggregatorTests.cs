using SteamKit2;
using SteamLibrarySize.Core;
using Xunit;

namespace SteamLibrarySize.Core.Tests;

public class SizeAggregatorTests
{
    // Helper: build an app KeyValue with a depots node from (name, children) tuples.
    private static KeyValue App(params KeyValue[] depots)
    {
        var depotsNode = new KeyValue("depots");
        depotsNode.Children.AddRange(depots);
        var app = new KeyValue("123");
        app.Children.Add(depotsNode);
        return app;
    }

    private static KeyValue Depot(string id, long size, string oslist = "", string language = "",
                                  bool shared = false, bool stringManifest = false)
    {
        var d = new KeyValue(id);
        if (shared) d.Children.Add(new KeyValue("sharedinstall", "1"));
        var manifests = new KeyValue("manifests");
        if (stringManifest)
        {
            manifests.Children.Add(new KeyValue("public", "1234567890"));  // old v1 format
        }
        else
        {
            var pub = new KeyValue("public");
            pub.Children.Add(new KeyValue("size", size.ToString()));
            manifests.Children.Add(pub);
        }
        d.Children.Add(manifests);
        var config = new KeyValue("config");
        if (oslist != "") config.Children.Add(new KeyValue("oslist", oslist));
        if (language != "") config.Children.Add(new KeyValue("language", language));
        d.Children.Add(config);
        return d;
    }

    [Fact]
    public void SharedDepotCountsForEveryOs()
    {
        var app = App(Depot("1", 100));
        Assert.Equal(100, SizeAggregator.ComputeAppSize(app, OsChoice.Windows));
        Assert.Equal(100, SizeAggregator.ComputeAppSize(app, OsChoice.Linux));
        Assert.Equal(100, SizeAggregator.ComputeAppSize(app, OsChoice.All));
    }

    [Fact]
    public void PicksRequestedOsBucket()
    {
        var app = App(Depot("1", 100, oslist: "windows"), Depot("2", 30, oslist: "linux"));
        Assert.Equal(100, SizeAggregator.ComputeAppSize(app, OsChoice.Windows));
        Assert.Equal(30, SizeAggregator.ComputeAppSize(app, OsChoice.Linux));
        Assert.Equal(130, SizeAggregator.ComputeAppSize(app, OsChoice.All));
    }

    [Fact]
    public void FallsBackWhenRequestedOsHasNoDepots()
    {
        // macOS requested, only windows depots exist -> falls back to windows
        var app = App(Depot("1", 100, oslist: "windows"));
        Assert.Equal(100, SizeAggregator.ComputeAppSize(app, OsChoice.MacOs));
    }

    [Fact]
    public void SkipsNonEnglishSharedinstallAndV1Manifests()
    {
        var app = App(
            Depot("1", 100),
            Depot("2", 50, language: "german"),
            Depot("3", 25, shared: true),
            Depot("4", 12, stringManifest: true));
        Assert.Equal(100, SizeAggregator.ComputeAppSize(app, OsChoice.Windows));
    }

    [Fact]
    public void EnglishLanguageDepotCounts()
    {
        var app = App(Depot("1", 100), Depot("2", 40, language: "english"));
        Assert.Equal(140, SizeAggregator.ComputeAppSize(app, OsChoice.Windows));
    }

    [Fact]
    public void MultiOsOslistCountsInEachBucket()
    {
        var app = App(Depot("1", 100, oslist: "windows,linux"));
        Assert.Equal(100, SizeAggregator.ComputeAppSize(app, OsChoice.Windows));
        Assert.Equal(100, SizeAggregator.ComputeAppSize(app, OsChoice.Linux));
    }

    [Fact]
    public void AppWithoutDepotsIsZero()
    {
        Assert.Equal(0, SizeAggregator.ComputeAppSize(new KeyValue("123"), OsChoice.Windows));
    }

    [Fact]
    public void SharedDepotsSufficeNoCrossOsFallback()
    {
        // Where Winds Meet bug: shared depots cover the install; an empty
        // windows bucket must NOT drag in the linux (Steam Deck) depot.
        var app = App(Depot("1", 100), Depot("2", 60, oslist: "linux"));
        Assert.Equal(100, SizeAggregator.ComputeAppSize(app, OsChoice.Windows));
    }

    [Fact]
    public void GrantedDepotsFiltersUnlicensedTwins()
    {
        var app = App(Depot("101", 100), Depot("102", 100));
        var granted = new HashSet<uint> { 101 };
        Assert.Equal(100, SizeAggregator.ComputeAppSize(app, OsChoice.Windows, granted));
        Assert.Equal(200, SizeAggregator.ComputeAppSize(app, OsChoice.Windows));       // no gating
    }
}
