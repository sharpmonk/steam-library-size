from __future__ import annotations

import argparse
import csv
import json
import sys

from . import __version__
from .licenses import UnsupportedFormatError, read_owned_appids
from .sizes import FetchResult, SteamConnectError, fetch_app_sizes
from .steam_paths import SteamNotFoundError, find_steam_dir

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
            return f"A {tb} TB drive would hold the lot."
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
        appids = read_owned_appids(steam_dir)
        print(f"Licenses grant {len(appids)} apps; fetching sizes...", file=sys.stderr)
        result = fetch_app_sizes(appids, args.os or default_os(), progress_cb=progress)
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
