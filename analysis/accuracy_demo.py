"""Demonstration of landcoverrewind.accuracy (version 1.4.0) on the six Polish sites: error-adjusted built-up area of
the 2025 epoch from a stratified random sample whose reference labels are read from BDOT10k (built-up, transport
areas and squares, >= 5 of 9 10 m sub-pixels; the main reference of the manuscript). Rules fixed before computing:
sample of 600 pixels per site, at least 100 per map class, seed 42, evaluated pixels = site area covered by BDOT10k.
Because BDOT10k covers every pixel, the census reference area is known and the estimate can be checked against it;
the sample is repeated with 200 seeds to report the empirical coverage of the 95% confidence interval."""
import sys, json, glob, numpy as np
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "aplikacja"))
from landcoverrewind import accuracy as A
from common import *
from bdot_ref import COUNTIES, read, frac, RAW  # reference construction of bdot_eval.py

rows = []
for site in COUNTIES:
    s = load_site(site, "gotowy"); H, W = s["shape"]
    x0, y0 = s["tr"].c, s["tr"].f; bbox = (x0, y0 - 30 * H, x0 + 30 * W, y0)
    lay = {L: read(site, L, bbox, s["crs"]) for L in ("PTZB", "PTKM", "PTPL")}
    cov = np.zeros((H, W), "float32")
    allpt = set(f.split("__OT_")[1][:4] for c in COUNTIES[site] for f in glob.glob(str(RAW / c / "*__OT_PT*_A.shp")))
    for L in sorted(allpt):
        cov += frac(list((lay[L] if L in lay else read(site, L, bbox, s["crs"])).geometry), s)
    valid = s["area"] & (cov >= 5 / 9 - 1e-9)
    fzp = np.clip(sum(frac(list(lay[L].geometry), s) for L in ("PTZB", "PTKM", "PTPL")), 0, 1)
    ref = fzp >= 5 / 9 - 1e-9
    m = A.state_map(s["b"][2025], valid); counts = A.class_counts(m)
    n = A.allocate(counts, 600, 100)
    def run(seed):
        pts = A.draw_sample(m, s["tr"], n, seed)
        return A.estimate([p["map_class"] for p in pts], [int(ref[p["row"], p["col"]]) for p in pts], counts, 900.0)
    e = run(42); c = e["classes_detail"][1]
    true_ha = float(ref[valid].sum() * 0.09)
    cover = 0; ests = []
    for sd in range(200):
        x = run(1000 + sd)["classes_detail"][1]; ests.append(x["adjusted_area_ha"])
        cover += abs(x["adjusted_area_ha"] - true_ha) <= x["adjusted_area_ci95_ha"]
    rows.append(dict(site=site, n=n, mapped_ha=c["mapped_area_ha"], adjusted_ha=c["adjusted_area_ha"], ci95_ha=c["adjusted_area_ci95_ha"],
                     ua=c["users_accuracy"], ua_ci95=c["users_accuracy_ci95"], pa=c["producers_accuracy"], pa_ci95=c["producers_accuracy_ci95"],
                     oa=e["overall_accuracy"]["value"], oa_ci95=e["overall_accuracy"]["ci95"], bdot_census_ha=true_ha,
                     ratio_mapped=c["mapped_area_ha"] / true_ha, ratio_adjusted=c["adjusted_area_ha"] / true_ha,
                     coverage_200_seeds=cover / 200, mean_adjusted_200_seeds=float(np.mean(ests))))
    print(site, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in rows[-1].items()}, flush=True)
json.dump(dict(rows=rows, rules=__doc__), open("accuracy_demo.json", "w"), indent=1)
