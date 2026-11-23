"""Unit tests for the plugin's pure logic (no QGIS needed)."""
import os
import sys
import datetime
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402


def test_parse_progress_matches_cli_format():
    assert core.parse_progress("[ 42%] epoch 2000 (3/9)") == (42, "epoch 2000 (3/9)")
    assert core.parse_progress("[100%] done") == (100, "done")
    assert core.parse_progress("[  0%] prepare") == (0, "prepare")


def test_parse_progress_non_progress_line():
    pct, text = core.parse_progress("Area: 12.3 km2, grid ...")
    assert pct is None and text.startswith("Area:")


def test_parse_progress_clamps():
    assert core.parse_progress("[250%] x")[0] == 100


def test_normalize_epochs_sorted_unique():
    assert core.normalize_epochs([2025, 1990, 2025, 2000]) == [1990, 2000, 2025]


def test_build_command_basic():
    cmd = core.build_command("python3", "/x/cli.py", "/t/aoi.gpkg", "/t/out",
                             [2025, 1990], mode="pretrained", threshold=0.65, max_cloud=70, lang="pl")
    assert cmd[0] == "python3" and cmd[1] == "/x/cli.py"
    assert "--file" in cmd and "/t/aoi.gpkg" in cmd
    assert "--out" in cmd and "/t/out" in cmd
    assert cmd[cmd.index("--mode") + 1] == "pretrained"
    # epochs are sorted and come after --epochs
    i = cmd.index("--epochs")
    assert cmd[i + 1:] == ["1990", "2025"]
    assert "--crs" not in cmd


def test_build_command_with_crs():
    cmd = core.build_command("py", "cli.py", "a.gpkg", "out", [2025], crs="EPSG:2180")
    assert cmd[cmd.index("--crs") + 1] == "EPSG:2180"


def test_build_command_rejects_bad_threshold():
    with pytest.raises(ValueError):
        core.build_command("py", "cli.py", "a.gpkg", "out", [2025], threshold=1.5)


def test_build_command_rejects_future_epoch():
    future = datetime.date.today().year + 1
    with pytest.raises(ValueError):
        core.build_command("py", "cli.py", "a.gpkg", "out", [future])


def test_build_command_rejects_pre_1985():
    with pytest.raises(ValueError):
        core.build_command("py", "cli.py", "a.gpkg", "out", [1975])


def test_build_command_requires_paths():
    with pytest.raises(ValueError):
        core.build_command("py", "cli.py", "", "out", [2025])


def test_validate_rejects_unknown_mode():
    with pytest.raises(ValueError):
        core.validate_params([2025], 0.65, 70, "magic")


def test_find_cli(tmp_path):
    assert core.find_cli([str(tmp_path)]) is None
    app = tmp_path / "aplikacja"
    app.mkdir()
    (app / "landcoverrewind_cli.py").write_text("# cli")
    assert core.find_cli([str(tmp_path)]) == str(app / "landcoverrewind_cli.py")


def test_result_layers(tmp_path):
    for name in ("built_up_1990.tif", "built_up_2025.tif", "land_cover_4class_2025.tif",
                 "first_detection_epoch.tif"):
        (tmp_path / name).write_bytes(b"II*\0")  # dummy
    layers = core.result_layers(str(tmp_path), [2025, 1990])
    kinds = [(l["kind"], l["year"]) for l in layers]
    assert ("built_up", 1990) in kinds and ("built_up", 2025) in kinds
    assert ("land_cover_4class", 2025) in kinds
    assert ("first_detection", None) in kinds
    # a missing file is not listed
    assert all(not (l["kind"] == "land_cover_4class" and l["year"] == 1990) for l in layers)


def test_colour_tables_cover_four_classes():
    vals = [v for v, _rgb, _lbl in core.LC4_CLASSES]
    assert vals == [1, 2, 3, 4]
    assert core.BUILTUP_CLASSES[0][0] == 1


def test_bbox_geojson_valid_polygon():
    import json as _json
    gj = core.bbox_geojson(18.5, 52.9, 18.7, 53.1)
    d = _json.loads(gj)
    assert d["type"] == "FeatureCollection"
    ring = d["features"][0]["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]            # closed ring
    assert len(ring) == 5
    assert d["features"][0]["geometry"]["type"] == "Polygon"


def test_bbox_geojson_rejects_empty_rectangle():
    with pytest.raises(ValueError):
        core.bbox_geojson(18.7, 53.1, 18.5, 52.9)


def test_dedupe_keeps_first_order_and_drops_empty():
    assert core.dedupe(["a", "", "b", "a", None, "c"]) == ["a", "b", "c"]


def test_project_and_requirements_paths():
    cli = os.path.join("x", "y", "landcoverrewind_cli.py")
    assert core.project_dir(cli).endswith(os.path.join("x", "y"))
    assert core.requirements_path(cli).endswith("requirements.txt")
    assert core.project_dir("") == ""
    assert core.requirements_path("") == ""
