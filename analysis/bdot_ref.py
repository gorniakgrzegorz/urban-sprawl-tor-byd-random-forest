"""Agreement of the 2025 (and 2020) epochs with the official topographic database BDOT10k (Polish sites only).

Reference layers (BDOT10k, schema 2021, SHP export of the county files from opendata.geoportal.gov.pl):
  PTZB  land cover "built-up areas" (OT_PTZB_A),
  PTZB+ built-up areas, transport areas and squares (OT_PTZB_A, OT_PTKM_A, OT_PTPL_A),
  BUBD  building footprints (OT_BUBD_A).
Polygons are rasterised on a 10 m sub-grid of each 30 m site grid; a 30 m pixel is reference built-up when at
least 5 of its 9 sub-pixels are inside the layer (the rule used for the extent mask M). Only pixels covered by the
BDOT10k land-cover tessellation (all OT_PT*_A layers) are evaluated.
"""
import sys, json, glob, pathlib, numpy as np, geopandas as gpd, joblib, pandas as pd
from rasterio import features
from affine import Affine
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "aplikacja"))
from landcoverrewind import model, pipeline
from common import *
from sens import series_from

RAW = DATA / "bdot10k"  # county SHP exports, not redistributed (see README)
COUNTIES = {"torun": ["0463"], "bydgoszcz": ["0461"], "olsztyn": ["2862", "2814"], "opole": ["1661", "1609"],
            "rzeszow": ["1863", "1816"], "zielona_gora": ["0862", "0809"]}
NB, SEED = 300, 42


def probs(rf, d):
    p = {}
    for f in glob.glob(str(d / "gotowy/cache/cechy_*_*.npy")):
        t = int(f.split("cechy_")[1][:4]); F = np.load(f).astype("float32")
        p[t] = model.predict(rf, F)[list(rf.classes_).index(1)]
    return p


def frac(geoms, s):
    H, W = s["shape"]; tr = s["tr"] * Affine.scale(1 / 3)
    if len(geoms) == 0:
        return np.zeros((H, W), "float32")
    r = features.rasterize(((g, 1) for g in geoms), out_shape=(3 * H, 3 * W), transform=tr, fill=0, dtype="uint8")
    return r.reshape(H, 3, W, 3).sum(axis=(1, 3)) / 9.0


def read(site, layer, bbox, crs):
    """BDOT10k layer (EPSG:2180) cut to the site bounding box and reprojected to the site CRS."""
    from shapely.geometry import box
    b2180 = gpd.GeoSeries([box(*bbox)], crs=crs).to_crs(2180).total_bounds
    out = []
    for c in COUNTIES[site]:
        for f in glob.glob(str(RAW / c / f"*__OT_{layer}_A.shp")):
            g = gpd.read_file(f, bbox=tuple(b2180))
            if len(g):
                out.append(g.set_crs(2180, allow_override=True).to_crs(crs))
    return pd.concat(out, ignore_index=True) if out else gpd.GeoDataFrame(geometry=[], crs=crs)


def f1s(x, y, m):
    tp, fp, fn, tn = confusion(x, y, m)
    return scores(tp, fp, fn, tn)


def paired(xa, xb, y, m, blocks):
    ids = blocks[m]; k = ids.max() + 1; used = np.unique(ids)
    cnt = lambda x: (np.bincount(ids, x[m] & y[m], k), np.bincount(ids, x[m] & ~y[m], k), np.bincount(ids, ~x[m] & y[m], k))
    a, b = cnt(xa), cnt(xb)
    f = lambda c, sl: 2 * c[0][sl].sum() / (2 * c[0][sl].sum() + c[1][sl].sum() + c[2][sl].sum())
    rng = np.random.default_rng(SEED)
    d = [f(a, sl) - f(b, sl) for sl in (rng.choice(used, used.size) for _ in range(NB))]
    return dict(d_f1=float(f(a, used) - f(b, used)), ci=[float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))])


