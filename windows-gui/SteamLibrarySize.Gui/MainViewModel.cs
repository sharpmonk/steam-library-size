using System.Collections.ObjectModel;
using System.IO;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using SteamLibrarySize.Core;

namespace SteamLibrarySize.Gui;

public partial class MainViewModel : ObservableObject
{
    [ObservableProperty] private string _steamPath = "";
    [ObservableProperty] private bool _isScanning;
    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private string _headline = "";
    [ObservableProperty] private double _progressValue;
    [ObservableProperty] private bool _includeDlc;
    [ObservableProperty] private bool _hasResults;

    public ObservableCollection<AppRow> Apps { get; } = [];
    private FetchResult? _lastResult;

    public MainViewModel()
    {
        SteamPath = SteamPathLocator.FindSteamDir() ?? "";
        StatusText = SteamPath == ""
            ? "Steam not found — click Browse and pick your Steam folder."
            : "Ready. Click Scan.";
    }

    [RelayCommand(CanExecute = nameof(CanScan))]
    private async Task ScanAsync()
    {
        IsScanning = true;
        HasResults = false;
        ProgressValue = 0;
        Apps.Clear();
        try
        {
            StatusText = "Reading Steam licenses...";
            var grants = await Task.Run(() =>
                PackageInfoParser.ReadLicenses(Path.Combine(SteamPath, "appcache", "packageinfo.vdf")));
            StatusText = $"Licenses grant {grants.AppIds.Count} apps. Connecting to Steam...";

            using var source = await SteamKitProductInfoSource.ConnectAnonymousAsync(
                TimeSpan.FromSeconds(30), CancellationToken.None);
            var progress = new Progress<(int Done, int Total)>(p =>
            {
                ProgressValue = 100.0 * p.Done / p.Total;
                StatusText = $"Fetching sizes... {p.Done}/{p.Total} apps";
            });
            _lastResult = await new SizeFetcher(source)
                .FetchAsync(grants.AppIds, OsChoice.Windows,
                            grants.DepotIds.Count > 0 ? grants.DepotIds : null, progress);

            RefreshView();
            HasResults = true;
        }
        catch (UnsupportedFormatException ex) { StatusText = ex.Message; }
        catch (InvalidDataException ex) { StatusText = ex.Message; }
        catch (SteamConnectException ex) { StatusText = ex.Message; }
        catch (IOException ex) { StatusText = $"Could not read Steam files: {ex.Message}"; }
        finally { IsScanning = false; }
    }

    private bool CanScan() => !IsScanning && SteamPath != "";

    partial void OnSteamPathChanged(string value) => ScanCommand.NotifyCanExecuteChanged();
    partial void OnIsScanningChanged(bool value) => ScanCommand.NotifyCanExecuteChanged();
    partial void OnIncludeDlcChanged(bool value) { if (_lastResult is not null) RefreshView(); }

    private void RefreshView()
    {
        if (_lastResult is null) return;
        Apps.Clear();
        var visible = _lastResult.Apps
            .Where(a => a.Type == "game" || (IncludeDlc && a.Type == "dlc"))
            .OrderByDescending(a => a.SizeBytes);
        foreach (var a in visible) Apps.Add(AppRow.From(a));
        var totals = LibraryTotals.Compute(_lastResult.Apps);
        Headline = totals.Headline(IncludeDlc);
        StatusText = _lastResult.SkippedAppIds.Count switch
        {
            0 => "Done. Sizes are fresh-install depot sizes (public branch, English).",
            1 => "Done. 1 app could not be fetched and is not counted.",
            var n => $"Done. {n} apps could not be fetched and are not counted."
        };
    }

    [RelayCommand]
    private void Browse()
    {
        var dialog = new Microsoft.Win32.OpenFolderDialog { Title = "Select your Steam folder" };
        if (dialog.ShowDialog() != true) return;
        if (SteamPathLocator.IsValidSteamDir(dialog.FolderName))
        {
            SteamPath = dialog.FolderName;
            StatusText = "Ready. Click Scan.";
        }
        else
        {
            StatusText = "That folder has no appcache\\packageinfo.vdf — start Steam once, then retry.";
        }
    }

    [RelayCommand]
    private void ExportCsv()
    {
        if (_lastResult is null) return;
        var dialog = new Microsoft.Win32.SaveFileDialog
        {
            FileName = "steam-library-size.csv",
            Filter = "CSV files (*.csv)|*.csv"
        };
        if (dialog.ShowDialog() != true) return;
        using var writer = new StreamWriter(dialog.FileName);
        CsvExporter.Write(writer, _lastResult.Apps);
        StatusText = $"Exported {_lastResult.Apps.Count} rows to {dialog.FileName}";
    }
}
