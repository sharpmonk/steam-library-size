from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

# preference order per requested OS: first entry with depots wins
_FALLBACK = {
    "windows": ("windows", "linux", "macos"),
    "linux": ("linux", "windows", "macos"),
    "macos": ("macos", "windows", "linux"),
}


@dataclass
class AppSize:
    appid: int
    name: str
    type: str
    size_bytes: int


@dataclass
class FetchResult:
    apps: list[AppSize] = field(default_factory=list)
    skipped_appids: list[int] = field(default_factory=list)


def compute_app_size(app: dict, os_choice: str, granted_depots: set[int] | None = None) -> int:
    """Install size in bytes: public-branch depots, English only, per-OS.

    granted_depots, when given, limits the sum to depots the account's
    licenses actually grant - apps can carry region/variant twins of the
    same content and a real install only downloads the licensed one.
    """
    shared = 0
    per_os = {"windows": 0, "linux": 0, "macos": 0}
    for depot_id, depot in app.get("depots", {}).items():
        if not isinstance(depot, dict):
            continue
        if granted_depots is not None and depot_id.isdigit() and int(depot_id) not in granted_depots:
            continue
        if depot.get("sharedinstall"):
            continue
        manifest = depot.get("manifests", {}).get("public")
        if not isinstance(manifest, dict):
            continue
        size = int(manifest.get("size", 0))
        config = depot.get("config", {})
        language = config.get("language", "")
        if language and language != "english":
            continue
        oslist = config.get("oslist", "")
        if not oslist:
            shared += size
        else:
            for os_name in per_os:
                if os_name in oslist:
                    per_os[os_name] += size
    if os_choice == "all":
        return shared + sum(per_os.values())
    if per_os[os_choice] or shared:
        return shared + per_os[os_choice]
    # nothing counted for this OS at all: fall back to another OS's depots
    # (e.g. a mac user sizing a game that only ships windows depots)
    for os_name in _FALLBACK[os_choice]:
        if per_os[os_name]:
            return per_os[os_name]
    return 0


CHUNK_SIZE = 50


class SteamConnectError(Exception):
    pass


def fetch_app_sizes(
    appids: Iterable[int],
    os_choice: str,
    progress_cb: Callable[[str], None] = lambda msg: None,
    granted_depots: set[int] | None = None,
) -> FetchResult:
    """Anonymously fetch product info for appids and compute install sizes."""
    import steam.client  # heavy import (gevent); deferred so tests can patch it
    from steam.enums import EResult

    ids = sorted({int(a) for a in appids})
    client = steam.client.SteamClient()
    login = client.anonymous_login()
    if login != EResult.OK:
        raise SteamConnectError(
            f"Anonymous Steam login failed ({login!r}). "
            "Check your internet connection and try again."
        )
    result = FetchResult()
    try:
        for start in range(0, len(ids), CHUNK_SIZE):
            chunk = ids[start : start + CHUNK_SIZE]
            info = None
            for attempt in (1, 2):
                try:
                    info = client.get_product_info(apps=chunk, timeout=60)
                    break
                except Exception as exc:  # noqa: BLE001 - any transport error
                    if attempt == 2:
                        progress_cb(f"warning: giving up on a chunk of {len(chunk)} apps ({exc})")
            if not info:
                result.skipped_appids.extend(chunk)
                continue
            apps = info.get("apps", {})
            for appid in chunk:
                app = apps.get(appid)
                if app is None:
                    result.skipped_appids.append(appid)
                    continue
                common = app.get("common", {})
                result.apps.append(
                    AppSize(
                        appid=appid,
                        name=common.get("name", f"app {appid}"),
                        type=common.get("type", "").lower(),
                        size_bytes=compute_app_size(app, os_choice, granted_depots),
                    )
                )
            progress_cb(f"fetched {min(start + CHUNK_SIZE, len(ids))}/{len(ids)} apps")
    finally:
        client.logout()
    return result
