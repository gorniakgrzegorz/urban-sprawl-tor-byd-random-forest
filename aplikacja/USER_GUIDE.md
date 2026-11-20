# User guide and tutorial

This guide walks through one complete run on the example area shipped with the package (central Toruń, about 9 km²) and explains how to read and check the results. The same steps work for any other area.

## 1. Start

- Browser app: double-click `run_windows.bat` (Windows) or run `streamlit run app.py`. Choose the interface language at the top of the side panel.
- Command line: `python landcoverrewind_cli.py --file examples/torun_centre.geojson --epochs 1990 2005 2025 --out results_example`.

## 2. Choose the area

Draw a rectangle or polygon on the map, or load a GeoPackage, GeoJSON or zipped Shapefile. For a first test keep the area below 50 km² and select two or three epochs; a full run for a city of about 150 km² with nine epochs takes from several to over a dozen minutes, depending on the connection and the number of scenes.

## 3. Choose the settings

| Setting | Default | When to change |
|---|---|---|
| Epochs | 1985–2025 every 5 years | fewer epochs for a quick look; growth forms need at least two |
| Mode | `pretrained` | `local` outside Poland or in landscapes unlike central Poland |
| Threshold | 0.65 | only for sensitivity checks; higher values map less built-up land |
| Cloud limit | 70% | raise it when an epoch is reported as skipped |

## 4. Run and follow the progress

The progress bar shows the current step: grid preparation, (local mode) training, one step per epoch (scene search, cloud masking, compositing, classification), the series constraints, tables and figures. Features of each epoch are cached in `<results>/cache`, so a second run on the same area with another threshold takes seconds.

## 5. Read the results

1. `built_up_animation.gif` and `first_detection_map.png` show where and when built-up land appears.
2. `epoch_metrics.csv` gives the built-up area and landscape metrics per epoch; `growth_forms.csv` splits the new built-up land of each period into infill, edge expansion and leapfrog.
3. `built_up_probability_<epoch>.tif` keeps the raw classifier output, which allows other thresholds or rules to be tested in QGIS or Python.

## 5a. Optional: SDG indicator 11.3.1

Open the panel "SDG indicator 11.3.1" below the results. Load one population file with two columns or two files (one per date); choose the identifier column that joins the two files (for the census grids of Statistics Poland: `code`), the population columns (`tot`) and the two dates (e.g. 2011 and 2021). Click "Compute SDG indicator 11.3.1". The app shows the whole-area values (population, built-up area, built-up land per capita, LCR, PGR, LCRPGR), a map of cell classes and a phase diagram; the cell layer and tables are added to the ZIP archive.

## 6. Check the results

- Compare one or two epochs with orthophotos or historical topographic maps of the area.
- Treat the earliest epoch (1985) with caution: it typically misses part of the existing built-up land, so growth rates are reported from 1990.
- The series cannot show demolition, and built-up land absent from the present-day extent mask cannot appear in any epoch.
- For another check, run the same area in both modes; large differences indicate that the pretrained model does not transfer well to the area.

## 7. Reproduce a run

`metadata.json` lists the software version, all settings and the identifiers of every Landsat scene used. Running the same version with the same settings on the same scenes gives the same maps. The 2025 epoch uses scenes from 2024–2026, so its result can change while new 2026 scenes are added to the archive.

## 8. Use the Python API

```python
from odc.geo.geom import box
from landcoverrewind import pipeline, series
r = pipeline.run(box(18.60, 53.00, 18.645, 53.027, "EPSG:4326"), epochs=[1990, 2005, 2025], out_dir="results_api")
B2 = series.monotonic_series(r["P"], 0.55, r["M"])     # the same series with another threshold, no new download
print([round(B2[t][r["area"]].sum() * 0.09) for t in sorted(B2)])   # built-up area [ha]
```

SDG indicator 11.3.1 for the same run:

```python
cells, summary = pipeline.run_sdg(r, ["nsp2011.gpkg", "nsp2021.gpkg"], ["tot", "tot"], (2011, 2021), id_field="code")
print(summary["lcrpgr"], summary["status"])
```
