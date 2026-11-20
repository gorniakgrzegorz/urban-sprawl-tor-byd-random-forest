"""Shared helpers for the evaluation of the Land Cover Rewind series."""
import json, pathlib, numpy as np, rasterio
from affine import Affine
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"  # input data not redistributed here, see README
OUT = ROOT / "out"
REF = DATA / "wsf_evolution"
EP = [1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]
SERIES_A = {"torun": str(DATA / "series_A" / "torw_zabudowa_1975_2025.tif"), "bydgoszcz": str(DATA / "series_A" / "bydw_zabudowa_1975_2025.tif")}


def load_site(site, mode):
    z = np.load(OUT / site / f"{mode}.npz")
    meta = json.load(open(OUT / site / f"{mode}.json"))
    tr = Affine(*z["transform"]); shape = tuple(z["shape"])
    p = {t: z[f"p{t}"].astype("float32") for t in EP if f"p{t}" in z.files}
    for t in p:
        p[t][p[t] < 0] = np.nan
    b = {t: z[f"b{t}"] for t in EP if f"b{t}" in z.files}
    return dict(p=p, b=b, M=z["M"], area=z["obszar"], tr=tr, shape=shape, crs=meta["crs"], time=meta["czas_s"])


def wsf_on_grid(s):
    """WSF Evolution first-settlement year (0 = none) resampled (nearest) to the site grid."""
    dst = np.zeros(s["shape"], "int32")
    for f in sorted(REF.glob("WSFevolution_v1_*.tif")):
        tmp = np.zeros(s["shape"], "int32")
        with rasterio.open(f) as src:
            reproject(rasterio.band(src, 1), tmp, dst_transform=s["tr"], dst_crs=s["crs"], resampling=Resampling.nearest,
                      src_nodata=None, dst_nodata=0)
        dst = np.where(dst > 0, dst, tmp)
    return dst


def series_a_on_grid(site, s):
    """Reference series A (bands 1975, 1980, 1985 ... 2025) cut to the site grid; dict epoch -> bool."""
    H, W = s["shape"]
    x0, y0 = s["tr"].c, s["tr"].f
    bounds = (x0, y0 - 30 * H, x0 + 30 * W, y0)
    with rasterio.open(SERIES_A[site]) as src:
        a = src.read(window=from_bounds(*bounds, transform=src.transform), boundless=True, fill_value=255, out_shape=(src.count, H, W))
    return {t: a[i + 2] == 1 for i, t in enumerate(EP)}, (a[2] != 255)


def confusion(x, y, m):
    x, y = x[m], y[m]
    tp = np.sum(x & y); fp = np.sum(x & ~y); fn = np.sum(~x & y); tn = np.sum(~x & ~y)
    return tp, fp, fn, tn


def scores(tp, fp, fn, tn):
    n = tp + fp + fn + tn
    ua = tp / (tp + fp) if tp + fp else np.nan
    pa = tp / (tp + fn) if tp + fn else np.nan
    f1 = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
    return dict(oa=(tp + tn) / n, pa=pa, ua=ua, f1=f1, map_ha=(tp + fp) * 0.09, ref_ha=(tp + fn) * 0.09)


def block_ids(shape, size=33):
    """Block index of each pixel (about 1 km x 1 km blocks) for the spatial block bootstrap."""
    H, W = shape
    r, c = np.meshgrid(np.arange(H) // size, np.arange(W) // size, indexing="ij")
    return r * (W // size + 1) + c


def boot_ci(x, y, m, blocks, n=1000, seed=42):
    """95% percentile CI of F1, PA and UA by resampling ~1 km blocks with replacement."""
    ids = blocks[m]; xs, ys = x[m], y[m]
    k = ids.max() + 1
    tp = np.bincount(ids, xs & ys, k); fp = np.bincount(ids, xs & ~ys, k); fn = np.bincount(ids, ~xs & ys, k)
    used = np.unique(ids)
    rng = np.random.default_rng(seed); out = []
    for _ in range(n):
        s = rng.choice(used, used.size, replace=True)
        a, b, c = tp[s].sum(), fp[s].sum(), fn[s].sum()
        out.append((2 * a / (2 * a + b + c) if a else 0, a / (a + c) if a + c else np.nan, a / (a + b) if a + b else np.nan))
    o = np.array(out)
    return {k: tuple(np.nanpercentile(o[:, i], [2.5, 97.5]).round(4)) for i, k in enumerate(("f1", "pa", "ua"))}
