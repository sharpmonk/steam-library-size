from pathlib import Path

import pytest

from steam_library_size.steam_paths import PACKAGEINFO, SteamNotFoundError, find_steam_dir


def make_steam(root: Path) -> Path:
    (root / "appcache").mkdir(parents=True)
    (root / PACKAGEINFO).write_bytes(b"stub")
    return root


def test_override_valid(tmp_path):
    steam = make_steam(tmp_path / "MySteam")
    assert find_steam_dir(str(steam)) == steam


def test_override_invalid_raises_and_does_not_fall_through(tmp_path, monkeypatch):
    # a valid default install exists, but a bad override must still raise
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    make_steam(tmp_path / ".local/share/Steam")
    with pytest.raises(SteamNotFoundError) as exc:
        find_steam_dir(str(tmp_path / "nope"))
    assert exc.value.searched == [tmp_path / "nope"]


def test_finds_linux_default(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    steam = make_steam(tmp_path / ".local/share/Steam")
    assert find_steam_dir() == steam


def test_finds_flatpak(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    steam = make_steam(tmp_path / ".var/app/com.valvesoftware.Steam/.local/share/Steam")
    assert find_steam_dir() == steam


def test_not_found_lists_searched_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    with pytest.raises(SteamNotFoundError) as exc:
        find_steam_dir()
    assert len(exc.value.searched) == 4
    assert "--steam-dir" in str(exc.value)
