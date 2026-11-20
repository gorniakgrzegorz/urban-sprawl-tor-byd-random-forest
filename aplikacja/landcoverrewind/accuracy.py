"""Accuracy assessment and area estimation for built-up land maps and change maps.

Implements the good-practice workflow of Olofsson et al. (2014, Remote Sensing of Environment 148, 42-57):
stratified random sampling with the map classes as strata, reference labels supplied by the user (for example
by photointerpretation in QGIS), and stratified estimators of overall, user's and producer's accuracy and of
error-adjusted class areas with 95% confidence intervals. A multi-scale agreement measure for map comparison
(Pontius 2002) is also provided.

Map classes
  state map of epoch t:          0 non-built-up, 1 built-up
  change map between t0 and t1:  0 stable non-built-up, 1 stable built-up (built-up at t0), 2 new built-up

Command line
  python -m landcoverrewind.accuracy sample   --results DIR --t1 2015 [--t0 1990] --n 600 [--min-n 100] --out sample.gpkg
  python -m landcoverrewind.accuracy estimate --results DIR --t1 2015 [--t0 1990] --labels sample.gpkg [--ref-field ref]
"""
from __future__ import annotations
import argparse
import json
import math
import pathlib
import numpy as np

Z95 = 1.959964
CLASS_NAMES = {"state": {0: "non-built-up", 1: "built-up"},
               "change": {0: "stable non-built-up", 1: "stable built-up", 2: "new built-up"}}


# ----------------------------------------------------------------------------- maps and strata
def state_map(b, valid=None):
    """Two-class map (uint8) from a boolean built-up raster; 255 outside `valid`."""
    m = np.asarray(b).astype("uint8")
    if valid is not None:
        m = np.where(valid, m, 255).astype("uint8")
    return m


def change_map(b0, b1, valid=None):
    """Three-class change map: 0 stable non-built-up, 1 built-up at t0, 2 new built-up between t0 and t1."""
    b0 = np.asarray(b0, bool); b1 = np.asarray(b1, bool)
    m = np.zeros(b0.shape, "uint8")
    m[b0] = 1
    m[b1 & ~b0] = 2
    if valid is not None:
        m = np.where(valid, m, 255).astype("uint8")
    return m


def class_counts(m):
    """Pixel count of each map class (255 = outside the area)."""
    v, c = np.unique(m[m != 255], return_counts=True)
    return {int(a): int(b) for a, b in zip(v, c)}


# ----------------------------------------------------------------------------- sample design
def sample_size(weights, ua_guess, target_se_oa=0.01):
    """Total sample size for a target standard error of overall accuracy (Olofsson et al. 2014, Eq. 13)."""
    s = sum(w * math.sqrt(u * (1 - u)) for w, u in zip(weights, ua_guess))
    return int(math.ceil((s / target_se_oa) ** 2))


def allocate(counts, n_total, min_n=50):
    """Allocation of `n_total` sample units to strata: at least `min_n` per stratum (rare classes such as
    new built-up land), the remainder proportional to stratum area. Never more units than pixels."""
    k = sorted(counts)
    n = {h: min(min_n, counts[h]) for h in k}
    rest = max(n_total - sum(n.values()), 0)
    tot = sum(counts.values())
    for h in k:
        n[h] = min(counts[h], n[h] + int(round(rest * counts[h] / tot)))
    return n


def draw_sample(m, transform, n_per_class, seed=42):
    """Stratified random sample of pixel centres: list of dicts (id, map_class, row, col, x, y)."""
    rng = np.random.default_rng(seed)
    out = []
    for h in sorted(n_per_class):
        idx = np.flatnonzero(m.ravel() == h)
        if not len(idx) or n_per_class[h] <= 0:
            continue
        pick = rng.choice(idx, size=min(n_per_class[h], len(idx)), replace=False)
        rows, cols = np.unravel_index(np.sort(pick), m.shape)
        for r, c in zip(rows, cols):
            x, y = transform * (c + 0.5, r + 0.5)
            out.append(dict(map_class=int(h), row=int(r), col=int(c), x=float(x), y=float(y)))
    for i, d in enumerate(out, 1):
        d["id"] = i
    return out


