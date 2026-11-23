"""Pure logic of the Land Cover Rewind QGIS plugin, with no QGIS or Qt imports.

Everything here is standard-library only so it can be unit-tested outside QGIS.
The plugin runs the project's command-line tool (``landcoverrewind_cli.py``) in a
separate process and loads the GeoTIFF results it writes; this module builds that
command, validates the parameters, parses progress and describes the output
layers and their colours.
"""
from __future__ import annotations

import datetime
import os
import re

EPOCHS = [1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]
MODES = ("pretrained", "local")

# progress lines printed by the CLI look like "[ 42%] epoch 2000 (3/9)"
_PROGRESS_RE = re.compile(r"\[\s*(\d{1,3})\s*%\]\s*(.*)")

# colours of the result maps (RGB), matching the project figures
BUILTUP_CLASSES = [(1, (179, 38, 30), "Built-up / Zabudowa")]
LC4_CLASSES = [
    (1, (179, 38, 30), "Built-up / Zabudowa"),
    (2, (77, 175, 74), "Trees and forest / Lasy i drzewa"),
    (3, (49, 130, 189), "Water / Woda"),
    (4, (255, 232, 166), "Other / Pozostałe"),
]


def parse_progress(line):
    """Return (percent:int, text:str) for a CLI progress line, else (None, stripped line)."""
    m = _PROGRESS_RE.search(line or "")
    if not m:
        return None, (line or "").strip()
    pct = max(0, min(100, int(m.group(1))))
    return pct, m.group(2).strip()


def validate_params(epochs, threshold, max_cloud, mode):
    """Raise ValueError if any parameter is outside the range the CLI accepts."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    if not epochs:
        raise ValueError("choose at least one epoch")
    year_now = datetime.date.today().year
    bad = [e for e in epochs if e < 1985 or e > year_now]
    if bad:
        raise ValueError(f"epochs {bad} are outside 1985-{year_now} "
                         "(Landsat MSS years 1975 and 1980 are not supported here)")
    if not 0 < float(threshold) < 1:
        raise ValueError("threshold must lie between 0 and 1")
    if not 0 < int(max_cloud) <= 100:
        raise ValueError("maximum cloud cover must lie between 1 and 100")


def normalize_epochs(epochs):
    """Sorted unique list of integer epochs."""
    return sorted({int(e) for e in epochs})


def build_command(interpreter, cli_path, aoi_path, out_dir, epochs,
                  mode="pretrained", threshold=0.65, max_cloud=70, crs=None, lang="pl"):
    """Build the argument list for ``landcoverrewind_cli.py``.

    interpreter: Python executable; cli_path: path to landcoverrewind_cli.py;
    aoi_path: GPKG/GeoJSON/SHP with the area; out_dir: output folder.
    Returns a list suitable for subprocess (no shell).
    """
    epochs = normalize_epochs(epochs)
    validate_params(epochs, threshold, max_cloud, mode)
    for label, value in (("interpreter", interpreter), ("cli_path", cli_path),
                         ("aoi_path", aoi_path), ("out_dir", out_dir)):
        if not value:
            raise ValueError(f"{label} is required")
    cmd = [str(interpreter), str(cli_path),
           "--file", str(aoi_path),
           "--out", str(out_dir),
           "--mode", str(mode),
           "--threshold", str(float(threshold)),
           "--max-cloud", str(int(max_cloud)),
           "--lang", str(lang),
           "--epochs", *[str(e) for e in epochs]]
    if crs:
        cmd += ["--crs", str(crs)]
    return cmd


def find_cli(search_dirs):
    """Return the first existing landcoverrewind_cli.py under the given directories, else None.

    Looks in each directory itself and in an ``aplikacja`` subfolder (the repo layout).
    """
    for d in search_dirs:
        if not d:
            continue
        for cand in (os.path.join(d, "landcoverrewind_cli.py"),
                     os.path.join(d, "aplikacja", "landcoverrewind_cli.py")):
            if os.path.isfile(cand):
                return cand
    return None


def result_layers(out_dir, epochs):
    """Describe the GeoTIFFs a finished run writes, those that exist on disk.

    Returns a list of dicts: {path, kind, year, title}. kind is one of
    'built_up', 'land_cover_4class', 'first_detection'.
    """
    epochs = normalize_epochs(epochs)
    out = []
    for y in epochs:
        p = os.path.join(out_dir, f"built_up_{y}.tif")
        if os.path.isfile(p):
            out.append(dict(path=p, kind="built_up", year=y, title=f"Built-up {y}"))
    for y in epochs:
        p = os.path.join(out_dir, f"land_cover_4class_{y}.tif")
        if os.path.isfile(p):
            out.append(dict(path=p, kind="land_cover_4class", year=y, title=f"Land cover {y}"))
    fd = os.path.join(out_dir, "first_detection_epoch.tif")
    if os.path.isfile(fd):
        out.append(dict(path=fd, kind="first_detection", year=None, title="First detection epoch"))
    return out
