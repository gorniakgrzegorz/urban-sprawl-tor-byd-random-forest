"""Download the 10 m maps needed for the extent-mask variants and store built-up fractions per 30 m pixel."""
import sys, numpy as np
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "aplikacja"))
from odc.geo.geobox import GeoBox
from landcoverrewind import data, series
from common import load_site, OUT
for site in sys.argv[1:]:
    f = OUT / site / "masks.npz"
    if f.exists():
        continue
    s = load_site(site, "gotowy")
    gb = GeoBox(s["shape"], s["tr"], s["crs"])
    out = {}
    for y in (2017, 2024):
        a, _ = data.load_10m_map("io-lulc-annual-v02", y, gb, "data")
        out[f"io{y}"] = series.built_fraction(a, gb.shape).astype("float32")
    a, _ = data.load_10m_map("esa-worldcover", 2021, gb, "map")
    out["wc2021"] = series.built_fraction(a, gb.shape, code=50).astype("float32")
    np.savez_compressed(f, **out)
    print(site, "masks ok", flush=True)
