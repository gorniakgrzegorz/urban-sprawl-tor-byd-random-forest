"""Sensitivity analysis v2 (all probabilities in float32, recomputed from the cached epoch features with
landcoverrewind 1.2.0): variants, two no-change baselines, block-bootstrap CIs for change metrics and paired
bootstrap of the F1 difference between the series and the no-change baseline."""
import sys, json, glob, numpy as np, joblib
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "aplikacja"))
from landcoverrewind import model, pipeline, __version__
from common import *
from sens import series_from

rf_pre, _ = model.load(pipeline.PRETRAINED[0])
NB = 300; rng0 = 42


def probs(rf, d):
    p = {}
    for f in glob.glob(str(d / "gotowy/cache/features_*_*.npy")):
        t = int(f.split("features_")[1][:4]); F = np.load(f).astype("float32")
        p[t] = model.predict(rf, F)[list(rf.classes_).index(1)]
    return p


def boot_stats(B, R, m, blocks, t0, t1, eps):
    """Per-block sufficient statistics so that every bootstrap replicate is a cheap weighted sum."""
    ids = blocks[m]; k = ids.max() + 1
    st = {}
    for t in eps:
        x, y = B[t][m], R[t][m]
        st[t] = (np.bincount(ids, x & y, k), np.bincount(ids, x & ~y, k), np.bincount(ids, ~x & y, k))
    nb, nr = (B[t1] & ~B[t0])[m], (R[t1] & ~R[t0])[m]
    st["chg"] = (np.bincount(ids, nb & nr, k), np.bincount(ids, nb & ~nr, k), np.bincount(ids, ~nb & nr, k))
    st["area"] = tuple(np.bincount(ids, X[t][m], k) for X in (B, R) for t in (t0, t1))
    return st, np.unique(ids)


def summarise(st, sel, eps):
    f = lambda a, b, c: 2 * a / (2 * a + b + c) if a else 0.0
    S = lambda arr: arr[sel].sum()
    epf = [f(*(S(v) for v in st[t])) for t in eps]
    pooled = f(sum(S(st[t][0]) for t in eps), sum(S(st[t][1]) for t in eps), sum(S(st[t][2]) for t in eps))
    b0, b1, r0, r1 = (S(a) for a in st["area"])
    gm, gr = 100 * (b1 / b0 - 1), 100 * (r1 / r0 - 1)
    return dict(mean_f1=float(np.mean(epf)), pooled_f1=float(pooled), f1_first=float(epf[0]), growth_map_pct=float(gm),
                growth_ref_pct=float(gr), growth_err_pp=float(gm - gr), new_map_ha=float((b1 - b0) * 0.09), new_ref_ha=float((r1 - r0) * 0.09),
                change_f1=float(f(*(S(v) for v in st["chg"]))))


def evaluate(B, R, m, blocks, boot=True):
    eps = [t for t in sorted(R) if t in B]; t0, t1 = (1990 if 1990 in eps else eps[0]), eps[-1]
    st, used = boot_stats(B, R, m, blocks, t0, t1, eps)
    out = summarise(st, used, eps); out["period"] = f"{t0}-{t1}"
    if boot:
        rng = np.random.default_rng(rng0); bs = [summarise(st, rng.choice(used, used.size), eps) for _ in range(NB)]
        for k in ("growth_err_pp", "change_f1", "mean_f1"):
            out[k + "_ci"] = [float(np.percentile([b[k] for b in bs], 2.5)), float(np.percentile([b[k] for b in bs], 97.5))]
    return out


rows, paired = [], []
for d in sorted(OUT.iterdir()):
    site = d.name
    if not (d / "gotowy.json").exists():
        continue
    s = load_site(site, "gotowy"); area = s["area"]; blocks = block_ids(s["shape"])
    p = probs(rf_pre, d)
    refs = {}
    wsf = wsf_on_grid(s); refs["WSF"] = ({t: (wsf > 0) & (wsf <= t) for t in EP if t <= 2015}, area)
    if site in SERIES_A:
        sa, valid = series_a_on_grid(site, s); refs["seriesA"] = (sa, area & valid)
    mk = np.load(d / "masks.npz"); thr = 5 / 9 - 1e-9
    masks = {"IO 2017|2024 >=5/9": s["M"], "IO 2017|2024 any": (mk["io2017"] > 0) | (mk["io2024"] > 0), "IO 2024 >=5/9": mk["io2024"] >= thr,
             "WorldCover 2021 >=5/9": mk["wc2021"] >= thr, "WorldCover 2021 any": mk["wc2021"] > 0, "none": None}
    variants = [("threshold", f"{t:.2f}", t, "IO 2017|2024 >=5/9", True) for t in (0.45, 0.55, 0.65, 0.75, 0.85)]
    variants += [("mask", k, 0.65, k, True) for k in masks if k != "IO 2017|2024 >=5/9"]
    variants += [("rule", "per-epoch (no accumulation)", 0.65, "IO 2017|2024 >=5/9", False)]
    Bdef = series_from(p, 0.65, s["M"])
    assert all(np.array_equal(Bdef[t], s["b"][t]) for t in Bdef), site + ": recomputed series differs from the pipeline output"
    rfl = joblib.load(d / "lokalny" / "local_model_binary.joblib")
    Bloc = series_from(probs(rfl, d), 0.65, s["M"])
    for rname, (R, m) in refs.items():
        for fam, lab, tau, mkey, mono in variants:
            rows.append(dict(site=site, reference=rname, family=fam, variant=lab, **evaluate(series_from(p, tau, masks[mkey], mono), R, m, blocks)))
        rows.append(dict(site=site, reference=rname, family="mode", variant="local", **evaluate(Bloc, R, m, blocks)))
        rows.append(dict(site=site, reference=rname, family="baseline", variant="no change: extent mask M", **evaluate({t: s["M"] for t in R}, R, m, blocks)))
        last = max(R) if max(R) in Bdef else 2025
        rows.append(dict(site=site, reference=rname, family="baseline", variant="no change: series state of last epoch", **evaluate({t: Bdef[last] for t in R}, R, m, blocks)))
        # paired bootstrap of F1(series) - F1(no change M) per epoch
        ids = blocks[m]; k = ids.max() + 1; used = np.unique(ids); rng = np.random.default_rng(rng0)
        samp = [rng.choice(used, used.size) for _ in range(NB)]
        for t in sorted(R):
            def cnt(X):
                x, y = X[m], R[t][m]
                return np.bincount(ids, x & y, k), np.bincount(ids, x & ~y, k), np.bincount(ids, ~x & y, k)
            a, b = cnt(Bdef[t]), cnt(s["M"])
            f = lambda c, sel: 2 * c[0][sel].sum() / (2 * c[0][sel].sum() + c[1][sel].sum() + c[2][sel].sum())
            dl = [f(a, sl) - f(b, sl) for sl in samp]
            paired.append(dict(site=site, reference=rname, epoch=t, d_f1=float(f(a, used) - f(b, used)),
                               ci=[float(np.percentile(dl, 2.5)), float(np.percentile(dl, 97.5))]))
    print(site, "ok", flush=True)
json.dump(dict(version=__version__, rows=rows, paired=paired), open("sensitivity2.json", "w"), indent=0)
