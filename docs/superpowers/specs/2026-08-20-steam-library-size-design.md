# steam-library-size — Design Spec

**Date:** 2026-08-20
**Status:** Approved by Chris (sharpmonk)
**License:** MIT

## Problem

"How big would my whole Steam library be if I installed every game?" is a
commonly asked question with no good answer today: Steam only stores sizes
for installed games, SteamDB's calculator has no size feature (declined
issue #873), and steamcalculator.org's domain has expired. Web tools also
require a public profile, which many users don't have.

## Solution

A pipx-installable CLI, `steam-library-size`, that answers the question
entirely from the user's own machine plus one anonymous connection to
Steam's PICS service:

1. Locate the local Steam install.
2. Parse `appcache/packageinfo.vdf` to enumerate every app ID the account
   owns (this file is the client's cache of the account's licenses).
3. Anonymously log in to Steam (ValvePython `steam[client]`) and batch-fetch
   product info for those app IDs.
4. Sum depot sizes per app and print a report.

No Steam Web API key. No public profile. Works with fully private accounts.
Nothing about the user's account is transmitted anywhere — the PICS queries
are anonymous and only contain public app IDs.

## Distribution

- GitHub: `sharpmonk/steam-library-size`, MIT license.
- PyPI package `steam-library-size`, console script `steam-library-size`.
- Recommended install: `pipx install steam-library-size` (isolates the
  heavy `steam[client]` dependency tree: gevent, protobuf, etc.).
- Requires Python 3.10+.

## Package layout

```
steam-library-size/
├── pyproject.toml            # hatchling build backend; project metadata, deps: vdf, steam[client]
├── LICENSE                   # MIT, copyright sharpmonk
├── README.md
├── .github/workflows/
│   ├── ci.yml                # pytest on push/PR (linux; 3.10–3.13 matrix)
│   └── publish.yml           # PyPI trusted publishing on tagged release
├── src/steam_library_size/
│   ├── __init__.py           # __version__
│   ├── cli.py                # argparse entry point, report rendering
│   ├── steam_paths.py        # locate Steam root per-OS
│   ├── licenses.py           # packageinfo.vdf binary parser → owned app IDs
│   └── sizes.py              # anonymous PICS fetch + depot-size computation
└── tests/
    ├── test_licenses.py      # synthetic packageinfo.vdf fixtures (v27 + v28)
    ├── test_sizes.py         # canned PICS app dicts → size logic
    ├── test_steam_paths.py   # path discovery with tmp dirs / monkeypatched platform
    └── test_cli.py           # report formatting, --json/--csv output
```

## Module contracts

### steam_paths.py

`find_steam_dir(override: str | None) -> Path`

Search order (first hit with an `appcache/packageinfo.vdf` wins):
- explicit `--steam-dir` override (error if invalid — never fall through)
- Linux: `~/.local/share/Steam`, `~/.steam/steam`,
  `~/.var/app/com.valvesoftware.Steam/.local/share/Steam` (Flatpak),
  `~/snap/steam/common/.local/share/Steam` (Snap)
- Windows: `%ProgramFiles(x86)%\Steam`, `%ProgramFiles%\Steam`, plus
  registry key `HKCU\Software\Valve\Steam\SteamPath` when available
- macOS: `~/Library/Application Support/Steam`

Failure: raise `SteamNotFoundError` with the searched paths; CLI renders it
with a hint to pass `--steam-dir`.

### licenses.py

`read_owned_appids(steam_dir: Path) -> set[int]`

Binary parser for `appcache/packageinfo.vdf`:
- magic `0x06565528` (v28): per package — u32 id, 20B sha1, u32 change
  number, u64 PICS token, then one binary-VDF blob (parsed with `vdf`).
- magic `0x06565527` (v27): same minus the 8-byte token.
- terminator: package id `0xFFFFFFFF`.
- any other magic: raise `UnsupportedFormatError` telling the user to file
  a GitHub issue (loud failure beats silent wrong answers).

Collect `appids` from every package. Free-license package 0 ("Steam") is
included naturally; junk IDs are filtered later by app type.

### sizes.py

`fetch_app_sizes(appids, os_filter, progress_cb) -> dict[int, AppSize]`
where `AppSize = {name: str, type: str, size_bytes: int}`.

- `SteamClient().anonymous_login()`; on failure raise `SteamConnectError`.
- `get_product_info(apps=chunk)` in chunks of 50, 60 s timeout.
- Per-chunk failure: retry once, then warn via `progress_cb` and record the
  chunk's app IDs as skipped. The final report must state how many apps
  were skipped — never silently under-count.

Size of one app = sum over its depots of the `public` branch manifest
`size` (uncompressed install size), where a depot counts iff:
- it is a dict with a `manifests.public` entry (skips encrypted/unused)
- not `sharedinstall` (skips redistributables shared across games)
- `config.language` is unset or `english`
- OS rule: shared depots (no `oslist`) always count; OS-specific depots
  count for the selected `--os`. Default OS = the platform the tool runs
  on, except Linux defaults to **windows** sizes when the app has Windows
  depots (Proton reality) with Linux depots as fallback. `--os all` sums
  every OS variant (upper bound).

### cli.py

```
steam-library-size [--top N] [--json | --csv] [--include-dlc]
                   [--include-all] [--os {windows,linux,macos,all}]
                   [--steam-dir PATH] [--version]
```

- Default output (human): headline total for type `game`, counts, a
  breakdown line for DLC and other types, top-N table (default N=20),
  skipped-apps warning if any, and a closing "drive you'd need" line
  (total rounded up to common drive sizes: 1/2/4/8/16 TB).
- `--include-dlc` adds DLC sizes into the headline total;
  `--include-all` adds everything (tools, demos, soundtracks, servers).
- `--json` emits the full per-app list plus totals (machine-readable,
  stable keys); `--csv` emits one row per app. Both to stdout; progress
  goes to stderr so piping stays clean.
- Exit codes: 0 success, 1 Steam/parse errors, 2 connection errors.

## Report caveats (documented in README and printed as a footnote)

- Sizes are uncompressed depot sizes for the public branch — effectively
  "fresh install today". Games with optional depots (CoD modes, ARK maps,
  HD texture packs) count them all, so those over-report a typical install.
- Shader cache, saves, and workshop content are not included.
- Owned-but-delisted apps may return no size (counted and reported as
  "no size data", not dropped silently).

## Testing

- pytest, no network by default. Fixtures: hand-built packageinfo.vdf
  blobs (v27, v28, truncated/garbage), canned product-info dicts covering
  the depot rules (language, oslist, sharedinstall, missing manifests).
- One live smoke test (`-m network`) that anonymous-logins and fetches a
  known app (440) — run manually and in a scheduled CI job, not on PR.
- CI: GitHub Actions, ubuntu, Python 3.10–3.13.

## Publishing

- `publish.yml`: on tag `v*` → build sdist+wheel → PyPI via trusted
  publishing (no stored API token).
- v0.1.0 after end-to-end verification on monkDesktop (expected result
  ≈ 288 games / ~6.4 TB). Windows/macOS path logic is unit-tested but not
  live-verified — README notes this and invites issues.

## Out of scope (v1)

- Steam Web API / remote mode for machines without Steam installed.
- GUI, install-size-vs-download-size distinction, per-drive planning,
  non-English depot language selection.
