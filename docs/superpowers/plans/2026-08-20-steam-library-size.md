# steam-library-size Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A pipx-installable CLI that reports how big a user's entire Steam library would be if every owned game were installed, computed locally with no API key or public profile.

**Architecture:** Three focused modules behind a thin argparse CLI: `steam_paths` locates the Steam install per-OS, `licenses` binary-parses `appcache/packageinfo.vdf` into owned app IDs, `sizes` fetches product info via an anonymous Steam PICS connection and sums depot sizes. `cli` wires them together and renders human/JSON/CSV reports.

**Tech Stack:** Python 3.10+, `vdf`, `steam[client]` (ValvePython), pytest, hatchling, GitHub Actions, PyPI trusted publishing.

**Spec:** `docs/superpowers/specs/2026-08-20-steam-library-size-design.md`

## Global Constraints

- Package/repo/command name: `steam-library-size`; import package `steam_library_size`; repo `sharpmonk/steam-library-size`.
- License: MIT, copyright "sharpmonk".
- `requires-python = ">=3.10"`; runtime deps exactly `vdf>=3.4` and `steam[client]>=1.4`.
- Tests never touch the network unless marked `@pytest.mark.network`; default pytest run excludes that marker.
- Errors are loud: unknown file formats raise, skipped apps are counted and reported, never silently dropped.
- Exit codes: 0 success, 1 Steam-install/parse errors, 2 Steam connection errors.
- Progress/warnings go to stderr; report/JSON/CSV go to stdout.
- All work happens in `/home/sharpmonk/Projects/steam-library-size`; commit after every task.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `LICENSE`, `.gitignore`, `src/steam_library_size/__init__.py`, `tests/test_package.py`

**Interfaces:**
- Produces: importable package `steam_library_size` with `__version__ = "0.1.0"`; editable install with `dev` extra providing pytest; pytest configured so `-m network` tests are excluded by default.

- [ ] **Step 1: Write files**

`pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "steam-library-size"
version = "0.1.0"
description = "How big would your Steam library be if you installed every game? Computed locally - no API key, no public profile needed."
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
requires-python = ">=3.10"
authors = [{ name = "sharpmonk" }]
keywords = ["steam", "library", "disk-space", "games"]
classifiers = [
    "Environment :: Console",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Topic :: Games/Entertainment",
]
dependencies = ["vdf>=3.4", "steam[client]>=1.4"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.urls]
Homepage = "https://github.com/sharpmonk/steam-library-size"
Issues = "https://github.com/sharpmonk/steam-library-size/issues"

[project.scripts]
steam-library-size = "steam_library_size.cli:main"

[tool.pytest.ini_options]
addopts = "-m 'not network'"
markers = ["network: tests that talk to real Steam servers (run with -m network)"]
```

`LICENSE`: standard MIT text, `Copyright (c) 2026 sharpmonk`.

`.gitignore`:

```
__pycache__/
*.egg-info/
dist/
.venv/
.pytest_cache/
```

`src/steam_library_size/__init__.py`:

```python
__version__ = "0.1.0"
```

`tests/test_package.py`:

```python
import steam_library_size


def test_version():
    assert steam_library_size.__version__ == "0.1.0"
```

- [ ] **Step 2: Create venv and install editable**

Run: `cd ~/Projects/steam-library-size && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
Expected: installs without error (pulls vdf, steam[client], pytest). Note: the console script will fail until Task 6 creates `cli.py` — that is fine; do not import it yet.

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: project scaffolding (pyproject, MIT license, package skeleton)"
```

---

### Task 2: steam_paths — locate the Steam install

**Files:**
- Create: `src/steam_library_size/steam_paths.py`
- Test: `tests/test_steam_paths.py`

**Interfaces:**
- Produces: `find_steam_dir(override: str | None = None) -> Path` returning a Steam root that contains `appcache/packageinfo.vdf`; `SteamNotFoundError(Exception)` with attribute `searched: list[Path]`; module constant `PACKAGEINFO = Path("appcache") / "packageinfo.vdf"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_steam_paths.py`:

```python
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
```

Note: `monkeypatch.setattr("sys.platform", ...)` patches the attribute on the `sys` module — `steam_paths` must read `sys.platform` at call time (inside `_candidates()`), not at import time.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_steam_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: steam_library_size.steam_paths`.

- [ ] **Step 3: Implement**

`src/steam_library_size/steam_paths.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_steam_paths.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: locate Steam install across Linux/Flatpak/Snap/Windows/macOS"
```

---

### Task 3: licenses — parse packageinfo.vdf into owned app IDs

**Files:**
- Create: `src/steam_library_size/licenses.py`
- Test: `tests/test_licenses.py`

**Interfaces:**
- Consumes: a Steam root `Path` from `find_steam_dir` (Task 2).
- Produces: `read_owned_appids(steam_dir: Path) -> set[int]`; `UnsupportedFormatError(Exception)`; constants `MAGIC_V27 = 0x06565527`, `MAGIC_V28 = 0x06565528`.

- [ ] **Step 1: Write the failing tests**

`tests/test_licenses.py`:

```python
import struct
from pathlib import Path

