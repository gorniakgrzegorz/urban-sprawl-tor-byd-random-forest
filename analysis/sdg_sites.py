"""SDG 11.3.1 for Torun and Bydgoszcz from the Land Cover Rewind series (pretrained model) and the GUS NSP 1 km grids."""
import sys, json, pathlib, numpy as np
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "aplikacja"))
from affine import Affine
from landcoverrewind import population, viz
import geopandas as gpd
from rasterio import features as rf
from shapely.geometry import shape
from shapely.ops import unary_union
NSP = str(ROOT / "data" / "nsp" / "nsp_{}_wycinek_oba_miasta.gpkg")  # GUS NSP 1 km grids cut to both cities (fields code, tot)
OUT = ROOT / "out_sdg"; OUT.mkdir(exist_ok=True)
pop = population.read_population([NSP.format(2011), NSP.format(2021)], ["tot", "tot"], "code")
res, dist = {}, {}
for site in ("torun", "bydgoszcz"):
    z = np.load(ROOT / "out" / site / "gotowy.npz")
    B = {t: z[f"b{t}"].astype(bool) for t in (1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025)}
    area = z["obszar"].astype(bool); tr = Affine(*z["transform"])
    geom = unary_union([shape(g) for g, v in rf.shapes(area.astype("uint8"), mask=area, transform=tr) if v == 1])
    gpd.GeoSeries([geom], crs=2180).to_file(OUT / f"{site}_area.gpkg", driver="GPKG")
    res[site] = {}
    for form in ("linear", "log"):
        cells, s = population.sdg_11_3_1(B, area, tr, "EPSG:2180", pop, (2011, 2021), form, area_geom=geom)
        res[site][form] = s
        if form == "linear":
            cells.to_file(OUT / f"{site}_sdg_cells.gpkg", driver="GPKG")
            # distance of cells from the centre of the city (centroid of the city polygon), by sign of the cell PGR;
            # cells lying >= 99% inside the city with >= MIN_POP inhabitants in 2011 and population in 2021
            c = cells[(cells.cover >= 0.99) & (cells.pop0 >= population.MIN_POP) & (cells.pop1 > 0)]
            d_km = c.geometry.centroid.distance(geom.centroid).values / 1000
            grp = np.where(c.pgr_cell >= population.STABLE_PGR, "growth", np.where(c.pgr_cell <= -population.STABLE_PGR, "decline", "stable"))
            dist[site] = {f"n_{k}": int((grp == k).sum()) for k in ("growth", "decline", "stable")}
            dist[site].update({f"median_dist_km_{k}": round(float(np.median(d_km[grp == k])), 1) for k in ("growth", "decline") if (grp == k).any()})
            for lang in ("en", "pl"):
                viz.sdg_figure(cells, gpd.GeoSeries([geom], crs=2180), OUT / f"{site}_sdg_{lang}.png", lang)
    print(site, json.dumps(res[site]["linear"]))
json.dump(res, open(OUT / "sdg_summary.json", "w"), indent=1)
json.dump(dist, open(OUT / "sdg_distance.json", "w"), indent=1)
print(dist)
