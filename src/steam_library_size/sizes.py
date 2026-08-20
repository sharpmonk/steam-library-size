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


def compute_app_size(app: dict, os_choice: str) -> int:
    """Install size in bytes: public-branch depots, English only, per-OS."""
    shared = 0
    per_os = {"windows": 0, "linux": 0, "macos": 0}
    for depot in app.get("depots", {}).values():
        if not isinstance(depot, dict):
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
    for os_name in _FALLBACK[os_choice]:
        if per_os[os_name]:
            return shared + per_os[os_name]
    return shared