import pytest
import vdf

from steam_library_size.licenses import (
    MAGIC_V27,
    MAGIC_V28,
    UnsupportedFormatError,
    read_owned_appids,
)


def build_packageinfo(packages: dict[int, list[int]], magic: int = MAGIC_V28) -> bytes:
    out = bytearray(struct.pack("<II", magic, 1))
    for pkgid, appids in packages.items():
        out += struct.pack("<I", pkgid)
        out += b"\x00" * 20              # sha1
        out += struct.pack("<I", 7)      # change number
        if magic == MAGIC_V28:
            out += struct.pack("<Q", 0)  # PICS access token
        blob = {
            str(pkgid): {
                "packageid": pkgid,
                "appids": {str(i): appid for i, appid in enumerate(appids)},
            }
        }
        out += vdf.binary_dumps(blob)
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


def test_unknown_magic_raises(tmp_path):
    steam = write_steam(tmp_path, struct.pack("<II", 0x06565599, 1))
    with pytest.raises(UnsupportedFormatError) as exc:
        read_owned_appids(steam)
    assert "issue" in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_licenses.py -v`
Expected: FAIL — `ModuleNotFoundError: steam_library_size.licenses`.

- [ ] **Step 3: Implement**

`src/steam_library_size/licenses.py`:

```python
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


def read_owned_appids(steam_dir: Path) -> set[int]:
    """Return every app ID granted by the account's cached licenses."""
    path = steam_dir / "appcache" / "packageinfo.vdf"
    appids: set[int] = set()
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
    return appids
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_licenses.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: parse packageinfo.vdf (v27/v28) into owned app IDs"
```

---

### Task 4: sizes — depot-size computation (pure logic)

**Files:**
- Create: `src/steam_library_size/sizes.py`
- Test: `tests/test_sizes.py`

**Interfaces:**
- Produces: `compute_app_size(app: dict, os_choice: str) -> int` where `os_choice ∈ {"windows", "linux", "macos", "all"}`; dataclass `AppSize(appid: int, name: str, type: str, size_bytes: int)`; dataclass `FetchResult(apps: list[AppSize], skipped_appids: list[int])` (both fields default to empty lists). Task 5 adds `fetch_app_sizes` and `SteamConnectError` to this same module.

- [ ] **Step 1: Write the failing tests**

`tests/test_sizes.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_sizes.py -v`
Expected: FAIL — `ModuleNotFoundError: steam_library_size.sizes`.

- [ ] **Step 3: Implement**

`src/steam_library_size/sizes.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_sizes.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: depot-size computation with OS/language/sharedinstall rules"
```

---

### Task 5: sizes — anonymous PICS fetch

**Files:**
- Modify: `src/steam_library_size/sizes.py` (append)
- Test: `tests/test_sizes.py` (append)

**Interfaces:**
- Consumes: `compute_app_size`, `AppSize`, `FetchResult` (Task 4).
- Produces: `fetch_app_sizes(appids: Iterable[int], os_choice: str, progress_cb: Callable[[str], None] = ...) -> FetchResult`; `SteamConnectError(Exception)`; module constant `CHUNK_SIZE = 50`. `SteamClient` is imported lazily *inside* `fetch_app_sizes` (module attribute lookup at call time) so tests can `monkeypatch.setattr("steam.client.SteamClient", ...)` and importing `sizes` stays cheap.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sizes.py`:

```python
import pytest

from steam_library_size.sizes import CHUNK_SIZE, SteamConnectError, fetch_app_sizes


class FakeClient:
    """Serves 3 apps; one chunk-sized hole tests skip accounting."""

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_sizes.py -v`
Expected: new tests FAIL with `ImportError: cannot import name 'fetch_app_sizes'`; Task 4 tests still pass.

- [ ] **Step 3: Implement**

Append to `src/steam_library_size/sizes.py` (and extend the imports at top to `from typing import Callable, Iterable`):

```python
CHUNK_SIZE = 50


class SteamConnectError(Exception):
    pass


def fetch_app_sizes(
    appids: Iterable[int],
    os_choice: str,
    progress_cb: Callable[[str], None] = lambda msg: None,
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
                        size_bytes=compute_app_size(app, os_choice),
                    )
                )
            progress_cb(f"fetched {min(start + CHUNK_SIZE, len(ids))}/{len(ids)} apps")
    finally:
        client.logout()
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_sizes.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: anonymous PICS fetch with chunking, retry, and skip accounting"
```

