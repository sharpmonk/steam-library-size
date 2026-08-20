using System.Globalization;

namespace SteamLibrarySize.Core;

public sealed record LibraryTotals(
    int GameCount, int DlcCount, int OtherCount,
    long GameBytes, long DlcBytes, long OtherBytes)
{
    private const double Gb = 1024.0 * 1024 * 1024;
    private const double Tib = Gb * 1024;

    public static LibraryTotals Compute(IEnumerable<AppSize> apps)
    {
        int gc = 0, dc = 0, oc = 0;
        long gb = 0, db = 0, ob = 0;
        foreach (var a in apps)
        {
            if (a.Type == "game") { gc++; gb += a.SizeBytes; }
            else if (a.Type == "dlc") { dc++; db += a.SizeBytes; }
            else { oc++; ob += a.SizeBytes; }
        }
        return new LibraryTotals(gc, dc, oc, gb, db, ob);
    }

    public long TotalBytes(bool includeDlc) => GameBytes + (includeDlc ? DlcBytes : 0);

    public string Headline(bool includeDlc)
    {
        long total = TotalBytes(includeDlc);
        string games = GameCount == 1 ? "1 game" : $"{GameCount} games";
        if (includeDlc) games += $" + {DlcCount} DLC";
        var ic = CultureInfo.InvariantCulture;
        return string.Create(ic, $"{games} — {total / Gb:N1} GB ({total / Tib:0.00} TiB)");
    }
}
