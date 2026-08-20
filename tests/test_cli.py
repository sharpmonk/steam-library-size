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
