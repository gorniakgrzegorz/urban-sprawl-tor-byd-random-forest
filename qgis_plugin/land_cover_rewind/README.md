# Land Cover Rewind — QGIS plugin

Reconstruct built-up land and four-class land cover for 1985–2025 over any area,
straight from QGIS. The plugin drives the open-source
[Land Cover Rewind](https://github.com/gorniakgrzegorz/urban-sprawl-tor-byd-random-forest)
workflow: a Random Forest classifier trained on present-day 10 m land cover labels
classifies Landsat composites read anonymously from the Microsoft Planetary Computer,
with an extent mask and monotonic accumulation producing a consistent 30 m series.

The heavy processing runs in the project's command-line tool (`landcoverrewind_cli.py`)
in a Python interpreter you choose, so QGIS does not need the scientific stack itself.
The plugin prepares the area, runs the tool in the background with a progress bar, and
loads the resulting GeoTIFFs into QGIS already styled.

## Requirements

- QGIS 3.22 or newer.
- A Python interpreter with the `landcoverrewind` dependencies installed. From the
  project's `aplikacja/` folder:
  ```bash
  python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
  pip install -r requirements.txt
  ```
- The path to `landcoverrewind_cli.py` (the `aplikacja/` folder of the repository).

You can point the plugin at the QGIS Python itself only if the dependencies are
installed there; a separate virtual environment is usually cleaner.

## Install the plugin

- Zip the `land_cover_rewind` folder and use *Plugins → Manage and Install Plugins →
  Install from ZIP*, or
- copy the `land_cover_rewind` folder into your QGIS plugins directory
  (`…/QGIS3/profiles/default/python/plugins/`) and enable *Land Cover Rewind* in the
  plugin manager.

## Use

1. Open *Raster → Land Cover Rewind*, or click the toolbar icon.
2. Choose a polygon layer (optionally "selected features only") or an area file
   (GPKG/GeoJSON/SHP). Keep the area small at first — a few km² and a few epochs run
   in about a minute; memory grows with area × epochs.
3. Pick epochs, mode (pretrained or local), the built-up threshold and the maximum
   scene cloud cover.
4. Set the Python interpreter and the path to `landcoverrewind_cli.py` (remembered
   between sessions).
5. Click **Run**. On success the built-up series, four-class maps and the
   first-detection map are added to the project, styled; the full output (GeoTIFFs,
   charts, animations, `metadata.json`, `results.zip`) is written to the output folder.

## Notes

- All imagery is read anonymously from the Microsoft Planetary Computer STAC; no Google
  account is needed.
- Results are approximations of historical built-up land; see the project website and
  manuscripts for accuracy and limitations.

## Licence

MIT, see `LICENSE`. © Grzegorz Górniak, Mieczysław Kunz, Nicolaus Copernicus University
in Toruń.
