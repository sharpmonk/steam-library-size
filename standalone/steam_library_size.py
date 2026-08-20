#!/usr/bin/env python3
"""steam-library-size, single-file edition.

How big would your Steam library be if you installed every game you own?
Computed locally from your Steam client's license cache plus one anonymous
connection to Steam - no API key, no public profile needed.

This is the whole tool in one file for people who'd rather read and run a
script than install a package. It needs two libraries first:

    python3 -m pip install vdf "steam[client]"

Then:

    python3 steam_library_size.py

The packaged version (`pipx install steam-library-size`) is identical in
behavior and is the recommended way to run it day-to-day:
https://github.com/sharpmonk/steam-library-size

MIT License, Copyright (c) 2026 sharpmonk.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import vdf

__version__ = "0.1.0"


# --------------------------------------------------------------------------
# Locating the Steam install
# --------------------------------------------------------------------------

PACKAGEINFO = Path("appcache") / "packageinfo.vdf"


class SteamNotFoundError(Exception):
    def __init__(self, searched: list[Path]):
        self.searched = searched
        listing = "\n  ".join(str(p) for p in searched)
        super().__init__(
            "Could not find a Steam install containing appcache/packageinfo.vdf.\n"
            f"Searched:\n  {listing}\n"
            "Start Steam once so it writes its cache, or point me at it with --steam-dir."
        )


def _candidates() -> list[Path]:
    home = Path.home()
    if sys.platform == "win32":
        cands: list[Path] = []
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                cands.append(Path(winreg.QueryValueEx(key, "SteamPath")[0]))
        except OSError:
            pass
        for env in ("ProgramFiles(x86)", "ProgramFiles"):
            base = os.environ.get(env)
            if base:
                cands.append(Path(base) / "Steam")
        return cands
    if sys.platform == "darwin":
        return [home / "Library/Application Support/Steam"]
    return [
        home / ".local/share/Steam",
        home / ".steam/steam",
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
        home / "snap/steam/common/.local/share/Steam",
    ]


def find_steam_dir(override: str | None = None) -> Path:
    if override:
        p = Path(override).expanduser()
        if (p / PACKAGEINFO).is_file():
            return p
        raise SteamNotFoundError([p])
    searched = _candidates()
    for p in searched:
        if (p / PACKAGEINFO).is_file():
            return p
    raise SteamNotFoundError(searched)


# --------------------------------------------------------------------------
# Reading owned app IDs from the license cache
# --------------------------------------------------------------------------

MAGIC_V27 = 0x06565527
MAGIC_V28 = 0x06565528
_TERMINATOR = 0xFFFFFFFF


class UnsupportedFormatError(Exception):
    def __init__(self, magic: int):
        super().__init__(
            f"packageinfo.vdf has unrecognized format magic {magic:#010x}. "
            "Steam may have changed the file format - please file an issue at "
            "https://github.com/sharpmonk/steam-library-size/issues"
        )


def read_licenses(steam_dir: Path) -> tuple[set[int], set[int]]:
    """Return (appids, depotids) granted by the account's cached licenses.

    depotids matter because Steam ships region/variant twins of the same
    content as separate depots on one app; a real install only downloads
    the depots your licenses grant.
    """
    path = steam_dir / "appcache" / "packageinfo.vdf"
    appids: set[int] = set()
    depotids: set[int] = set()
    with open(path, "rb") as f:
        magic, _universe = struct.unpack("<II", f.read(8))
        if magic not in (MAGIC_V27, MAGIC_V28):
            raise UnsupportedFormatError(magic)
        # after the package id: sha1 (20) + change number (4) [+ PICS token (8) in v28]
        header_skip = 24 if magic == MAGIC_V27 else 32
        while True:
            raw = f.read(4)
            if len(raw) < 4:
                break
            (pkgid,) = struct.unpack("<I", raw)
            if pkgid == _TERMINATOR:
                break
            f.read(header_skip)
            data = vdf.binary_load(f)
            for pkg in data.values():
                for appid in pkg.get("appids", {}).values():
                    appids.add(int(appid))
                for depotid in pkg.get("depotids", {}).values():
                    depotids.add(int(depotid))
    return appids, depotids


def read_owned_appids(steam_dir: Path) -> set[int]:
    """Return every app ID granted by the account's cached licenses."""
    return read_licenses(steam_dir)[0]


# --------------------------------------------------------------------------
# Fetching and computing install sizes
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# CLI and report rendering
# --------------------------------------------------------------------------

GB = 1024**3
TB = 1024**4
DRIVE_SIZES_TB = (1, 2, 4, 8, 16)

CAVEATS = (
    "Note: sizes are fresh-install depot sizes (public branch, English). Games with\n"
    "optional depots (all CoD modes, ARK maps, HD packs) count everything, so those\n"
    "over-report a typical install. Shader cache, saves and workshop aren't included."
)