# ----------------------------------------------------------------------------- estimators
def estimate(map_class, ref_class, counts, pixel_area=900.0):
    """Stratified estimators with the map classes as strata (Olofsson et al. 2014, Eqs. 2-10).

    map_class, ref_class: sequences of the sampled units (same length); counts: map pixel count per class.
    Returns a dict with the error matrix in area proportions, OA, UA, PA with standard errors and 95% CIs,
    mapped and error-adjusted areas (ha) with 95% CIs."""
    mc = np.asarray(map_class, int); rc = np.asarray(ref_class, int)
    K = sorted(set(counts) | set(rc.tolist()))
    N = float(sum(counts.values()))
    W = {h: counts.get(h, 0) / N for h in K}
    n = {h: int(np.sum(mc == h)) for h in K}
    nij = {(i, j): int(np.sum((mc == i) & (rc == j))) for i in K for j in K}
    p = {(i, j): (W[i] * nij[i, j] / n[i] if n[i] else 0.0) for i in K for j in K}
    res = dict(classes=K, n=n, map_pixels={h: counts.get(h, 0) for h in K}, matrix_area_proportions={f"{i}->{j}": p[i, j] for i in K for j in K})
    oa = sum(p[h, h] for h in K)
    v_oa = sum(W[h] ** 2 * (nij[h, h] / n[h]) * (1 - nij[h, h] / n[h]) / (n[h] - 1) for h in K if n[h] > 1)
    res["overall_accuracy"] = dict(value=oa, se=math.sqrt(v_oa), ci95=Z95 * math.sqrt(v_oa))
    A = N * pixel_area / 1e4
    res["total_area_ha"] = A
    cls = {}
    for j in K:
        pj = sum(p[i, j] for i in K)
        v_pj = sum(W[i] ** 2 * (nij[i, j] / n[i]) * (1 - nij[i, j] / n[i]) / (n[i] - 1) for i in K if n[i] > 1)
        ua = nij[j, j] / n[j] if n[j] else float("nan")
        v_ua = ua * (1 - ua) / (n[j] - 1) if n[j] > 1 else float("nan")
        # producer's accuracy and its variance (Olofsson et al. 2014, Eqs. 6-7, written with estimated class totals)
        Ni = {i: counts.get(i, 0) for i in K}
        Nj_hat = sum(Ni[i] * nij[i, j] / n[i] for i in K if n[i])
        pa = (Ni[j] * nij[j, j] / n[j]) / Nj_hat if (n[j] and Nj_hat) else float("nan")
        if n[j] > 1 and Nj_hat:
            t1 = Ni[j] ** 2 * (1 - pa) ** 2 * ua * (1 - ua) / (n[j] - 1)
            t2 = pa ** 2 * sum(Ni[i] ** 2 * (nij[i, j] / n[i]) * (1 - nij[i, j] / n[i]) / (n[i] - 1) for i in K if i != j and n[i] > 1)
            v_pa = (t1 + t2) / Nj_hat ** 2
        else:
            v_pa = float("nan")
        cls[j] = dict(mapped_area_ha=counts.get(j, 0) * pixel_area / 1e4,
                      adjusted_area_ha=pj * A, adjusted_area_ci95_ha=Z95 * math.sqrt(v_pj) * A,
                      users_accuracy=ua, users_accuracy_ci95=Z95 * math.sqrt(v_ua) if v_ua == v_ua else float("nan"),
                      producers_accuracy=pa, producers_accuracy_ci95=Z95 * math.sqrt(v_pa) if v_pa == v_pa else float("nan"))
    res["classes_detail"] = cls
    return res


