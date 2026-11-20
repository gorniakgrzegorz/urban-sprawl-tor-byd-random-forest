# Analysis scripts for the sensitivity study

Scripts and result files behind the manuscript "Land Cover Rewind: an open tool for reconstructing built-up land from the Landsat archive and assessing the sensitivity of growth rates". They use the `landcoverrewind` package from the neighbouring `aplikacja` folder.

## Order of execution

| Step | Script | Output |
|---|---|---|
| 1 | `python run_site.py <site>` for torun, bydgoszcz, olsztyn, opole, rzeszow, zielona_gora, brno | `out/<site>/{gotowy,lokalny}.npz` and pipeline outputs (directory names: gotowy = pretrained, lokalny = local) |
| 2 | `python fetch_masks.py <sites…>` | `out/<site>/masks.npz` (IO LULC 2017, 2024 and ESA WorldCover 2021 built-up fractions) |
| 3 | `python eval_series.py` | `series_eval.json`: per-epoch confusion matrices, PA, UA, F1 and block-bootstrap CIs against WSF Evolution and series A |
| 4 | `python sens2.py` | `sensitivity2.json`: threshold, mask, rule and teacher variants, two no-change maps, change metrics with CIs, paired bootstrap of the F1 difference |
| 5 | `python ablation.py` | `ablation.json`: retrained models with feature subsets |
| 6 | `python a6.py` | `a6.json`: cloud-limit test and repeated runs on a 9.1 km² area |
| 7 | `python bdot_eval.py` | `bdot_eval.json`: agreement of the 2020 and 2025 epochs with the official topographic database BDOT10k (six Polish sites) for all variants, paired bootstrap against mask M, building-footprint area inside built-up pixels, provenance of the reference objects |
| 8 | `python sdg_sites.py` | `out_sdg/sdg_summary.json` and `out_sdg/sdg_distance.json` (copies in this folder), cell layers and figures: SDG indicator 11.3.1 for Toruń and Bydgoszcz from the series (pretrained model) and the GUS NSP 2011/2021 1 km grids (`data/nsp/`). The city area is the rasterised boundary of the 30 m series (polygonised), not the official boundary polygon. `sdg_distance.json`: median distance of cell centroids from the centroid of the city polygon for cells with a growing and a declining population (cells >= 99% inside the city, >= 100 inhabitants in 2011, population in 2021; |PGR| >= 0.0013 per year) |
| 9 | `python results2.py` | `results.json` and Figures 2–4 |

`sens.py` holds the series rule used by the other scripts. `eq_compare.json` records the bit-identical comparison of versions 1.1.0 and 1.2.0.

## Input data not included

Place them under `data/`: `wsf_evolution/WSFevolution_v1_<lon>_<lat>.tif` (DLR, CC BY 4.0; tiles 14–22° E, 48–52° N), `series_A/*.tif` and `boundaries/*.gpkg` (reference implementation, Zenodo 10.5281/zenodo.24155226 and 10.5281/zenodo.24076776). `nsp/nsp_2011_wycinek_oba_miasta.gpkg` and `nsp/nsp_2021_wycinek_oba_miasta.gpkg` are the GUS census 1 km grids cut to the two cities (fields `code`, `tot`; Geostatistics Portal resources 18337 and 24532). `bdot10k/<TERYT>/` holds the unzipped county SHP exports of BDOT10k (schema 2021, export of 3 October 2026; counties 0461, 0463, 0809, 0862, 1609, 1661, 1816, 1863, 2814, 2862) from https://opendata.geoportal.gov.pl/bdot10k/schemat2021/SHP/<voivodeship>/<TERYT>_SHP.zip (GUGiK, free use). Landsat, IO LULC and ESA WorldCover are read from Microsoft Planetary Computer by the package.

## Note on versions

The site runs reported in the manuscript were produced with landcoverrewind 1.1.0 (Polish file names); these scripts are adapted to the 1.2.0 names. Version 1.2.0 reproduces the 1.1.0 outputs bit for bit in the tested epochs 1990 and 2025 (`eq_compare.json`), and `sens2.py` asserts that the series recomputed with 1.2.0 equal the stored 1.1.0 series for all seven sites.

Version 1.3.0 adds the `population` module and `pipeline.run_sdg`; the modules that compute the series (`data`, `features`, `model`, `series`) are identical to 1.2.0, so the series outputs are unchanged. `sdg_sites.py` requires 1.3.0.

IO LULC years: the variant names and the mask keys use "2024" (e.g. `IO 2024 >=5/9`, `io2024`), because the runs requested the year 2024; the Planetary Computer collection io-lulc-annual-v02 ends with the 2023 map, which is what a 2024 search returns. All these masks are therefore built from the IO LULC 2017 and 2023 maps (checked: identical arrays). Version 1.3.0 selects maps by their start year and requests 2023.
