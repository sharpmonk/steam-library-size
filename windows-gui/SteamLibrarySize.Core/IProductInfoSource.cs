using SteamKit2;

namespace SteamLibrarySize.Core;

/// <summary>Abstracts SteamKit2's PICS product-info call so SizeFetcher is testable offline.</summary>
public interface IProductInfoSource : IDisposable
{
    /// <summary>Returns the app KeyValue node per found appid; missing ids are simply absent.
    /// Throws on transport failure (caller retries).</summary>
    Task<IReadOnlyDictionary<uint, KeyValue>> GetProductInfoAsync(IReadOnlyList<uint> appIds, CancellationToken ct);
}
