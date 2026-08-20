from __future__ import annotations

import struct
from pathlib import Path

import vdf

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