# ----------------------------------------------------------------------------- map comparison
def multiscale_agreement(a, r, valid=None, sizes=(1, 3, 10, 33)):
    """Agreement of two binary maps (for example new built-up land in the series and in a reference product)
    in square blocks of s x s pixels: F1_s = 2 * sum(min(a_b, r_b)) / (sum a_b + sum r_b), where a_b and r_b
    are the counts of positive pixels in block b (Pontius 2002). s = 1 gives the pixel F1; the value for the
    whole area ('area') measures quantity agreement only."""
    a = np.asarray(a, bool); r = np.asarray(r, bool)
    if valid is not None:
        a = a & valid; r = r & valid
    out = {}
    H, W = a.shape
    for s in sizes:
        h, w = -(-H // s) * s, -(-W // s) * s
        blk = lambda x: np.pad(x.astype("float64"), ((0, h - H), (0, w - W))).reshape(h // s, s, w // s, s).sum((1, 3))
        A_, R_ = blk(a), blk(r)
        den = A_.sum() + R_.sum()
        out[s] = float(2 * np.minimum(A_, R_).sum() / den) if den else float("nan")
    sa, sr = float(a.sum()), float(r.sum())
    out["area"] = 2 * min(sa, sr) / (sa + sr) if sa + sr else float("nan")
    return out


# ----------------------------------------------------------------------------- results folder helpers
def _read_results(results, t1, t0=None):
    import rasterio
    d = pathlib.Path(results)
    with rasterio.open(d / f"built_up_{t1}.tif") as s:
        b1 = s.read(1); tr = s.transform; crs = s.crs
    valid = b1 != 255
    if t0 is None:
        return state_map(b1 == 1, valid), tr, crs, "state"
    with rasterio.open(d / f"built_up_{t0}.tif") as s:
        b0 = s.read(1)
    valid &= b0 != 255
    return change_map(b0 == 1, b1 == 1, valid), tr, crs, "change"


def export_sample(points, crs, path, kind):
    """Write the sample as GPKG (or CSV) with an empty 'ref' column for the interpreter."""
    import geopandas as gpd
    from shapely.geometry import Point
    g = gpd.GeoDataFrame(points, geometry=[Point(p["x"], p["y"]) for p in points], crs=crs)
    g["map_name"] = [CLASS_NAMES[kind][c] for c in g["map_class"]]
    g["ref"] = None
    g = g[["id", "map_class", "map_name", "ref", "row", "col", "x", "y", "geometry"]]
    path = pathlib.Path(path)
    if path.suffix.lower() == ".csv":
        g.drop(columns="geometry").to_csv(path, index=False)
    else:
        g.to_file(path, driver="GPKG", layer="sample")
    return g


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m landcoverrewind.accuracy", description=__doc__.split("\n")[0],
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("sample", "estimate"):
        s = sub.add_parser(name, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        s.add_argument("--results", required=True, help="results folder of a Land Cover Rewind run (built_up_<epoch>.tif)")
        s.add_argument("--t1", type=int, required=True, help="epoch of the state map, or end epoch of the change map")
        s.add_argument("--t0", type=int, default=None, help="start epoch of the change map (omit for a state map)")
    s = sub.choices["sample"]
    s.add_argument("--n", type=int, default=600, help="total number of sample pixels")
    s.add_argument("--min-n", type=int, default=100, help="minimum sample size per map class")
    s.add_argument("--seed", type=int, default=42)
    s.add_argument("--out", default="accuracy_sample.gpkg")
    e = sub.choices["estimate"]
    e.add_argument("--labels", required=True, help="the sample file with reference labels filled in")
    e.add_argument("--ref-field", default="ref", help="field with the reference class code")
    e.add_argument("--out", default="accuracy_estimate.json")
    a = ap.parse_args(argv)
    m, tr, crs, kind = _read_results(a.results, a.t1, a.t0)
    counts = class_counts(m)
    if a.cmd == "sample":
        n = allocate(counts, a.n, a.min_n)
        pts = draw_sample(m, tr, n, a.seed)
        export_sample(pts, crs, a.out, kind)
        print(f"{len(pts)} sample pixels written to {a.out}; allocation {n}; map pixels {counts}")
        return 0
    import geopandas as gpd, pandas as pd
    g = pd.read_csv(a.labels) if a.labels.lower().endswith(".csv") else gpd.read_file(a.labels)
    g = g[g[a.ref_field].notna()]
    if not len(g):
        raise SystemExit("error: no reference labels in the sample file")
    r = estimate(g["map_class"].astype(int), g[a.ref_field].astype(int), counts, abs(tr.a * tr.e))
    r.update(kind=kind, t0=a.t0, t1=a.t1, class_names=CLASS_NAMES[kind])
    pathlib.Path(a.out).write_text(json.dumps(r, indent=1, default=float))
    for j, c in r["classes_detail"].items():
        print(f"{CLASS_NAMES[kind].get(j, j)}: mapped {c['mapped_area_ha']:.1f} ha, adjusted {c['adjusted_area_ha']:.1f} ± {c['adjusted_area_ci95_ha']:.1f} ha, "
              f"UA {100 * c['users_accuracy']:.1f}%, PA {100 * c['producers_accuracy']:.1f}%")
    print(f"overall accuracy {100 * r['overall_accuracy']['value']:.1f} ± {100 * r['overall_accuracy']['ci95']:.1f}%; written to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
