"""Run the pipeline for one site in both training modes and store probabilities and series."""
import sys, json, math, time, pathlib, numpy as np
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "aplikacja"))
import geopandas as gpd
from odc.geo.geom import Geometry, box
from landcoverrewind import pipeline, EPOCHS

SITES = {
 "torun": dict(gpkg=str(pathlib.Path(__file__).resolve().parent / "data" / "boundaries" / "torun.gpkg"), crs="EPSG:2180"),
 "bydgoszcz": dict(gpkg=str(pathlib.Path(__file__).resolve().parent / "data" / "boundaries" / "bydgoszcz.gpkg"), crs="EPSG:2180"),
 "olsztyn": dict(c=(20.48, 53.78)), "rzeszow": dict(c=(22.00, 50.04)), "opole": dict(c=(17.92, 50.67)),
 "zielona_gora": dict(c=(15.51, 51.94)), "brno": dict(c=(16.61, 49.20)),
}
name = sys.argv[1]; modes = sys.argv[2:] or ["gotowy", "lokalny"]
s = SITES[name]
if "gpkg" in s:
    geom = Geometry(gpd.read_file(s["gpkg"]).to_crs(4326).union_all(), "EPSG:4326"); crs = s["crs"]
else:
    lon, lat = s["c"]; dy = 0.045; dx = dy / math.cos(math.radians(lat))
    geom = box(lon - dx, lat - dy, lon + dx, lat + dy, "EPSG:4326"); crs = None
out = pathlib.Path(__file__).resolve().parent / "out" / name
for m in modes:
    t0 = time.time()
    (out / m).mkdir(parents=True, exist_ok=True)
    if m != modes[0] and not (out / m / "cache").exists():
        (out / m / "cache").symlink_to(out / modes[0] / "cache")  # features do not depend on the mode
    w = pipeline.run(geom, EPOCHS, m, 0.65, str(out / m), crs, 70, log=lambda x: None)
    gb = w["geobox"]
    np.savez_compressed(out / f"{m}.npz", **{f"p{t}": np.nan_to_num(w["P"][t], nan=-1).astype("float16") for t in w["P"]},
                        **{f"b{t}": w["B"][t] for t in w["B"]}, M=w["M"], obszar=w["area"],
                        transform=np.array(tuple(gb.affine)[:6]), shape=np.array(gb.shape))
    json.dump(dict(crs=str(gb.crs), czas_s=round(time.time() - t0), pominiete=w.get("skipped", [])), open(out / f"{m}.json", "w"))
    print(name, m, "done", round(time.time() - t0), "s", flush=True)
