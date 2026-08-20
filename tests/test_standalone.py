"""The standalone script must stay behaviorally in sync with the package."""

import importlib.util
import inspect
import struct
from pathlib import Path

import pytest

STANDALONE = Path(__file__).parent.parent / "standalone" / "steam_library_size.py"


@pytest.fixture(scope="module")
def standalone():
    import sys

    spec = importlib.util.spec_from_file_location("standalone_sls", STANDALONE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["standalone_sls"] = mod  # dataclasses resolve annotations via sys.modules
    try:
        spec.loader.exec_module(mod)
        yield mod
    finally:
        sys.modules.pop("standalone_sls", None)


def test_version_matches_package(standalone):
    import steam_library_size

    assert standalone.__version__ == steam_library_size.__version__


def test_core_functions_are_identical_to_package(standalone):
    """Source-level sync check: the shared logic must not drift."""
    from steam_library_size import cli, licenses, sizes, steam_paths

    pairs = [
        (steam_paths.find_steam_dir, standalone.find_steam_dir),
        (steam_paths._candidates, standalone._candidates),
        (licenses.read_licenses, standalone.read_licenses),
        (licenses.read_owned_appids, standalone.read_owned_appids),
        (sizes.compute_app_size, standalone.compute_app_size),
        (sizes.fetch_app_sizes, standalone.fetch_app_sizes),
        (cli.build_parser, standalone.build_parser),
        (cli.render_report, standalone.render_report),
        (cli._drive_line, standalone._drive_line),
        (cli.main, standalone.main),
    ]
    for pkg_fn, alone_fn in pairs:
        assert inspect.getsource(pkg_fn) == inspect.getsource(alone_fn), (
            f"{pkg_fn.__name__} differs between package and standalone script"
        )


def test_standalone_parses_packageinfo(standalone, tmp_path):
    import vdf

    out = bytearray(struct.pack("<II", standalone.MAGIC_V28, 1))
    out += struct.pack("<I", 10) + b"\x00" * 20 + struct.pack("<I", 7) + struct.pack("<Q", 0)
    out += vdf.binary_dumps({"10": {"appids": {"0": 440}}})
    out += struct.pack("<I", 0xFFFFFFFF)
    (tmp_path / "appcache").mkdir()
    (tmp_path / "appcache/packageinfo.vdf").write_bytes(bytes(out))

    assert standalone.read_owned_appids(tmp_path) == {440}


def test_standalone_computes_sizes(standalone):
    app = {
        "depots": {
            "0": {"config": {}, "manifests": {"public": {"size": "100"}}},
            "1": {"config": {"oslist": "windows"}, "manifests": {"public": {"size": "50"}}},
        }
    }
    assert standalone.compute_app_size(app, "windows") == 150
