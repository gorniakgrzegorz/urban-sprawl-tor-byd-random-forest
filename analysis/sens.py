"""A4/A6: sensitivity of the series to the pipeline choices (threshold, extent mask, monotonic rule, mode).

For every variant and reference (WSF Evolution 1985-2015 for all sites, series A 1985-2025 for Torun and Bydgoszcz):
mean F1 over epochs, F1 of the first epoch, built-up growth between 1990 and the last reference epoch (map and
reference), and F1 of the new built-up land of that period (change agreement).
"""
import json, numpy as np
from common import *


def series_from(p, tau, M, monotonic=True):
    out, acc = {}, None
    for t in sorted(p):
        r = np.nan_to_num(p[t], nan=0) >= tau
        acc = r if (acc is None or not monotonic) else (acc | r)
        out[t] = acc & M if M is not None else acc.copy()
    return out


def f1(x, y, m):
    tp, fp, fn, tn = confusion(x, y, m)
    return 2 * tp / (2 * tp + fp + fn) if tp else 0.0


def evaluate(B, R, m):
    ep = [t for t in sorted(R) if t in B]
    t0, t1 = (1990 if 1990 in ep else ep[0]), ep[-1]
    a = lambda X, t: X[t][m].sum() * 0.09
    newB, newR = B[t1] & ~B[t0], R[t1] & ~R[t0]
    return dict(mean_f1=float(np.mean([f1(B[t], R[t], m) for t in ep])), f1_first=float(f1(B[ep[0]], R[ep[0]], m)),
                growth_map_pct=float(100 * (a(B, t1) / a(B, t0) - 1)), growth_ref_pct=float(100 * (a(R, t1) / a(R, t0) - 1)),
                change_f1=float(f1(newB, newR, m)), area_first_map_ha=float(a(B, ep[0])), area_first_ref_ha=float(a(R, ep[0])),
                period=f"{t0}-{t1}")


def main():
    rows = []
    for d in sorted(OUT.iterdir()):
        site = d.name
        if not (d / "gotowy.json").exists():
            continue
        s = load_site(site, "gotowy"); area = s["area"]
        refs = {}
        wsf = wsf_on_grid(s)
        refs["WSF"] = ({t: (wsf > 0) & (wsf <= t) for t in EP if t <= 2015}, area)
        if site in SERIES_A:
            sa, valid = series_a_on_grid(site, s)
            refs["seriesA"] = (sa, area & valid)
        mk = np.load(d / "masks.npz") if (d / "masks.npz").exists() else None
        masks = {"IO 2017|2024 >=5/9": s["M"], "none": None}
        if mk is not None:
            thr = 5 / 9 - 1e-9
            masks.update({"IO 2017|2024 any": (mk["io2017"] > 0) | (mk["io2024"] > 0), "IO 2024 >=5/9": mk["io2024"] >= thr,
                          "WorldCover 2021 >=5/9": mk["wc2021"] >= thr, "WorldCover 2021 any": mk["wc2021"] > 0})
            assert np.array_equal(masks["IO 2017|2024 >=5/9"], (mk["io2017"] >= thr) | (mk["io2024"] >= thr)), site
        if site in SERIES_A:
            masks["oracle: series A 2025"] = sa[2025]
        variants = [("threshold", f"{tau:.2f}", tau, "IO 2017|2024 >=5/9", True) for tau in (0.45, 0.55, 0.65, 0.75, 0.85)]
        variants += [("mask", k, 0.65, k, True) for k in masks if k != "IO 2017|2024 >=5/9"]
        variants += [("rule", "per-epoch (no accumulation)", 0.65, "IO 2017|2024 >=5/9", False)]
        for rname, (R, m) in refs.items():
            for fam, label, tau, mkey, mono in variants:
                B = series_from(s["p"], tau, masks[mkey], mono)
                rows.append(dict(site=site, reference=rname, family=fam, variant=label, **evaluate(B, R, m)))
            st = {t: s["M"] for t in R}
            rows.append(dict(site=site, reference=rname, family="baseline", variant="static (mask M in every epoch)", **evaluate(st, R, m)))
            if (d / "lokalny.json").exists():
                sl = load_site(site, "lokalny")
                rows.append(dict(site=site, reference=rname, family="mode", variant="local", **evaluate(sl["b"], R, m)))
        print(site, "ok", flush=True)
    json.dump(rows, open("sensitivity.json", "w"), indent=0)


if __name__ == "__main__":
    main()
