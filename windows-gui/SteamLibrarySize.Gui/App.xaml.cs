using System.Windows;

namespace SteamLibrarySize.Gui;

/// <summary>
/// Interaction logic for App.xaml
/// </summary>
public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        DispatcherUnhandledException += (_, args) =>
        {
            var result = MessageBox.Show(
                $"Something went wrong:\n\n{args.Exception.Message}\n\nCopy details to clipboard?",
                "Steam Library Size", MessageBoxButton.YesNo, MessageBoxImage.Error);
            if (result == MessageBoxResult.Yes)
                Clipboard.SetText(args.Exception.ToString());
            args.Handled = true;
        };
    }
}
