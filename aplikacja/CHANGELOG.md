# Changelog

## 1.3.0 (2026-11-20)
- New module `population` and function `pipeline.run_sdg`: SDG indicator 11.3.1 (ratio of land consumption rate to population growth rate, LCRPGR) from the built-up series and a population grid of two dates (one file with two columns or two files joined by a cell identifier, e.g. the 1 km census grids of Statistics Poland). LCR in the linear form of the UN-Habitat metadata (2025) or in the log form; built-up land at the census dates interpolated between epochs; cell table, whole-area summary, cell typology and a figure (class map and LCR–PGR phase diagram).
- Browser app: optional SDG 11.3.1 panel after a run; command line: `--population`, `--pop-fields`, `--pop-id`, `--pop-years`, `--lcr-form`.
- New outputs: `sdg_11_3_1_cells.gpkg`, `sdg_11_3_1_cells.csv`, `sdg_11_3_1_summary.json`, `sdg_11_3_1.png` (added to `results.zip`).
- Cell share inside the area from vector intersection when the area outline is known (pixel share otherwise), warning when the population grid does not cover the area or a census date lies outside the epochs, minimum cell population for cell ratios (default 100), validation messages in the app panel.
- `metadata.json` lists skipped epochs; `requirements-lock.txt` with exact library versions; `[build-system]` in `pyproject.toml`.
- Unit tests of the indicator: synthetic grid, shifted grid, grid extending beyond the raster, two-file join, full `run_sdg` call (15 tests).
- Without an area outline, the cell share is the pixel share times the share of the cell within the raster extent, so edge cells are not counted as fully inside.
- `results.zip` contains only files written by the current run; the Docker image installs `requirements-lock.txt`; the command line rejects identical population fields for a single file; the app warns when a boundary file has no coordinate reference system.
- The modules that compute the series (`data`, `features`, `model`, `series`) are unchanged from 1.2.0.

## 1.2.0 (2026-11)
- English module and function names (`data`, `features`, `model`, `series`, `viz`, `pipeline`), English code comments and docstrings; the computation is unchanged and gives identical maps to 1.1.0.
- Bilingual browser app (Polish and English), `app.py` replaces `aplikacja.py`, `run_windows.bat` replaces `uruchom_windows.bat`.
- English output file names (e.g. `built_up_<epoch>.tif`, `epoch_metrics.csv`) and figure labels in English or Polish (`--lang`).
- Configurable extent-mask years (`extent_years`), software version and all settings stored in `metadata.json`.
- Unit tests on synthetic data (`pytest`), GitHub Actions workflow, example area, user guide, `CITATION.cff`, `pyproject.toml`.
- Fixed: the local mode stopped with an error when saving the local model.
- Environment variable `LCR_THREADS` (the former `URBANRF_WATKI` is still read).

## 1.1.0 (2026-11-18)
- First public release (Zenodo 10.5281/zenodo.24332551).
