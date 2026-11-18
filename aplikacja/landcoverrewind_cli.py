"""Wiersz poleceń.

Przykłady:
  python landcoverrewind_cli.py --bbox 18.55 52.98 18.70 53.06 --wyniki wyniki_torun
  python landcoverrewind_cli.py --plik obszar.gpkg --epoki 1990 2005 2025 --tryb lokalny
"""
import argparse
import geopandas as gpd
from odc.geo.geom import Geometry, box
from landcoverrewind import potok, EPOCHS

p = argparse.ArgumentParser(description="Zabudowa 1985–2025 z Landsat dla dowolnego obszaru (bez konta Google)")
g = p.add_mutually_exclusive_group(required=True)
g.add_argument("--plik", help="GPKG / GeoJSON / SHP z poligonem obszaru")
g.add_argument("--bbox", nargs=4, type=float, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"))
p.add_argument("--epoki", nargs="+", type=int, default=EPOCHS)
p.add_argument("--tryb", choices=["gotowy", "lokalny"], default="gotowy",
               help="gotowy: model Toruń/Bydgoszcz; lokalny: uczenie na IO LULC 2024 w tym obszarze")
p.add_argument("--prog", type=float, default=0.65)
p.add_argument("--crs", default=None, help="np. EPSG:2180; domyślnie strefa UTM")
p.add_argument("--max-chmur", type=int, default=70)
p.add_argument("--wyniki", default="wyniki")
a = p.parse_args()
if a.plik:
    gdf = gpd.read_file(a.plik).to_crs(4326)
    geom = Geometry(gdf.union_all(), "EPSG:4326")
else:
    geom = box(*a.bbox, "EPSG:4326")
potok.uruchom(geom, a.epoki, a.tryb, a.prog, a.wyniki, a.crs, a.max_chmur,
              postep=lambda u, opis: print(f"[{int(round(100 * u)):3d}%] {opis}", flush=True))
