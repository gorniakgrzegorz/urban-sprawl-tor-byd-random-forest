"""A4: feature ablation. Binary models are retrained on the Torun/Bydgoszcz 2025 labels with feature subsets,
applied to the cached epoch features of every site, constrained (mask M, threshold 0.65, accumulation) and evaluated."""
import sys, json, glob, numpy as np, rasterio
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "aplikacja"))
from landcoverrewind import model
from common import *
from sens import series_from, evaluate

C = str(ROOT.parent / "aplikacja" / "training_cache") + "/"
D = []
for pre in ("tor", "byd"):
    F = np.load(C + f"{pre}_v3_rf_4kl_2025_features2025.npy")
    with rasterio.open(str(DATA / "series_A" / f"{pre}_v3_rf_4kl_2025.tif")) as s:
        lab = s.read(1)
    lab = np.where(lab == 0, 255, lab)
    D.append((F, np.where(lab == 255, 255, (lab == 1).astype("uint8"))))
SETS = {"all 18 (default)": list(range(18)), "no GLCM texture": [i for i in range(18) if i not in (12, 13)],
        "no spring features": list(range(14)), "18 + NDVI amplitude": list(range(19)),
        "summer bands + indices only": list(range(12))}
models = {}
for name, idx in SETS.items():
    Xs, ys = [], []
    for k, (F, lab) in enumerate(D):
        X, y = model.sample_points(lab, F, per_class=750, seed=42 + k)
        Xs.append(X[:, idx]); ys.append(y)
    from sklearn.ensemble import RandomForestClassifier
    rf = RandomForestClassifier(n_estimators=300, max_features=4, min_samples_leaf=1, n_jobs=-1, random_state=42, oob_score=True)
    rf.fit(np.vstack(Xs), np.concatenate(ys)); models[name] = (rf, idx)
    print(name, "OOB", round(rf.oob_score_, 4), flush=True)

rows = []
for d in sorted(OUT.iterdir()):
    site = d.name
    if not (d / "gotowy.json").exists():
        continue
    s = load_site(site, "gotowy"); area = s["area"]
    refs = {"WSF": ({t: (wsf > 0) & (wsf <= t) for t in EP if t <= 2015} if (wsf := wsf_on_grid(s)) is not None else None, area)}
    if site in SERIES_A:
        sa, valid = series_a_on_grid(site, s); refs["seriesA"] = (sa, area & valid)
    feats = {}
    for f in glob.glob(str(d / "gotowy/cache/features_*_*.npy")):
        t = int(f.split("features_")[1][:4]); feats[t] = f
    for name, (rf, idx) in models.items():
        p = {}
        for t in sorted(feats):
            F = np.load(feats[t]); C_, H, W = F.shape
            X = F.reshape(C_, -1).T[:, idx]; ok = np.all(np.isfinite(X), axis=1)
            pr = np.full(X.shape[0], np.nan, "float32"); pr[ok] = rf.predict_proba(X[ok])[:, list(rf.classes_).index(1)]
            p[t] = pr.reshape(H, W)
        B = series_from(p, 0.65, s["M"])
        for rname, (R, m) in refs.items():
            rows.append(dict(site=site, reference=rname, family="features", variant=name, oob=float(rf.oob_score_), **evaluate(B, R, m)))
    print(site, "ok", flush=True)
json.dump(rows, open("ablation.json", "w"), indent=0)
