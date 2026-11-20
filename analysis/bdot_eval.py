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
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "aplikacja"))
from landcoverrewind import model, pipeline
from common import *
from sens import series_from

RAW = DATA / "bdot10k"  # county folders <TERYT>/ with the unzipped SHP export, see README

COUNTIES = {"torun": ["0463"], "bydgoszcz": ["0461"], "olsztyn": ["2862", "2814"], "opole": ["1661", "1609"],
            "rzeszow": ["1863", "1816"], "zielona_gora": ["0862", "0809"]}
NB, SEED = 300, 42
rf_pre, _ = model.load(pipeline.PRETRAINED[0])


def probs(rf, d):
    p = {}
    for f in glob.glob(str(d / "gotowy/cache/features_*_*.npy")):
        t = int(f.split("features_")[1][:4]); F = np.load(f).astype("float32")
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


rows, meta = [], {}
for site in COUNTIES:
    d = OUT / site
    s = load_site(site, "gotowy"); H, W = s["shape"]
    x0, y0 = s["tr"].c, s["tr"].f; bbox = (x0, y0 - 30 * H, x0 + 30 * W, y0)
    lay = {L: read(site, L, bbox, s["crs"]) for L in ("PTZB", "PTKM", "PTPL", "BUBD")}
    cov = np.zeros((H, W), "float32")
    allpt = set(f.split("__OT_")[1][:4] for c in COUNTIES[site] for f in glob.glob(str(RAW / c / "*__OT_PT*_A.shp")))
    for L in sorted(allpt):
        g = lay[L] if L in lay else read(site, L, bbox, s["crs"])
        cov += frac(list(g.geometry), s)
    covered = cov >= 5 / 9 - 1e-9
    fz = frac(list(lay["PTZB"].geometry), s)
    fzp = np.clip(fz + frac(list(lay["PTKM"].geometry), s) + frac(list(lay["PTPL"].geometry), s), 0, 1)
    fb = frac(list(lay["BUBD"].geometry), s)
    thr = 5 / 9 - 1e-9
    refs = {"PTZB": fz >= thr, "PTZB+PTKM+PTPL": fzp >= thr, "BUBD": fb >= thr}
    m = s["area"] & covered; blocks = block_ids(s["shape"])
    # provenance of the reference polygons inside the evaluated area
    def prov(g):
        if not len(g):
            return {}
        g = g.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
        src = g["ZRO_DANYCH"].fillna("n.d.").value_counts(normalize=True).round(4).to_dict()
        ver = pd.to_datetime(g["WERSJA"].str[:8], format="%Y%m%d", errors="coerce")
        return dict(n=int(len(g)), source_share=src, version_min=str(ver.min().date()), version_median=str(ver.median().date()),
                    version_max=str(ver.max().date()), share_version_2023_or_later=float((ver.dt.year >= 2023).mean()))
    meta[site] = dict(covered_share=float(covered[s["area"]].mean()), evaluated_px=int(m.sum()),
                      ref_ha={k: float(v[m].sum() * 0.09) for k, v in refs.items()},
                      building_area_ha=float((fb * 0.09)[m].sum()), PTZB=prov(lay["PTZB"]), BUBD=prov(lay["BUBD"]))
    p = probs(rf_pre, d)
    mk = np.load(d / "masks.npz")
    masks = {"IO 2017|2024 >=5/9": s["M"], "IO 2017|2024 any": (mk["io2017"] > 0) | (mk["io2024"] > 0), "IO 2024 >=5/9": mk["io2024"] >= thr,
             "WorldCover 2021 >=5/9": mk["wc2021"] >= thr, "WorldCover 2021 any": mk["wc2021"] > 0, "none": None}
    variants = [("threshold", f"{t:.2f}", t, "IO 2017|2024 >=5/9", True) for t in (0.45, 0.55, 0.65, 0.75, 0.85)]
    variants += [("mask", k, 0.65, k, True) for k in masks if k != "IO 2017|2024 >=5/9"]
    variants += [("rule", "per-epoch (no accumulation)", 0.65, "IO 2017|2024 >=5/9", False)]
    Bdef = series_from(p, 0.65, s["M"])
    assert all(np.array_equal(Bdef[t], s["b"][t]) for t in Bdef)
    Bloc = series_from(probs(joblib.load(d / "lokalny" / "local_model_binary.joblib"), d), 0.65, s["M"])
    for rname, R in refs.items():
        for t in (2020, 2025):
            for fam, lab, tau, mkey, mono in variants:
                B = series_from(p, tau, masks[mkey], mono)[t]
                rows.append(dict(site=site, reference=rname, epoch=t, family=fam, variant=lab, **f1s(B, R, m)))
            rows.append(dict(site=site, reference=rname, epoch=t, family="mode", variant="local", **f1s(Bloc[t], R, m)))
            for k in ("IO 2017|2024 >=5/9", "WorldCover 2021 >=5/9"):
                rows.append(dict(site=site, reference=rname, epoch=t, family="product", variant=k, **f1s(masks[k], R, m)))
            if True:
                pr = paired(Bdef[t], s["M"], R, m, blocks)
                ci = boot_ci(Bdef[t], R, m, blocks, n=NB)
                rows.append(dict(site=site, reference=rname, epoch=t, family="paired", variant="default minus mask M", **pr, f1_ci=ci["f1"]))
    # detection of building footprints by area (share of BUBD area inside built-up pixels of the default series)
    for t in (2020, 2025):
        meta[site][f"building_area_detected_{t}"] = float((fb * Bdef[t])[m].sum() / fb[m].sum())
        meta[site][f"building_area_in_M"] = float((fb * s["M"])[m].sum() / fb[m].sum())
    print(site, meta[site]["covered_share"], meta[site]["ref_ha"], flush=True)
json.dump(dict(rows=rows, meta=meta), open("bdot_eval.json", "w"), indent=0, default=str)