---

### Task 6: cli — argument parsing, report rendering, wiring

**Files:**
- Create: `src/steam_library_size/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `find_steam_dir`/`SteamNotFoundError` (Task 2), `read_owned_appids`/`UnsupportedFormatError` (Task 3), `fetch_app_sizes`/`FetchResult`/`AppSize`/`SteamConnectError` (Tasks 4–5).
- Produces: `main(argv: list[str] | None = None) -> int` (console-script entry point); `build_parser() -> argparse.ArgumentParser`; `render_report(result: FetchResult, top: int, include_dlc: bool, include_all: bool) -> str`; `default_os() -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:

```python
import json

import pytest

from steam_library_size.cli import build_parser, main, render_report
from steam_library_size.sizes import AppSize, FetchResult

GB = 1024**3


def sample_result():
    return FetchResult(
        apps=[
            AppSize(1, "Big Game", "game", 500 * GB),
            AppSize(2, "Small Game", "game", 10 * GB),
            AppSize(3, "Zero Game", "game", 0),
            AppSize(4, "Some DLC", "dlc", 8 * GB),
            AppSize(5, "A Tool", "tool", 3 * GB),
        ],
        skipped_appids=[99],
    )


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.top == 20 and not args.json and not args.csv
    assert args.os is None and args.steam_dir is None


def test_json_csv_mutually_exclusive():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--json", "--csv"])


def test_render_report_headline_and_sections():
    text = render_report(sample_result(), top=20, include_dlc=False, include_all=False)
    assert "3 games" in text
    assert "510.0 GB" in text           # games only
    assert "Big Game" in text and "Some DLC" not in text  # top table = games
    assert "1 app with no size data" in text   # Zero Game
    assert "1 app could not be fetched" in text  # skipped 99
    assert "1 TB" in text               # drive suggestion: 510 GB -> 1 TB


def test_render_report_include_all_changes_total():
    text = render_report(sample_result(), top=5, include_dlc=True, include_all=True)
    assert "521.0 GB" in text


def test_main_json_output(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("steam_library_size.cli.find_steam_dir", lambda override: tmp_path)
    monkeypatch.setattr("steam_library_size.cli.read_owned_appids", lambda d: {1, 2})
    monkeypatch.setattr(
        "steam_library_size.cli.fetch_app_sizes",
        lambda appids, os_choice, progress_cb: sample_result(),
    )
    assert main(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["totals"]["game_bytes"] == 510 * GB
    assert data["totals"]["skipped_appids"] == [99]
    assert len(data["apps"]) == 5


def test_main_steam_not_found_exit_1(monkeypatch, capsys):
    from steam_library_size.steam_paths import SteamNotFoundError

    def boom(override):
        raise SteamNotFoundError([])

    monkeypatch.setattr("steam_library_size.cli.find_steam_dir", boom)
    assert main([]) == 1
    assert "Steam" in capsys.readouterr().err


def test_main_connect_error_exit_2(monkeypatch, capsys, tmp_path):
    from steam_library_size.sizes import SteamConnectError

    monkeypatch.setattr("steam_library_size.cli.find_steam_dir", lambda override: tmp_path)
    monkeypatch.setattr("steam_library_size.cli.read_owned_appids", lambda d: {1})
    def boom(appids, os_choice, progress_cb):
        raise SteamConnectError("no net")

    monkeypatch.setattr("steam_library_size.cli.fetch_app_sizes", boom)
    assert main([]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: steam_library_size.cli`.

- [ ] **Step 3: Implement**

`src/steam_library_size/cli.py`:

```python
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
```

Progress always goes to stderr, so it never corrupts stdout JSON/CSV.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -v`
Expected: all tests pass (package, paths, licenses, sizes, cli).

- [ ] **Step 5: Smoke the console script**

Run: `.venv/bin/steam-library-size --version && .venv/bin/steam-library-size --help`
Expected: version string, then help text listing all flags.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: CLI with human report, --json/--csv, exit codes"
```

---

### Task 7: README

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: final CLI flags from Task 6 (documentation must match `--help` exactly).

- [ ] **Step 1: Write README.md**

