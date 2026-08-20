using SteamLibrarySize.Core;
using Xunit;

namespace SteamLibrarySize.Core.Tests;

public class CsvExporterTests
{
    [Fact]
    public void WritesHeaderAndQuotesSpecials()
    {
        var sw = new StringWriter();
        CsvExporter.Write(sw, [new AppSize(220, "Half-Life 2", "game", 7), new AppSize(1, "A, \"B\"", "dlc", 8)]);
        var lines = sw.ToString().TrimEnd().Split('\n').Select(l => l.TrimEnd('\r')).ToArray();
        Assert.Equal("appid,name,type,size_bytes", lines[0]);
        Assert.Equal("220,Half-Life 2,game,7", lines[1]);
        Assert.Equal("1,\"A, \"\"B\"\"\",dlc,8", lines[2]);
    }
}
