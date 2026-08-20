import struct
from pathlib import Path

import pytest
import vdf

from steam_library_size.licenses import (
    MAGIC_V27,
    MAGIC_V28,
    UnsupportedFormatError,
    read_licenses,
    read_owned_appids,
)


def build_packageinfo(
    packages: dict[int, list[int]],
    magic: int = MAGIC_V28,
    depots: dict[int, list[int]] | None = None,
) -> bytes:
    out = bytearray(struct.pack("<II", magic, 1))
    for pkgid, appids in packages.items():
        out += struct.pack("<I", pkgid)
        out += b"\x00" * 20              # sha1
        out += struct.pack("<I", 7)      # change number
        if magic == MAGIC_V28:
            out += struct.pack("<Q", 0)  # PICS access token
        pkg: dict = {
            "packageid": pkgid,
            "appids": {str(i): appid for i, appid in enumerate(appids)},
        }
        if depots and pkgid in depots:
            pkg["depotids"] = {str(i): d for i, d in enumerate(depots[pkgid])}
        out += vdf.binary_dumps({str(pkgid): pkg})
    out += struct.pack("<I", 0xFFFFFFFF)
    return bytes(out)


def write_steam(tmp_path: Path, payload: bytes) -> Path:
    (tmp_path / "appcache").mkdir()
    (tmp_path / "appcache/packageinfo.vdf").write_bytes(payload)
    return tmp_path


def test_v28_collects_unique_appids(tmp_path):
    steam = write_steam(tmp_path, build_packageinfo({10: [220, 440], 20: [440, 730]}))
    assert read_owned_appids(steam) == {220, 440, 730}


def test_v27_no_token_field(tmp_path):
    steam = write_steam(tmp_path, build_packageinfo({10: [220]}, magic=MAGIC_V27))
    assert read_owned_appids(steam) == {220}


def test_package_without_appids_is_fine(tmp_path):
    steam = write_steam(tmp_path, build_packageinfo({10: []}))
    assert read_owned_appids(steam) == set()


def test_read_licenses_collects_appids_and_depotids(tmp_path):
    steam = write_steam(tmp_path, build_packageinfo(
        {10: [220, 440], 20: [730]},
        depots={10: [221, 441], 20: [731, 732]},
    ))
    appids, depotids = read_licenses(steam)
    assert appids == {220, 440, 730}
    assert depotids == {221, 441, 731, 732}


def test_read_licenses_package_without_depotids(tmp_path):
    steam = write_steam(tmp_path, build_packageinfo({10: [220]}))
    appids, depotids = read_licenses(steam)
    assert appids == {220}
    assert depotids == set()


def test_unknown_magic_raises(tmp_path):
    steam = write_steam(tmp_path, struct.pack("<II", 0x06565599, 1))
    with pytest.raises(UnsupportedFormatError) as exc:
        read_owned_appids(steam)
    assert "issue" in str(exc.value)