Sections, in order:
1. **Title + one-liner:** "How big would your Steam library be if you installed *every* game you own?"
2. **Why:** Steam only knows sizes of installed games; SteamDB's calculator has no size feature; old web calculators are dead and needed a public profile. This tool works offline from your own Steam client's license cache plus one **anonymous** connection to Steam — works with fully private profiles.
3. **Install:** `pipx install steam-library-size` (recommended), or `pip install steam-library-size`.
4. **Usage:** bare command, then flag table for `--top`, `--json`, `--csv`, `--include-dlc`, `--include-all`, `--os`, `--steam-dir`. Include a realistic sample output block (use the real monkDesktop numbers from Task 9 once known; placeholder numbers until then are fine in this step, updated in Task 9).
5. **How it works:** the packageinfo.vdf → anonymous PICS → depot-sum pipeline in one short paragraph.
6. **Accuracy caveats:** copy the three caveat bullets from the spec ("Report caveats").
7. **Privacy:** nothing about your account leaves your machine; the only network traffic is an anonymous Steam login querying public app metadata.
8. **Platform support:** Linux (incl. Flatpak/Snap) verified; Windows/macOS path detection implemented and unit-tested but not live-verified — issues welcome.
9. **License:** MIT.

- [ ] **Step 2: Verify pyproject readme reference resolves**

Run: `.venv/bin/pip install -e . --quiet && .venv/bin/python -c "from importlib.metadata import metadata; print(metadata('steam-library-size')['Summary'])"`
Expected: prints the description; no readme-missing build error.

- [ ] **Step 3: Commit**

```bash
git add README.md && git commit -m "docs: README with install, usage, how-it-works, caveats"
```

---

### Task 8: CI, publish workflow, network smoke test

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, `tests/test_network_smoke.py`

**Interfaces:**
- Consumes: `fetch_app_sizes` (Task 5).
- Produces: green CI on push/PR; PyPI publish on `v*` tags via trusted publishing.

- [ ] **Step 1: Write the network smoke test**

`tests/test_network_smoke.py`:

```python
import pytest

from steam_library_size.sizes import fetch_app_sizes


@pytest.mark.network
def test_live_fetch_team_fortress_2():
    result = fetch_app_sizes([440], "windows")
    assert result.skipped_appids == []
    (app,) = result.apps
    assert app.name == "Team Fortress 2"
    assert app.type == "game"
    assert app.size_bytes > 5 * 1024**3  # TF2 is well over 5 GB
```

- [ ] **Step 2: Verify marker exclusion and live run**

Run: `.venv/bin/pytest tests/test_network_smoke.py -v` → Expected: 1 deselected, 0 run.
Run: `.venv/bin/pytest tests/test_network_smoke.py -v -m network` → Expected: 1 passed (needs internet).

- [ ] **Step 3: Write the workflows**

`.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push:
    branches: [master]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e '.[dev]'
      - run: pytest -v
  network-smoke:
    if: github.event_name == 'schedule'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e '.[dev]'
      - run: pytest -v -m network
```

Also add to the `on:` block of ci.yml:

```yaml
  schedule:
    - cron: "0 6 * * 1"   # weekly live smoke test against real Steam
```

`.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI
on:
  push:
    tags: ["v*"]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build && python -m build
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
  publish:
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 4: Sanity-check the build locally**

Run: `.venv/bin/pip install build --quiet && .venv/bin/python -m build && ls dist/`
Expected: `steam_library_size-0.1.0.tar.gz` and `steam_library_size-0.1.0-py3-none-any.whl`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "ci: test matrix, PyPI trusted publishing, live smoke test"
```

---

### Task 9: End-to-end verification on this machine

**Files:**
- Modify: `README.md` (real sample output)

**Interfaces:**
- Consumes: the finished CLI.

- [ ] **Step 1: Run for real**

Run: `.venv/bin/steam-library-size --top 10`
Expected: finds `/home/sharpmonk/.local/share/Steam`, reports ~901 apps from licenses, headline ≈ **288 games / ~6,400 GB** (within a few percent of the 2026-08-20 session measurement — sizes drift as games update). Top of the table should show Call of Duty (~570 GB) and ARK (~500 GB).

- [ ] **Step 2: Exercise the variants**

Run: `.venv/bin/steam-library-size --json | .venv/bin/python -m json.tool > /dev/null && .venv/bin/steam-library-size --csv | head -3 && .venv/bin/steam-library-size --include-all --top 3`
Expected: valid JSON; CSV header + rows; `--include-all` headline ≈ 7 TB.

- [ ] **Step 3: Paste real sample output into README**

Replace the placeholder sample block in README.md with genuine (trimmed to top-5) output from Step 1.

- [ ] **Step 4: Full test suite one last time**

Run: `.venv/bin/pytest -v`
Expected: all pass, network test deselected.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "docs: real sample output from end-to-end run"
```

---

## After the plan

Publishing to GitHub/PyPI (repo creation, PyPI trusted-publisher setup, `v0.1.0` tag) happens after Chris reviews the finished tool — it is deliberately not a task in this plan.
