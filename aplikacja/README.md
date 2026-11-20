# Land Cover Rewind 1985–2025

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24332551.svg)](https://doi.org/10.5281/zenodo.24332551)
[![tests](https://github.com/gorniakgrzegorz/urban-sprawl-tor-byd-random-forest/actions/workflows/tests.yml/badge.svg)](https://github.com/gorniakgrzegorz/urban-sprawl-tor-byd-random-forest/actions/workflows/tests.yml)

Land Cover Rewind reconstructs built-up land and four-class land cover for the epochs 1985, 1990, … 2025 for any area on Earth covered by the Landsat archive. A Random Forest classifier trained on a present-day 10 m land cover map labels annual Landsat composites of earlier years; an extent mask and a monotonic accumulation rule turn the per-epoch probabilities into a consistent series. The package also reports landscape metrics and growth forms (infill, edge expansion, leapfrog) for every period.

No Google account or any other account is needed. Landsat Collection 2 Level 2 scenes and the Impact Observatory/Esri annual 10 m land use/land cover maps are read anonymously from the [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com) STAC catalogue, and all computation runs on the user's computer.

A Polish version of this document is in [README_PL.md](README_PL.md). A step-by-step tutorial is in [USER_GUIDE.md](USER_GUIDE.md). The browser app has a Polish and an English interface (switch at the top of the side panel).

## Installation

### Windows, no programming

1. Install Python 3.12 from https://www.python.org/downloads/windows/ and tick **Add python.exe to PATH** in the first screen of the installer.
2. Download the ZIP of this repository (or of the Zenodo record) and extract it.
3. Double-click `run_windows.bat` in the application folder. The first start installs the packages (5–10 min); keep the black console window open while you work.
4. The app opens in the browser at http://localhost:8501.

Requirements: an internet connection (tested on a machine with 8 GB RAM and two cores; peak memory use was not measured), about 2 GB of disk space for the packages.

### Linux, macOS, command line, Docker

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt                          # or requirements-lock.txt for the exact tested environment
pip install -e .                                         # optional: import landcoverrewind from anywhere (keeps models/ next to the package)
streamlit run app.py                                     # browser app
python landcoverrewind_cli.py --file examples/torun_centre.geojson --epochs 1990 2005 2025 --out results_example
python landcoverrewind_cli.py --bbox 18.55 52.98 18.70 53.06 --mode local --out results_local
pip install -r requirements-dev.txt && pytest -q        # unit tests on synthetic data, no network
```

Docker: `docker build -t landcoverrewind . && docker run -p 8501:8501 landcoverrewind`; command line in Docker: `docker run -v "$PWD/out:/app/out" landcoverrewind python landcoverrewind_cli.py --file examples/torun_centre.geojson --out out`.

Python API:

```python
from odc.geo.geom import box
from landcoverrewind import pipeline
r = pipeline.run(box(18.60, 53.00, 18.645, 53.027, "EPSG:4326"), epochs=[1990, 2025], mode="pretrained", out_dir="results")
r["table"]          # per-epoch metrics; r["B"][1990] is the built-up map (bool array) of epoch 1990
```

> The pretrained models are read from the `models/` folder next to the package, so run the app, the command line and the API from the unpacked source folder (or the Docker image); `pip install -e .` keeps this layout. `requirements-lock.txt` lists the exact library versions used for the tests and the published evaluation; results are bit-identical only with identical library versions and unchanged provider data.

## Outputs

| File | Content |
|---|---|
| `built_up_<epoch>.tif` | built-up land of the monotonic series (1 built-up, 0 not built-up, 255 outside the area), 30 m |
| `built_up_probability_<epoch>.tif` | Random Forest built-up probability before the series constraints, 0–100 (255 no data) |
| `land_cover_4class_<epoch>.tif` | 1 built-up, 2 trees and forest, 3 water, 4 other, 0 no data or outside the area |
| `first_detection_epoch.tif` | first epoch in which the pixel is built-up; 0 never built-up, −1 outside the area |
| `epoch_metrics.csv` | `built_up_ha` built-up area [ha], `patches` number of patches (8-neighbourhood), `mean_patch_ha` mean patch size [ha], `lpi_class_pct` share of the largest patch in the built-up area [%], `edge_density_km_per_km2` built-up boundary length [km km⁻²] (study-area boundary not counted), `linear_rate_from_base_pct_per_year` = 100·(A<sub>t</sub>/A<sub>base</sub> − 1)/(t − base), base 1990 or the earliest epoch [% yr⁻¹] |
| `growth_forms.csv` | `new_ha` new built-up land of the period [ha] and its shares [%]: `infill_pct` (≥ 4 of 8 neighbours built-up), `edge_expansion_pct` (1–3), `leapfrog_pct` (0) |
| `input_scenes.csv` | number of scenes, summer and spring scenes and sensors per epoch |
| `metadata.json` | software version, settings, date and the identifiers of all Landsat scenes of every epoch |
| `*_animation.gif`, `first_detection_map.png`, `built_up_area_chart.png` | figures (labels in English or Polish) |
| `results.zip` | all of the above |

## SDG indicator 11.3.1 (population)

After a run, the app (panel "SDG indicator 11.3.1") and the command line combine the built-up series with a population grid of two dates and compute the ratio of land consumption rate to population growth rate (LCRPGR) for the whole area and for every grid cell. Any polygon layer with population works: one file with two population columns, or two files joined by a cell identifier, such as the 1 km census grids NSP 2011 and NSP 2021 of Statistics Poland (field `tot`, identifier `code`).

```
python landcoverrewind_cli.py --file city.gpkg --population nsp2011.gpkg nsp2021.gpkg --pop-fields tot tot --pop-years 2011 2021
```

LCR follows the linear form of the UN-Habitat metadata (2025) by default (`--lcr-form log` for the logarithmic form), PGR is logarithmic, and built-up land at the census dates is interpolated between the nearest epochs. A cell ratio is reported only for cells lying wholly inside the area; when population is stable (|PGR| < 0.0013 per year) the ratio is flagged as not interpretable. Outputs: `sdg_11_3_1_cells.gpkg/.csv`, `sdg_11_3_1_summary.json`, `sdg_11_3_1.png`.

## Accuracy assessment and area estimation

Map areas are biased by classification errors. Version 1.4.0 adds the good-practice workflow of Olofsson et al. (2014):

```bash
# 1. stratified random sample of the change map 1990-2015 (at least 100 pixels per class)
python -m landcoverrewind.accuracy sample --results results --t0 1990 --t1 2015 --n 600 --min-n 100 --out sample.gpkg
# 2. open sample.gpkg in QGIS and fill the field `ref` (0 stable non-built-up, 1 stable built-up, 2 new built-up) from imagery
# 3. error-adjusted areas and accuracies with 95% confidence intervals
python -m landcoverrewind.accuracy estimate --results results --t0 1990 --t1 2015 --labels sample.gpkg
```

Omit `--t0` to assess the state map of one epoch (classes 0 non-built-up, 1 built-up). `accuracy.multiscale_agreement` compares two binary maps at several block sizes.

## Method

1. **Grid.** 30 m grid aligned to multiples of 30 m in the UTM zone of the area centroid (or in a CRS given with `--crs`).
2. **Scenes.** For epoch *t*, Landsat Collection 2 Level 2 scenes from years *t* − 1 … *t* + 1 with scene cloud cover below 70% (Landsat 4/5 TM up to 2012, Landsat 7 ETM+ 2000–2012, Landsat 8 OLI from 2013, Landsat 9 OLI from 2022).
3. **Cloud mask and harmonisation.** Pixels with QA_PIXEL bits 0–5 set (fill, dilated cloud, cirrus, cloud, shadow, snow) are removed; reflectance = DN · 2.75·10⁻⁵ − 0.2; TM and ETM+ are transformed to OLI with the ETM+→OLI OLS coefficients of Roy et al. (2016), applied to TM as an approximation.
4. **Features (18).** Summer (June–September) median of six bands, NDVI, NDBI, NDWI, MNDWI, BU (NDBI − NDVI), BSI, GLCM contrast and entropy of NIR in a 7 × 7 window (own implementation, 32 and 8 grey levels over 0–0.6 reflectance, four directions), and the spring (March–May) median NDVI, NDBI, BU and BSI. NDVI amplitude is computed but not used (unstable between epochs). Areas larger than 768 × 768 pixels are processed in tiles.
5. **Models.** `pretrained` (default): Random Forest `rf_torun_bydgoszcz_2025` trained on the 2025 maps of the reference project for Toruń and Bydgoszcz (labels transferred from Dynamic World 2025) and on features computed by this code. `local`: models trained in the user's area on Impact Observatory LULC 2023 labels aggregated to 30 m (built-up when at least 5 of 9 10 m cells are built-up; mixed pixels with 1–4 built-up cells ignored; otherwise the dominant class), 1500 points per class. Both: 300 trees, 4 features per split, minimum leaf size 1, seed 42 (scikit-learn 1.9).
6. **Series constraints.** B<sub>t</sub> = M ∩ ⋃<sub>s ≤ t</sub> (p<sub>s</sub> ≥ 0.65), where M are the 30 m pixels with at least 5 of 9 built-up 10 m cells in IO LULC 2017 or 2023. The threshold was selected on the development epoch 2005 against the reference series ([models/threshold_calibration.json](models/threshold_calibration.json)).

## Evaluation shipped with the package

`tools/compare_reference.py` compares the app series with the reference series A of the project ([10.5281/zenodo.24155226](https://doi.org/10.5281/zenodo.24155226)) in Toruń and Bydgoszcz; results are in [models/app_test.json](models/app_test.json). F1 against the reference series was 83.0–91.9%, and the app mapped 9.5–19.6% more built-up land than the reference, most in 1990. These are agreements with the maps of the reference project, not accuracies against independent data; the 2025 agreement concerns the year and cities used for training. The cross-city transfer of the pretrained model (trained in one city, tested in the other on a balanced pixel sample of the 2025 maps) is recorded in the model cards `models/*.json`.

## Known limitations

- Historical maps are approximations: in the reference project, the F1 agreement of series A with independent sources was 62–77%, and the first epoch (1985) misses part of the existing built-up land.
- The monotonic series does not record demolition.
- The pretrained model comes from two cities of one region. Elsewhere, use `--mode local` and check the result against orthophotos.
- GLCM features are scaled differently from Google Earth Engine `glcmTexture`; models trained on GEE features cannot be reused without retraining.
- Landsat MSS (1975, 1980) is not supported.
- The non-built classes (trees, water, other) are less accurate than built-up land.

## Reproducing the pretrained models

`tools/train_pretrained.py tor_v3_rf_4kl_2025.tif byd_v3_rf_4kl_2025.tif` rebuilds both models from the 2025 four-class maps of the reference project and stores the training points (`models/*_points.npz`). When a stored `.joblib` file does not match the installed scikit-learn version, the package retrains the model from these points with the same seed.

Settings: the number of download threads is set by the environment variable `LCR_THREADS` (default 8).

## Author, licence, citation

© 2026 [Grzegorz Górniak](mailto:ggorniak@doktorant.umk.pl), Nicolaus Copernicus University in Toruń. Bug reports: GitHub issues or e-mail.

Code: MIT. Models and results: CC BY 4.0. Please cite: Górniak, G., Kunz, M., 2026. Land Cover Rewind 1985–2025. Zenodo. https://doi.org/10.5281/zenodo.24332551 (see [CITATION.cff](CITATION.cff)). Reference project code and data: https://doi.org/10.5281/zenodo.24076776; rasters: https://doi.org/10.5281/zenodo.24155226.

Data: Landsat Collection 2 courtesy of the U.S. Geological Survey; Impact Observatory/Esri 10 m Annual Land Use Land Cover (CC BY 4.0); both via Microsoft Planetary Computer. Base map and search in the app © OpenStreetMap contributors.

## Notes for GIS users

- **IO LULC year.** The last Impact Observatory map in the Planetary Computer catalogue is 2023. The extent mask uses the 2017 and 2023 maps and the local model learns from the 2023 map. Versions up to 1.3.0 requested the year 2024, which the catalogue answers with the 2023 map, so their results are the same; 1.3.1 selects maps by their start year and records the item ids in `metadata.json`.
- **Grid.** The 30 m grid is aligned to multiples of 30 m in the chosen CRS so that it nests the 10 m IO LULC cells; it is offset by half a pixel from the native Landsat grid, so Landsat values are bilinearly interpolated. A user CRS must be projected in metres (`--crs`); Mercator is rejected because areas would be wrong.
- **No data.** In `built_up_<epoch>.tif`, 255 marks pixels outside the area and pixels without a valid observation in that epoch that were not built-up earlier; their share per epoch is in `metadata.json` (`no_data_share_in_area`). Areas in the tables count built-up pixels only.
- **Memory.** Downloads are tiled, but the features of an epoch are held in memory for the whole area, so memory use grows with the area; the command line refuses areas above `--max-area` (default 2500 km²).
- **Reproducibility.** `metadata.json` records the software and library versions (including GDAL), settings, grid, Landsat scene ids and IO LULC item ids. A scene whose assets cannot be read is skipped by the loader, which can change a composite; rerun if the network was unstable.

