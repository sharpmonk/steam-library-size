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
