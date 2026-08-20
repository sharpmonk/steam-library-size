using SteamKit2;

namespace SteamLibrarySize.Core;

public sealed class SizeFetcher(IProductInfoSource source)
{
    public const int ChunkSize = 50;

    /// <summary>Fetch product info for appids and compute install sizes.
    /// Port of fetch_app_sizes() in the Python CLI.</summary>
    public async Task<FetchResult> FetchAsync(
        IEnumerable<uint> appIds, OsChoice osChoice,
        IReadOnlySet<uint>? grantedDepots = null,
        IProgress<(int Done, int Total)>? progress = null, CancellationToken ct = default)
    {
        var ids = appIds.Distinct().OrderBy(i => i).ToList();
        var apps = new List<AppSize>();
        var skipped = new List<uint>();

        for (int start = 0; start < ids.Count; start += ChunkSize)
        {
            ct.ThrowIfCancellationRequested();
            var chunk = ids.GetRange(start, Math.Min(ChunkSize, ids.Count - start));
            IReadOnlyDictionary<uint, KeyValue>? info = null;
            for (int attempt = 1; attempt <= 2 && info is null; attempt++)
            {
                try { info = await source.GetProductInfoAsync(chunk, ct).ConfigureAwait(false); }
                catch (OperationCanceledException) { throw; }
                catch (Exception) when (attempt == 1) { /* retry once */ }
                catch (Exception) { /* second failure: skip chunk */ }
            }
            if (info is null) { skipped.AddRange(chunk); continue; }

            foreach (var appId in chunk)
            {
                if (!info.TryGetValue(appId, out var app)) { skipped.Add(appId); continue; }
                var common = app["common"];
                apps.Add(new AppSize(
                    appId,
                    common["name"].AsString() ?? $"app {appId}",
                    (common["type"].AsString() ?? "").ToLowerInvariant(),
                    SizeAggregator.ComputeAppSize(app, osChoice, grantedDepots)));
            }
            progress?.Report((Math.Min(start + ChunkSize, ids.Count), ids.Count));
        }
        return new FetchResult(apps, skipped);
    }
}