def default_os() -> str:
    if sys.platform == "darwin":
        return "macos"
    return "windows"  # Windows itself; Linux installs Windows depots via Proton


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="steam-library-size",
        description="How big would your Steam library be if you installed every game? "
        "Computed from your local Steam client - no API key, no public profile.",
    )
    p.add_argument("--top", type=int, default=20, metavar="N",
                   help="how many of the biggest games to list (default: 20)")
    fmt = p.add_mutually_exclusive_group()
    fmt.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    fmt.add_argument("--csv", action="store_true", help="emit one CSV row per app")
    p.add_argument("--include-dlc", action="store_true",
                   help="add owned DLC sizes to the headline total")
    p.add_argument("--include-all", action="store_true",
                   help="add everything owned (DLC, tools, demos, soundtracks, servers)")
    p.add_argument("--os", choices=["windows", "linux", "macos", "all"], default=None,
                   help="which platform's depots to size (default: your platform; "
                   "Linux uses Windows sizes, matching Proton installs)")
    p.add_argument("--steam-dir", default=None, metavar="PATH",
                   help="path to your Steam install if auto-detection fails")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _fmt(size: int) -> str:
    return f"{size / GB:,.1f} GB"


def _drive_line(total: int) -> str:
    for tb in DRIVE_SIZES_TB:
        if total <= tb * TB:
            article = "An" if tb == 8 else "A"
            return f"{article} {tb} TB drive would hold the lot."
    return "That's beyond a 16 TB drive - you'd need more than one."


def render_report(result: FetchResult, top: int, include_dlc: bool, include_all: bool) -> str:
    games = [a for a in result.apps if a.type == "game"]
    dlc = [a for a in result.apps if a.type == "dlc"]
    other = [a for a in result.apps if a.type not in ("game", "dlc")]
    game_bytes = sum(a.size_bytes for a in games)
    dlc_bytes = sum(a.size_bytes for a in dlc)
    other_bytes = sum(a.size_bytes for a in other)

    total = game_bytes
    label = f"{len(games)} games"
    if include_dlc or include_all:
        total += dlc_bytes
        label += f" + {len(dlc)} DLC"
    if include_all:
        total += other_bytes
        label += f" + {len(other)} other apps"

    lines = [
        f"Your Steam library: {label}",
        f"Installed all at once, that's {_fmt(total)} ({total / TB:.2f} TiB).",
        _drive_line(total),
        "",
        f"  Games: {_fmt(game_bytes)}   DLC: {_fmt(dlc_bytes)}   "
        f"Other (tools/demos/etc): {_fmt(other_bytes)}",
        "",
        f"Top {min(top, len(games))} biggest games:",
    ]
    for a in sorted(games, key=lambda a: -a.size_bytes)[:top]:
        lines.append(f"  {a.size_bytes / GB:9,.1f} GB  {a.name}")

    zero = sum(1 for a in games if a.size_bytes == 0)
    if zero:
        s = "" if zero == 1 else "s"
        lines.append(f"\n{zero} app{s} with no size data (usually delisted or test apps).")
    if result.skipped_appids:
        n = len(result.skipped_appids)
        s = "" if n == 1 else "s"
        lines.append(f"{n} app{s} could not be fetched and {'is' if n == 1 else 'are'} NOT counted.")
    lines += ["", CAVEATS]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    def progress(msg: str) -> None:
        print(msg, file=sys.stderr)

    try:
        steam_dir = find_steam_dir(args.steam_dir)
        print(f"Steam install: {steam_dir}", file=sys.stderr)
        appids, depotids = read_licenses(steam_dir)
        print(f"Licenses grant {len(appids)} apps; fetching sizes...", file=sys.stderr)
        result = fetch_app_sizes(appids, args.os or default_os(), progress_cb=progress,
                                 granted_depots=depotids or None)
    except (SteamNotFoundError, UnsupportedFormatError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except SteamConnectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        totals = {
            "game_bytes": sum(a.size_bytes for a in result.apps if a.type == "game"),
            "dlc_bytes": sum(a.size_bytes for a in result.apps if a.type == "dlc"),
            "other_bytes": sum(
                a.size_bytes for a in result.apps if a.type not in ("game", "dlc")
            ),
            "app_count": len(result.apps),
            "skipped_appids": result.skipped_appids,
        }
        apps = [
            {"appid": a.appid, "name": a.name, "type": a.type, "size_bytes": a.size_bytes}
            for a in result.apps
        ]
        print(json.dumps({"totals": totals, "apps": apps}, indent=2))
    elif args.csv:
        writer = csv.writer(sys.stdout)
        writer.writerow(["appid", "name", "type", "size_bytes"])
        for a in result.apps:
            writer.writerow([a.appid, a.name, a.type, a.size_bytes])
    else:
        print(render_report(result, args.top, args.include_dlc, args.include_all))
    return 0


if __name__ == "__main__":
    sys.exit(main())
