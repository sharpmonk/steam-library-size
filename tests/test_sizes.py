from steam_library_size.sizes import AppSize, FetchResult, compute_app_size

GB = 1024**3


def depot(size, oslist=None, language=None, sharedinstall=False, no_manifest=False):
    d = {"config": {}}
    if not no_manifest:
        d["manifests"] = {"public": {"gid": "1", "size": str(size)}}
    if oslist is not None:
        d["config"]["oslist"] = oslist
    if language is not None:
        d["config"]["language"] = language
    if sharedinstall:
        d["sharedinstall"] = "1"
    return d


def app(depots):
    return {"depots": {str(i): d for i, d in enumerate(depots)}}


def test_shared_plus_windows():
    a = app([depot(10), depot(20, oslist="windows"), depot(30, oslist="linux")])
    assert compute_app_size(a, "windows") == 30
    assert compute_app_size(a, "linux") == 40
    assert compute_app_size(a, "all") == 60


def test_shared_depots_suffice_no_cross_os_fallback():
    # Where Winds Meet bug: shared depots cover the install; an empty windows
    # bucket must NOT drag in the linux (Steam Deck) depot.
    a = app([depot(10), depot(30, oslist="linux")])
    assert compute_app_size(a, "windows") == 10


def test_windows_falls_back_to_linux_when_nothing_else_counted():
    # True fallback: no shared depots, no windows depots -> use linux size
    # (a Mac/other-OS user sizing a game that only ships foreign-OS depots).
    a = app([depot(30, oslist="linux")])
    assert compute_app_size(a, "windows") == 30


def test_granted_depots_filters_unlicensed_twins():
    # Twin-depot bug: two identical shared depots, licenses grant only one.
    a = {"depots": {
        "101": depot(100),
        "102": depot(100),
        "103": depot(60, oslist="linux"),
    }}
    assert compute_app_size(a, "windows", granted_depots={101, 103}) == 100
    assert compute_app_size(a, "windows") == 200                    # no gating: count both
    assert compute_app_size(a, "windows", granted_depots=None) == 200


def test_granted_depots_ignores_non_numeric_depot_keys():
    a = {"depots": {"branches": {"public": {"buildid": "1"}}, "0": depot(10)}}
    assert compute_app_size(a, "windows", granted_depots={0}) == 10


def test_non_english_language_depots_skipped():
    a = app([depot(10), depot(50, language="german"), depot(5, language="english")])
    assert compute_app_size(a, "windows") == 15


def test_sharedinstall_and_manifestless_depots_skipped():
    a = app([depot(10), depot(99, sharedinstall=True), depot(77, no_manifest=True)])
    assert compute_app_size(a, "windows") == 10


def test_non_dict_depot_entries_ignored():
    a = {"depots": {"branches": {"public": {"buildid": "1"}}, "0": depot(10), "baselanguages": "english"}}
    assert compute_app_size(a, "windows") == 10


def test_no_depots():
    assert compute_app_size({}, "windows") == 0


def test_dataclasses():
    r = FetchResult()
    r.apps.append(AppSize(appid=440, name="Team Fortress 2", type="game", size_bytes=GB))
    assert r.skipped_appids == []


import pytest

from steam_library_size.sizes import CHUNK_SIZE, SteamConnectError, fetch_app_sizes


class FakeClient:
    """Serves 2 known apps; appid 30 is a hole to test skip accounting."""

    login_ok = True
    fail_forever_on = set()  # appids whose chunk should raise every attempt

    def __init__(self):
        self.calls = 0

    def anonymous_login(self):
        from steam.enums import EResult

        return EResult.OK if self.login_ok else EResult.Fail

    def logout(self):
        pass

    def get_product_info(self, apps, timeout=60):
        self.calls += 1
        if set(apps) & self.fail_forever_on:
            raise TimeoutError("boom")
        catalog = {
            10: {"common": {"name": "Tiny Game", "type": "Game"},
                 "depots": {"0": {"config": {}, "manifests": {"public": {"size": "100"}}}}},
            20: {"common": {"name": "A DLC", "type": "DLC"}, "depots": {}},
            # appid 30 intentionally absent from responses
        }
        return {"apps": {a: catalog[a] for a in apps if a in catalog}}


@pytest.fixture
def fake_client(monkeypatch):
    FakeClient.login_ok = True
    FakeClient.fail_forever_on = set()
    monkeypatch.setattr("steam.client.SteamClient", FakeClient)
    return FakeClient


def test_fetch_passes_granted_depots_through(fake_client):
    # depot "0" of app 10 is not granted -> size collapses to 0
    result = fetch_app_sizes([10], "windows", granted_depots={999})
    assert result.apps[0].size_bytes == 0
    result = fetch_app_sizes([10], "windows", granted_depots={0})
    assert result.apps[0].size_bytes == 100


def test_fetch_happy_path(fake_client):
    result = fetch_app_sizes([10, 20, 30], "windows")
    by_id = {a.appid: a for a in result.apps}
    assert by_id[10].name == "Tiny Game"
    assert by_id[10].type == "game"          # lowercased
    assert by_id[10].size_bytes == 100
    assert by_id[20].size_bytes == 0
    assert result.skipped_appids == [30]     # missing from response -> skipped


def test_fetch_failed_chunk_is_skipped_not_fatal(fake_client):
    fake_client.fail_forever_on = {10}
    messages = []
    result = fetch_app_sizes([10, 20], "windows", progress_cb=messages.append)
    # 10 and 20 share one chunk (< CHUNK_SIZE apps), so both end up skipped
    assert sorted(result.skipped_appids) == [10, 20]
    assert result.apps == []
    assert any("giving up" in m for m in messages)


def test_login_failure_raises(fake_client):
    fake_client.login_ok = False
    with pytest.raises(SteamConnectError):
        fetch_app_sizes([10], "windows")


def test_chunk_size_is_50():
    assert CHUNK_SIZE == 50
