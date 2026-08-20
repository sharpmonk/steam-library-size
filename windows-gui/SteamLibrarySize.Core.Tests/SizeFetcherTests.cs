using SteamKit2;
using SteamLibrarySize.Core;
using Xunit;

namespace SteamLibrarySize.Core.Tests;

public class SizeFetcherTests
{
    private sealed class FakeSource : IProductInfoSource
    {
        public List<IReadOnlyList<uint>> Calls = [];
        public Func<IReadOnlyList<uint>, IReadOnlyDictionary<uint, KeyValue>> Handler = _ => new Dictionary<uint, KeyValue>();
        public Task<IReadOnlyDictionary<uint, KeyValue>> GetProductInfoAsync(IReadOnlyList<uint> appIds, CancellationToken ct)
        {
            Calls.Add(appIds);
            return Task.FromResult(Handler(appIds));
        }
        public void Dispose() { }
    }

    private static KeyValue AppNode(string name, string type, long size)
    {
        var app = new KeyValue("app");
        var common = new KeyValue("common");
        common.Children.Add(new KeyValue("name", name));
        common.Children.Add(new KeyValue("type", type));
        app.Children.Add(common);
        var depots = new KeyValue("depots");
        var d = new KeyValue("1");
        var manifests = new KeyValue("manifests");
        var pub = new KeyValue("public");
        pub.Children.Add(new KeyValue("size", size.ToString()));
        manifests.Children.Add(pub);
        d.Children.Add(manifests);
        depots.Children.Add(d);
        app.Children.Add(depots);
        return app;
    }

    [Fact]
    public async Task MapsNameTypeAndSize()
    {
        var src = new FakeSource
        {
            Handler = ids => new Dictionary<uint, KeyValue> { [220] = AppNode("Half-Life 2", "Game", 7_000_000_000) }
        };
        var result = await new SizeFetcher(src).FetchAsync([220], OsChoice.Windows);
        var app = Assert.Single(result.Apps);
        Assert.Equal(220u, app.AppId);
        Assert.Equal("Half-Life 2", app.Name);
        Assert.Equal("game", app.Type);               // lowercased
        Assert.Equal(7_000_000_000, app.SizeBytes);
        Assert.Empty(result.SkippedAppIds);
    }

    [Fact]
    public async Task DedupesSortsAndChunksBy50()
    {
        var ids = Enumerable.Range(1, 120).Select(i => (uint)i).Concat([(uint)1]);
        var src = new FakeSource();
        await new SizeFetcher(src).FetchAsync(ids, OsChoice.Windows);
        Assert.Equal(3, src.Calls.Count);
        Assert.Equal(50, src.Calls[0].Count);
        Assert.Equal(20, src.Calls[2].Count);
        Assert.Equal((uint)1, src.Calls[0][0]);       // sorted
    }

    [Fact]
    public async Task MissingAppsAreSkipped()
    {
        var src = new FakeSource();                    // returns nothing for any id
        var result = await new SizeFetcher(src).FetchAsync([220, 440], OsChoice.Windows);
        Assert.Empty(result.Apps);
        Assert.Equal(new uint[] { 220, 440 }, result.SkippedAppIds);
    }

    [Fact]
    public async Task ChunkRetriesOnceThenSkips()
    {
        int calls = 0;
        var src = new FakeSource { Handler = _ => { calls++; throw new IOException("net down"); } };
        var result = await new SizeFetcher(src).FetchAsync([220], OsChoice.Windows);
        Assert.Equal(2, calls);                        // one retry
        Assert.Equal(new uint[] { 220 }, result.SkippedAppIds);
    }

    [Fact]
    public async Task ChunkRetriesOnceThenSkipsOnSpuriousTaskCanceled()
    {
        // SteamKit2 fails timed-out/disconnected jobs by cancelling the task, even though
        // the caller's own CancellationToken was never signalled. That must be treated as
        // an ordinary transient failure (retry once, then skip) — not rethrown as a real
        // cancellation.
        int calls = 0;
        var src = new FakeSource { Handler = _ => { calls++; throw new TaskCanceledException("job timed out"); } };
        var result = await new SizeFetcher(src).FetchAsync([220], OsChoice.Windows);
        Assert.Equal(2, calls);                        // one retry
        Assert.Equal(new uint[] { 220 }, result.SkippedAppIds);
    }

    [Fact]
    public async Task ReportsProgress()
    {
        var src = new FakeSource();
        var reports = new List<(int Done, int Total)>();
        await new SizeFetcher(src).FetchAsync(Enumerable.Range(1, 60).Select(i => (uint)i),
            OsChoice.Windows, progress: new SynchronousProgress<(int Done, int Total)>(reports.Add));
        Assert.Equal([(50, 60), (60, 60)], reports);
    }

    [Fact]
    public async Task GrantedDepotsGatesComputedSize()
    {
        var src = new FakeSource
        {
            Handler = ids => new Dictionary<uint, KeyValue> { [220] = AppNode("Half-Life 2", "Game", 7_000_000_000) }
        };
        var excluded = await new SizeFetcher(src).FetchAsync([220], OsChoice.Windows, new HashSet<uint> { 999 });
        Assert.Equal(0, Assert.Single(excluded.Apps).SizeBytes);

        var included = await new SizeFetcher(src).FetchAsync([220], OsChoice.Windows, new HashSet<uint> { 1 });
        Assert.Equal(7_000_000_000, Assert.Single(included.Apps).SizeBytes);
    }

    // System.Progress<T> posts to a sync context and is flaky in tests; use a synchronous stand-in.
    private sealed class SynchronousProgress<T>(Action<T> action) : IProgress<T>
    {
        public void Report(T value) => action(value);
    }
}
