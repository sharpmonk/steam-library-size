using SteamKit2;

namespace SteamLibrarySize.Core;

public sealed class SteamConnectException(string message) : Exception(message);

/// <summary>Real PICS source: anonymous SteamKit2 session with a background callback pump.</summary>
public sealed class SteamKitProductInfoSource : IProductInfoSource
{
    private readonly SteamClient _client;
    private readonly CallbackManager _manager;
    private readonly SteamApps _steamApps;
    private readonly CancellationTokenSource _pumpCts = new();
    private readonly Task _pumpTask;

    private SteamKitProductInfoSource(SteamClient client, CallbackManager manager, SteamApps steamApps)
    {
        _client = client;
        _manager = manager;
        _steamApps = steamApps;
        _pumpTask = Task.Run(() =>
        {
            while (!_pumpCts.IsCancellationRequested)
                _manager.RunWaitCallbacks(TimeSpan.FromMilliseconds(200));
        });
    }

    public static async Task<SteamKitProductInfoSource> ConnectAnonymousAsync(TimeSpan timeout, CancellationToken ct)
    {
        var client = new SteamClient();
        var manager = new CallbackManager(client);
        var user = client.GetHandler<SteamUser>()!;
        var apps = client.GetHandler<SteamApps>()!;
        var loggedOn = new TaskCompletionSource<EResult>(TaskCreationOptions.RunContinuationsAsynchronously);

        manager.Subscribe<SteamClient.ConnectedCallback>(_ => user.LogOnAnonymous());
        manager.Subscribe<SteamClient.DisconnectedCallback>(_ =>
            loggedOn.TrySetResult(EResult.NoConnection));
        manager.Subscribe<SteamUser.LoggedOnCallback>(cb => loggedOn.TrySetResult(cb.Result));

        client.Connect();
        var deadline = Task.Delay(timeout, ct);
        // pump manually until logged on (the background pump starts after construction)
        while (!loggedOn.Task.IsCompleted && !deadline.IsCompleted)
            manager.RunWaitCallbacks(TimeSpan.FromMilliseconds(200));

        if (!loggedOn.Task.IsCompleted || await loggedOn.Task.ConfigureAwait(false) != EResult.OK)
        {
            client.Disconnect();
            throw new SteamConnectException(
                "Anonymous Steam login failed. Check your internet connection and try again.");
        }
        return new SteamKitProductInfoSource(client, manager, apps);
    }

    public async Task<IReadOnlyDictionary<uint, KeyValue>> GetProductInfoAsync(
        IReadOnlyList<uint> appIds, CancellationToken ct)
    {
        var requests = appIds.Select(id => new SteamApps.PICSRequest(id)).ToList();
        var job = _steamApps.PICSGetProductInfo(requests, []);
        job.Timeout = TimeSpan.FromSeconds(60);
        var resultSet = await job.ToTask().WaitAsync(ct).ConfigureAwait(false);
        var found = new Dictionary<uint, KeyValue>();
        foreach (var callback in resultSet.Results ?? Enumerable.Empty<SteamApps.PICSProductInfoCallback>())
            foreach (var (appId, info) in callback.Apps)
                found[appId] = info.KeyValues;
        return found;
    }

    public void Dispose()
    {
        _pumpCts.Cancel();
        try { _client.Disconnect(); } catch { }
        try { _pumpTask.Wait(TimeSpan.FromSeconds(2)); } catch { }
        _pumpCts.Dispose();
    }
}
