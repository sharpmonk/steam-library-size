using SteamKit2;

namespace SteamLibrarySize.Core;

public static class SizeAggregator
{
    private static readonly Dictionary<OsChoice, string[]> Fallback = new()
    {
        [OsChoice.Windows] = ["windows", "linux", "macos"],
        [OsChoice.Linux] = ["linux", "windows", "macos"],
        [OsChoice.MacOs] = ["macos", "windows", "linux"],
    };

    /// <summary>Install size in bytes: public-branch depots, English only, per-OS,
    /// limited to license-granted depots when grantedDepots is provided.
    /// Direct port of compute_app_size() in the Python CLI (post-d26149f).</summary>
    public static long ComputeAppSize(KeyValue app, OsChoice osChoice, IReadOnlySet<uint>? grantedDepots = null)
    {
        long shared = 0;
        var perOs = new Dictionary<string, long> { ["windows"] = 0, ["linux"] = 0, ["macos"] = 0 };

        foreach (var depot in app["depots"].Children)
        {
            if (depot.Children.Count == 0) continue;               // not a dict
            if (grantedDepots is not null && uint.TryParse(depot.Name, out var depotId)
                && !grantedDepots.Contains(depotId)) continue;     // unlicensed twin/variant depot
            if (depot["sharedinstall"].AsBoolean()) continue;
            var manifest = depot["manifests"]["public"];
            if (manifest.Children.Count == 0) continue;            // v1 string manifest or absent
            long size = manifest["size"].AsLong();
            var config = depot["config"];
            var language = config["language"].AsString() ?? "";
            if (language != "" && language != "english") continue;
            var oslist = config["oslist"].AsString() ?? "";
            if (oslist == "")
            {
                shared += size;
            }
            else
            {
                foreach (var osName in perOs.Keys)
                    if (oslist.Contains(osName)) perOs[osName] += size;
            }
        }

        if (osChoice == OsChoice.All) return shared + perOs.Values.Sum();
        var requested = Fallback[osChoice][0];
        if (perOs[requested] != 0 || shared != 0) return shared + perOs[requested];
        // nothing counted for this OS at all: fall back to another OS's depots
        foreach (var osName in Fallback[osChoice])
            if (perOs[osName] != 0) return perOs[osName];
        return 0;
    }
}
