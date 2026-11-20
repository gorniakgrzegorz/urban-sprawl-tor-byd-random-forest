"""A8 and A2/A3: per-epoch agreement of the app series with series A (Torun, Bydgoszcz) and WSF Evolution (all sites).

For every site, mode and epoch: confusion matrix, OA, PA, UA, F1 of built-up land with 95% block-bootstrap CIs,
and the same scores for the static baseline (the present-day extent mask M assigned to every epoch).
"""
import sys, json, numpy as np
from common import *

rows = []
sites = [d.name for d in OUT.iterdir() if d.is_dir()]
for site in sorted(sites):
    for mode in ("gotowy", "lokalny"):
        if not (OUT / site / f"{mode}.json").exists():
            continue
        s = load_site(site, mode); area = s["area"]; blocks = block_ids(s["shape"])
        refs = {}
        wsf = wsf_on_grid(s)
        refs["WSF"] = {t: (wsf > 0) & (wsf <= t) for t in EP if t <= 2015}
        if site in SERIES_A:
            sa, valid = series_a_on_grid(site, s)
            refs["seriesA"] = sa
        for rname, R in refs.items():
            m = area if rname == "WSF" else area & valid
            for t, y in R.items():
                for prod, x in (("app", s["b"].get(t)), ("static", s["M"])):
                    if x is None:
                        continue
                    c = confusion(x, y, m)
                    r = dict(site=site, mode=mode, reference=rname, epoch=t, product=prod, tp=int(c[0]), fp=int(c[1]), fn=int(c[2]), tn=int(c[3]), **scores(*c))
                    r["ci"] = boot_ci(x, y, m, blocks, n=500)
                    rows.append(r)
            print(site, mode, rname, "ok", flush=True)
json.dump(rows, open("series_eval.json", "w"), indent=0, default=float)
