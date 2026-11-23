"""Command-line interface.

Examples:
  python landcoverrewind_cli.py --bbox 18.55 52.98 18.70 53.06 --out results_torun
  python landcoverrewind_cli.py --file area.gpkg --epochs 1990 2005 2025 --mode local
  python landcoverrewind_cli.py --file city.gpkg --population nsp2011.gpkg nsp2021.gpkg --pop-years 2011 2021
"""
import argparse
import datetime
import sys
import geopandas as gpd
from shapely.validation import make_valid
from odc.geo.geom import Geometry, box
from landcoverrewind import pipeline, population, EPOCHS, __version__

p = argparse.ArgumentParser(description="Built-up land and land cover 1985-2025 from Landsat for any area (no Google account)",
                            formatter_class=argparse.ArgumentDefaultsHelpFormatter, epilog=__doc__.split("Examples:")[1].join(["Examples:", ""]))
p.add_argument("--version", action="version", version=f"landcoverrewind {__version__}")
g = p.add_mutually_exclusive_group(required=True)
g.add_argument("--file", help="GPKG / GeoJSON / SHP with the area polygon")
g.add_argument("--bbox", nargs=4, type=float, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"))
p.add_argument("--epochs", nargs="+", type=int, default=EPOCHS, help="epoch years (window: year - 1 to year + 1), 1985 or later")
p.add_argument("--mode", choices=["pretrained", "local"], default="pretrained",
               help="pretrained: 2025 model (trained on Toruń & Bydgoszcz); local: training on IO LULC 2023 in this area")
p.add_argument("--threshold", type=float, default=0.65, help="probability threshold of built-up land (0-1)")
p.add_argument("--crs", default=None, help="projected CRS in metres, e.g. EPSG:2180; UTM zone of the centroid by default")
p.add_argument("--max-cloud", type=int, default=70, help="maximum scene cloud cover [%%]")
p.add_argument("--max-area", type=float, default=2500, help="refuse larger areas [km2] (memory grows with area x epochs)")
p.add_argument("--lang", choices=["en", "pl"], default="en", help="language of figure labels")
p.add_argument("--out", default="results", help="output folder (features are cached in OUT/cache)")
p.add_argument("--population", nargs="+", metavar="FILE", help="SDG 11.3.1: population grid, one file with two columns or two files")
p.add_argument("--pop-fields", nargs=2, metavar=("FIELD_T0", "FIELD_T1"), default=["tot", "tot"])
p.add_argument("--pop-id", default="code", help="cell identifier (joins two population files; kept in the output)")
p.add_argument("--pop-years", nargs=2, type=int, metavar=("YEAR_T0", "YEAR_T1"), default=[2011, 2021])
p.add_argument("--lcr-form", choices=["linear", "log"], default="linear")
a = p.parse_args()
if a.population and len(a.population) == 1 and a.pop_fields[0] == a.pop_fields[1]:
    p.error("--pop-fields must name two different columns when a single population file is given")
if not 0 < a.threshold < 1:
    p.error("--threshold must lie between 0 and 1")
if not 0 < a.max_cloud <= 100:
    p.error("--max-cloud must lie between 1 and 100")
bad = [e for e in a.epochs if e < 1985 or e > datetime.date.today().year]
if bad:
    p.error(f"epochs {bad} are outside 1985-present (Landsat MSS years 1975 and 1980 are not supported)")
try:
    if a.file:
        gdf = gpd.read_file(a.file)
        if gdf.crs is None:
            p.error(f"{a.file} has no coordinate reference system; save it with a CRS (e.g. in QGIS)")
        shape = make_valid(gdf.to_crs(4326).union_all())
    else:
        if a.bbox[0] >= a.bbox[2] or a.bbox[1] >= a.bbox[3]:
            p.error("--bbox must be LON_MIN LAT_MIN LON_MAX LAT_MAX with LON_MIN < LON_MAX (areas crossing the antimeridian are not supported)")
        shape = box(*a.bbox, "EPSG:4326").geom
    if shape.is_empty or shape.area == 0:
        p.error("the area is empty or has zero area")
    if shape.bounds[2] - shape.bounds[0] > 180:
        p.error("areas crossing the antimeridian are not supported")
    km2 = gpd.GeoSeries([shape], crs=4326).to_crs(6933).area.iloc[0] / 1e6
    if km2 > a.max_area:
        p.error(f"the area has {km2:.0f} km2 (> --max-area {a.max_area:.0f}); split it or raise --max-area")
    if a.population:  # check the population files before the long run
        population.read_population(a.population, a.pop_fields, a.pop_id if len(a.population) == 2 else None)
    geom = Geometry(shape, "EPSG:4326")
    res = pipeline.run(geom, a.epochs, a.mode, a.threshold, a.out, a.crs, a.max_cloud, lang=a.lang,
                       progress=lambda u, step: print(f"[{int(round(100 * u)):3d}%] {step}", flush=True))
    if a.population:
        cells, summary = pipeline.run_sdg(res, a.population, a.pop_fields, a.pop_years, a.pop_id, a.lcr_form, a.lang,
                                          area_geom=geom)
        print("SDG 11.3.1:", summary)
except (RuntimeError, ValueError, FileNotFoundError) as e:
    print(f"error: {e}", file=sys.stderr)
    sys.exit(1)
