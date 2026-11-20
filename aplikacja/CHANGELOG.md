# Changelog

## 1.4.0 (2026-11-20)
- New module `accuracy` (API and `python -m landcoverrewind.accuracy`): stratified random sample of map classes of a state map (built-up, non-built-up) or a change map between two epochs (stable non-built-up, stable built-up, new built-up), with a minimum sample size per class; export to GPKG or CSV with an empty `ref` field for photointerpretation in QGIS; stratified estimators of overall, user's and producer's accuracy and of error-adjusted class areas with 95% confidence intervals (Olofsson et al. 2014); sample-size formula for a target standard error of overall accuracy.
- `accuracy.multiscale_agreement`: agreement of two binary maps in blocks of s x s pixels (pixel F1 to quantity agreement).
- Unit tests of the module: allocation, unbiasedness and interval coverage of the area estimator on a synthetic map, multi-scale agreement (19 tests).
- The computation of the series is unchanged.

## 1.3.1 (2026-11-20)
- IO LULC maps are selected by their start year. The collection io-lulc-annual-v02 ends with the 2023 map; earlier versions requested 2024, which the catalogue answers with the 2023 map, so the default extent mask (2017 and 2023) and the local-model labels (2023) are unchanged and now named correctly. A search for 2018–2022 no longer merges two consecutive maps. The STAC item ids of the maps are written to `metadata.json`.
- A user CRS must be projected in metres (Mercator rejected); the command line validates epochs, threshold, cloud limit, input CRS and geometry (made valid), rejects areas crossing the antimeridian and areas larger than `--max-area` (default 2500 km²), checks population fields before the run and prints short error messages.
- `built_up_<epoch>.tif` marks pixels without valid observations in the epoch (and not built-up earlier) as no data (255); `metadata.json` adds the no-data share per epoch, the grid transform and shape, and library versions (including GDAL).
- The cache key includes the software version; missing model files give a clear message; a model rebuilt from the stored points is reported.
- SDG 11.3.1: the cell identifier is kept also for a single population file, the cell layer is written in the CRS of the population grid, missing population values stay missing, and the ratio of stable-population cells is not reported.
- The computation of the series (`features`, `model`, `series`) is unchanged from 1.2.0; the published series are reproduced.
- Full environment file `requirements-lock.txt` (pip freeze of a clean environment with Python version) and `requirements-dev.txt` (pytest).

## 1.3.0 (2026-11-20, Zenodo 10.5281/zenodo.24392970)
- New module `population` and function `pipeline.run_sdg`: SDG indicator 11.3.1 (ratio of land consumption rate to population growth rate, LCRPGR) from the built-up series and a population grid of two dates (one file with two columns or two files joined by a cell identifier, e.g. the 1 km census grids of Statistics Poland). LCR in the linear form of the UN-Habitat metadata (2025) or in the log form; built-up land at the census dates interpolated between epochs; cell table, whole-area summary, cell typology and a figure (class map and LCR–PGR phase diagram).
- Browser app: optional SDG 11.3.1 panel after a run; command line: `--population`, `--pop-fields`, `--pop-id`, `--pop-years`, `--lcr-form`.
- New outputs: `sdg_11_3_1_cells.gpkg`, `sdg_11_3_1_cells.csv`, `sdg_11_3_1_summary.json`, `sdg_11_3_1.png` (added to `results.zip`).
- Cell share inside the area from vector intersection when the area outline is known (pixel share otherwise), warning when the population grid does not cover the area or a census date lies outside the epochs, minimum cell population for cell ratios (default 100), validation messages in the app panel.
- `metadata.json` lists skipped epochs; `requirements-lock.txt` with exact library versions; `[build-system]` in `pyproject.toml`.
- Unit tests of the indicator: synthetic grid, shifted grid, grid extending beyond the raster, two-file join, full `run_sdg` call (15 tests).
- Without an area outline, the cell share is the pixel share times the share of the cell within the raster extent, so edge cells are not counted as fully inside.
- `results.zip` contains only files written by the current run; the Docker image installs `requirements-lock.txt`; the command line rejects identical population fields for a single file; the app warns when a boundary file has no coordinate reference system.

## 1.2.0 (2026-11)
- English module and function names (`data`, `features`, `model`, `series`, `viz`, `pipeline`), English code comments and docstrings; the computation is unchanged and gives identical maps to 1.1.0.
- Bilingual browser app (Polish and English), `app.py` replaces `aplikacja.py`, `run_windows.bat` replaces `uruchom_windows.bat`.
- English output file names (e.g. `built_up_<epoch>.tif`, `epoch_metrics.csv`) and figure labels in English or Polish (`--lang`).
- Configurable extent-mask years (`extent_years`), software version and all settings stored in `metadata.json`.
- Unit tests on synthetic data (`pytest`), GitHub Actions workflow, example area, user guide, `CITATION.cff`, `pyproject.toml`.
- Fixed: the local mode stopped with an error when saving the local model.
- Environment variable `LCR_THREADS` (the former `URBANRF_WATKI` is still read).

## 1.1.0 (2026-11-18)
- First public release (Zenodo 10.5281/zenodo.24332552; all versions: 10.5281/zenodo.24332551).
