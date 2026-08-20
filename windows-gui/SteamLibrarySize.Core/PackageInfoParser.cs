using SteamKit2;

namespace SteamLibrarySize.Core;

public sealed class UnsupportedFormatException(uint magic) : Exception(
    $"packageinfo.vdf has unrecognized format magic 0x{magic:x8}. " +
    "Steam may have changed the file format - please file an issue at " +
    "https://github.com/sharpmonk/steam-library-size/issues")
{
    public uint Magic { get; } = magic;
}

/// <summary>appids and depotids granted by the account's cached licenses.
/// depotids matter because Steam ships region/variant twins of the same
/// content as separate depots on one app; a real install only downloads
/// the depots your licenses grant.</summary>
public sealed record LicenseGrants(HashSet<uint> AppIds, HashSet<uint> DepotIds);

public static class PackageInfoParser
{
    private const uint MagicV27 = 0x06565527;
    private const uint MagicV28 = 0x06565528;
    private const uint Terminator = 0xFFFFFFFF;

    public static LicenseGrants ReadLicenses(string path)
    {
        using var stream = File.OpenRead(path);
        return ReadLicenses(stream);
    }

    /// <summary>Port of read_licenses() in the Python CLI.</summary>
    public static LicenseGrants ReadLicenses(Stream stream)
    {
        using var reader = new BinaryReader(stream);
        uint magic = reader.ReadUInt32();
        if (magic is not (MagicV27 or MagicV28)) throw new UnsupportedFormatException(magic);
        reader.ReadUInt32();                                  // universe
        int headerSkip = magic == MagicV27 ? 24 : 32;

        var appIds = new HashSet<uint>();
        var depotIds = new HashSet<uint>();
        while (true)
        {
            uint pkgId;
            try { pkgId = reader.ReadUInt32(); }
            catch (EndOfStreamException) { break; }
            if (pkgId == Terminator) break;
            reader.BaseStream.Seek(headerSkip, SeekOrigin.Current);
            var pkg = new KeyValue();
            if (!pkg.TryReadAsBinary(stream)) break;          // corrupt blob: stop, keep what we have
            foreach (var child in pkg["appids"].Children)
                appIds.Add((uint)child.AsUnsignedLong());
            foreach (var child in pkg["depotids"].Children)
                depotIds.Add((uint)child.AsUnsignedLong());
        }
        return new LicenseGrants(appIds, depotIds);
    }
}
