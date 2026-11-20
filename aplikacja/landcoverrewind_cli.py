"""Command-line interface.

Examples:
  python landcoverrewind_cli.py --bbox 18.55 52.98 18.70 53.06 --out results_torun
  python landcoverrewind_cli.py --file area.gpkg --epochs 1990 2005 2025 --mode local
  python landcoverrewind_cli.py --file city.gpkg --population nsp2011.gpkg nsp2021.gpkg --pop-years 2011 2021
"""
import argparse
import geopandas as gpd
from odc.geo.geom import Geometry, box
from landcoverrewind import pipeline, EPOCHS

p = argparse.ArgumentParser(description="Built-up land and land cover 1985-2025 from Landsat for any area (no Google account)")
g = p.add_mutually_exclusive_group(required=True)
g.add_argument("--file", help="GPKG / GeoJSON / SHP with the area polygon")
g.add_argument("--bbox", nargs=4, type=float, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"))
p.add_argument("--epochs", nargs="+", type=int, default=EPOCHS)
p.add_argument("--mode", choices=["pretrained", "local"], default="pretrained",
               help="pretrained: Torun/Bydgoszcz 2025 model; local: training on IO LULC 2024 in this area")
p.add_argument("--threshold", type=float, default=0.65)
p.add_argument("--crs", default=None, help="e.g. EPSG:2180; UTM zone of the centroid by default")
p.add_argument("--max-cloud", type=int, default=70)
p.add_argument("--lang", choices=["en", "pl"], default="en", help="language of figure labels")
p.add_argument("--out", default="results")
p.add_argument("--population", nargs="+", metavar="FILE", help="SDG 11.3.1: population grid, one file with two columns or two files")
p.add_argument("--pop-fields", nargs=2, metavar=("FIELD_T0", "FIELD_T1"), default=["tot", "tot"])
p.add_argument("--pop-id", default="code", help="cell identifier joining two population files")
p.add_argument("--pop-years", nargs=2, type=int, metavar=("YEAR_T0", "YEAR_T1"), default=[2011, 2021])
p.add_argument("--lcr-form", choices=["linear", "log"], default="linear")
a = p.parse_args()
if a.population and len(a.population) == 1 and a.pop_fields[0] == a.pop_fields[1]:
    p.error("--pop-fields must name two different columns when a single population file is given")
if a.file:
    geom = Geometry(gpd.read_file(a.file).to_crs(4326).union_all(), "EPSG:4326")
else:
    geom = box(*a.bbox, "EPSG:4326")
res = pipeline.run(geom, a.epochs, a.mode, a.threshold, a.out, a.crs, a.max_cloud, lang=a.lang,
             progress=lambda u, step: print(f"[{int(round(100 * u)):3d}%] {step}", flush=True))
if a.population:
    cells, summary = pipeline.run_sdg(res, a.population, a.pop_fields, a.pop_years,
                                      a.pop_id if len(a.population) == 2 else None, a.lcr_form, a.lang, area_geom=geom)
    print("SDG 11.3.1:", summary)
