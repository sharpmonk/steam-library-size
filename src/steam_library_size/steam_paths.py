from __future__ import annotations

import os
import sys
from pathlib import Path

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
