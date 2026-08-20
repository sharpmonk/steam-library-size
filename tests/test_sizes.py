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


def test_windows_falls_back_to_linux_when_no_windows_depots():
    a = app([depot(10), depot(30, oslist="linux")])
    assert compute_app_size(a, "windows") == 40


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
