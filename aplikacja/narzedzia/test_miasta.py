"""Sprawdzian aplikacji: porównanie z serią A projektu (GEE) na wspólnej siatce 30 m EPSG:2180.

Użycie (z folderu aplikacja):
  python narzedzia/test_miasta.py --etykiety KATALOG_Z_RASTRAMI --granice torun.gpkg bydgoszcz.gpkg
KATALOG_Z_RASTRAMI zawiera pliki {tor,byd}_v3_rf_4kl_{1990,2005,2025}.tif (rekord Zenodo 10.5281/zenodo.24155226);
pliki granic to poligony miast (np. z Państwowego Rejestru Granic). Wynik: modele/test_aplikacji.json.
"""
import sys, json, argparse, pathlib, numpy as np, rasterio
from rasterio.windows import from_bounds
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import geopandas as gpd
from odc.geo.geom import Geometry
from landcoverrewind import potok

p = argparse.ArgumentParser()
p.add_argument("--etykiety", required=True); p.add_argument("--granice", nargs=2, required=True)
p.add_argument("--wyniki", default="wyniki_test"); p.add_argument("--prog", type=float, default=0.65)
a = p.parse_args()
EP = [1990, 2005, 2025]; wyniki = []
for (city, pre), gfile in zip((("Toruń", "tor"), ("Bydgoszcz", "byd")), a.granice):
    geom = Geometry(gpd.read_file(gfile).to_crs(4326).union_all(), "EPSG:4326")
    for tryb in (("gotowy", "lokalny") if pre == "tor" else ("gotowy",)):
        w = potok.uruchom(geom, EP, tryb, a.prog, f"{a.wyniki}/{pre}_{tryb}", "EPSG:2180", log=lambda m: None)
        gb, ob = w["geobox"], w["obszar"]
        for t in EP:
            with rasterio.open(f"{a.etykiety}/{pre}_v3_rf_4kl_{t}.tif") as s:
                ref = s.read(1, window=from_bounds(*gb.boundingbox, transform=s.transform), boundless=True, fill_value=0, out_shape=gb.shape) == 1
            x = w["B"][t] & ob; r = ref & ob
            wyniki.append(dict(miasto=city, tryb=tryb, epoka=t, projekt_ha=round(float(r.sum() * 0.09), 1), aplikacja_ha=round(float(x.sum() * 0.09), 1),
                               roznica_proc=round(float(100 * (x.sum() / r.sum() - 1)), 1), zgodnosc_proc=round(float(100 * (x == r)[ob].mean()), 1),
                               f1_proc=round(float(200 * (x & r).sum() / (x.sum() + r.sum())), 1)))
            print(wyniki[-1], flush=True)
json.dump(dict(prog=a.prog, epoki=wyniki), open("modele/test_aplikacji.json", "w"), ensure_ascii=False, indent=1)
