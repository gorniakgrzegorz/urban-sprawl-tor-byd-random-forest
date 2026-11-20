"""Compare the app series with the reference series A of the project on a common 30 m grid (EPSG:2180).

Usage (from the application folder):
  python tools/compare_reference.py --labels DIR --boundaries torun.gpkg bydgoszcz.gpkg
DIR holds {tor,byd}_v3_rf_4kl_{1990,2005,2025}.tif (Zenodo record 10.5281/zenodo.24155226); boundary files are
city polygons (e.g. from the Polish State Register of Boundaries). Output: models/app_test.json.
"""
import sys, json, argparse, pathlib
import numpy as np, rasterio
from rasterio.windows import from_bounds
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import geopandas as gpd
from odc.geo.geom import Geometry
from landcoverrewind import pipeline

p = argparse.ArgumentParser()
p.add_argument("--labels", required=True); p.add_argument("--boundaries", nargs=2, required=True)
p.add_argument("--out", default="results_test"); p.add_argument("--threshold", type=float, default=0.65)
a = p.parse_args()
EP = [1990, 2005, 2025]; rows = []
for (city, pre), gfile in zip((("Torun", "tor"), ("Bydgoszcz", "byd")), a.boundaries):
    geom = Geometry(gpd.read_file(gfile).to_crs(4326).union_all(), "EPSG:4326")
    for mode in (("pretrained", "local") if pre == "tor" else ("pretrained",)):
        r = pipeline.run(geom, EP, mode, a.threshold, f"{a.out}/{pre}_{mode}", "EPSG:2180", log=lambda m: None)
        gb, area = r["geobox"], r["area"]
        for t in EP:
            with rasterio.open(f"{a.labels}/{pre}_v3_rf_4kl_{t}.tif") as s:
                ref = s.read(1, window=from_bounds(*gb.boundingbox, transform=s.transform), boundless=True,
                             fill_value=0, out_shape=gb.shape) == 1
            x, y = r["B"][t] & area, ref & area
            rows.append(dict(city=city, mode=mode, epoch=t, reference_ha=round(float(y.sum() * 0.09), 1),
                             app_ha=round(float(x.sum() * 0.09), 1), area_difference_pct=round(float(100 * (x.sum() / y.sum() - 1)), 1),
                             agreement_pct=round(float(100 * (x == y)[area].mean()), 1),
                             f1_pct=round(float(200 * (x & y).sum() / (x.sum() + y.sum())), 1)))
            print(rows[-1], flush=True)
json.dump(dict(threshold=a.threshold, epochs=rows), open("models/app_test.json", "w"), indent=1)
