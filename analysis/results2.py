"""Numbers, tables and figures of manuscript v3 (sensitivity2.json, series_eval.json, ablation.json)."""
import json, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from common import OUT
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent
F = str(ROOT / "figures") + "/"; pathlib.Path(F).mkdir(exist_ok=True)
NAME = {"torun": "Toruń", "bydgoszcz": "Bydgoszcz", "olsztyn": "Olsztyn", "opole": "Opole", "rzeszow": "Rzeszów", "zielona_gora": "Zielona Góra", "brno": "Brno"}
ORDER = ["torun", "bydgoszcz", "olsztyn", "opole", "rzeszow", "zielona_gora", "brno"]; OUTS = ORDER[2:]
CB = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#000000"]; MK = ["o", "s", "D", "^", "v", "P", "X"]
plt.rcParams.update({"font.size": 8, "font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})
S2 = json.load(open("sensitivity2.json")); R = S2["rows"]; P = S2["paired"]; E = json.load(open("series_eval.json")); A = json.load(open("ablation.json"))
W = lambda fam, var: {r["site"]: r for r in R if r["reference"] == "WSF" and r["family"] == fam and r["variant"] == var}
out = {"version": S2["version"]}


def agg(rr):
    e = [r["growth_err_pp"] for r in rr]
    g = [r["growth_map_pct"] for r in rr]
    return dict(n=len(rr), mean_f1=100 * np.mean([r["mean_f1"] for r in rr]), pooled_f1=100 * np.mean([r["pooled_f1"] for r in rr]),
                f1_first=100 * np.mean([r["f1_first"] for r in rr]), change_f1=100 * np.mean([r["change_f1"] for r in rr]),
                median_growth_err=float(np.median(e)), mae_growth=float(np.mean(np.abs(e))),
                rho=float(spearmanr(g, [r["growth_ref_pct"] for r in rr]).statistic) if len(set(g)) > 1 else None,
                rho_p=float(spearmanr(g, [r["growth_ref_pct"] for r in rr]).pvalue) if len(set(g)) > 1 else None)


VAR = [("threshold", "0.65", "default"), ("threshold", "0.45", "τ = 0.45"), ("threshold", "0.55", "τ = 0.55"), ("threshold", "0.75", "τ = 0.75"), ("threshold", "0.85", "τ = 0.85"),
       ("mask", "IO 2017|2024 any", "mask: IO any 10 m cell"), ("mask", "IO 2024 >=5/9", "mask: IO 2023 only"), ("mask", "WorldCover 2021 >=5/9", "mask: WorldCover ≥ 5/9"),
       ("mask", "WorldCover 2021 any", "mask: WorldCover any cell"), ("mask", "none", "no extent mask"), ("rule", "per-epoch (no accumulation)", "no accumulation"),
       ("mode", "local", "local model (IO LULC 2023)")]
FV = [("no GLCM texture", "features: no GLCM"), ("no spring features", "features: no spring"), ("18 + NDVI amplitude", "features: + NDVI amplitude"), ("summer bands + indices only", "features: summer only")]
NULL = [("baseline", "no change: extent mask M", "no change: mask M"), ("baseline", "no change: series state of last epoch", "no change: series 2015 state")]
tab, rowsets = [], []
for fam, v, lab in VAR + NULL:
    rr = [r for r in R if r["reference"] == "WSF" and r["family"] == fam and r["variant"] == v]
    rowsets.append((lab, rr))
for j, (v, lab) in enumerate(FV):
    rr = []
    for r in A:
        if r["reference"] == "WSF" and r["variant"] == v:
            q = dict(r); q["growth_err_pp"] = r["growth_map_pct"] - r["growth_ref_pct"]; q["pooled_f1"] = r["mean_f1"]; rr.append(q)
    rowsets.insert(len(VAR) + j, (lab, rr))
for lab, rr in rowsets:
    t = dict(variant=lab, **agg(rr)); t["out5"] = agg([r for r in rr if r["site"] in OUTS]); t["no_rzeszow"] = agg([r for r in rr if r["site"] != "rzeszow"]); tab.append(t)
out["variants"] = tab
abl18 = [r for r in A if r["reference"] == "WSF" and r["variant"].startswith("all 18")]
out["ablation_18_check"] = dict(mean_f1=100 * np.mean([r["mean_f1"] for r in abl18]), oob={r["variant"]: r["oob"] for r in A if r["site"] == "torun" and r["reference"] == "WSF"})
nm = [t for t in tab if not t["variant"].startswith("no change")]
out["corr_meanf1_mae"] = float(np.corrcoef([t["mean_f1"] for t in nm], [t["mae_growth"] for t in nm])[0, 1])
w = [p for p in P if p["reference"] == "WSF"]
out["paired_wsf"] = dict(n=len(w), series_better=sum(p["ci"][0] > 0 for p in w), static_better=sum(p["ci"][1] < 0 for p in w),
                         ns=sum(p["ci"][0] <= 0 <= p["ci"][1] for p in w), static_better_sites=sorted({p["site"] for p in w if p["ci"][1] < 0}),
                         mean_d=100 * np.mean([p["d_f1"] for p in w]))
sa = [p for p in P if p["reference"] == "seriesA"]
out["paired_seriesA"] = dict(n=len(sa), series_better=sum(p["ci"][0] > 0 for p in sa))
d = W("threshold", "0.65")
out["default_sites"] = {s: dict(growth_map=d[s]["growth_map_pct"], growth_ref=d[s]["growth_ref_pct"], err=d[s]["growth_err_pp"], err_ci=d[s]["growth_err_pp_ci"],
                                change_f1=d[s]["change_f1"], change_f1_ci=d[s]["change_f1_ci"], new_map_ha=d[s]["new_map_ha"], new_ref_ha=d[s]["new_ref_ha"]) for s in ORDER}
th = {t: W("threshold", t) for t in ("0.45", "0.55", "0.65", "0.75", "0.85")}
out["growth_by_threshold"] = {s: {t: th[t][s]["growth_map_pct"] for t in th} for s in ORDER}
sA = {r["site"]: r for r in R if r["reference"] == "seriesA" and r["family"] == "threshold" and r["variant"] == "0.65"}
out["seriesA_growth"] = {s: dict(map=sA[s]["growth_map_pct"], ref=sA[s]["growth_ref_pct"], period=sA[s]["period"]) for s in sA}

# ---------------- Figure 2
fig, ax = plt.subplots(1, 2, figsize=(7.2, 3.6))
for i, s in enumerate(ORDER):
    for prod, ls in (("app", "-"), ("static", ":")):
        r = sorted([e for e in E if e["site"] == s and e["mode"] == "gotowy" and e["reference"] == "WSF" and e["product"] == prod], key=lambda e: e["epoch"])
        ax[0].plot([e["epoch"] for e in r], [100 * e["f1"] for e in r], ls, color=CB[i], lw=1.2, marker=MK[i] if prod == "app" else None, ms=3, label=NAME[s] if prod == "app" else None)
ax[0].plot([], [], "-", color="0.55", label="series (τ = 0.65)"); ax[0].plot([], [], ":", color="0.55", label="no-change baseline (mask M)")
ax[0].set_xlabel("Epoch"); ax[0].set_ylabel("F1 against WSF Evolution [%]"); ax[0].set_ylim(25, 95)
ax[0].legend(fontsize=5.8, ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2))
loc = W("mode", "local"); OFF = {"torun": (7, 1), "brno": (-6, 2), "bydgoszcz": (-6, -3), "olsztyn": (6, -8), "opole": (6, -3), "rzeszow": (-6, 6), "zielona_gora": (-6, -3)}
for i, s in enumerate(ORDER):
    ax[1].scatter(d[s]["growth_ref_pct"], d[s]["growth_map_pct"], color=CB[i], marker=MK[i], s=24, zorder=3)
    ax[1].scatter(loc[s]["growth_ref_pct"], loc[s]["growth_map_pct"], edgecolor=CB[i], facecolor="white", marker=MK[i], s=24, zorder=2)
    ax[1].plot([d[s]["growth_ref_pct"]] * 2, [loc[s]["growth_map_pct"], d[s]["growth_map_pct"]], color=CB[i], lw=0.5, zorder=1)
    if s == "zielona_gora":  # crowded part of the panel: label with a leader line
        ax[1].annotate(NAME[s], (d[s]["growth_ref_pct"], d[s]["growth_map_pct"]), xytext=(50, 60), textcoords="data", fontsize=6,
                       ha="left", arrowprops=dict(arrowstyle="-", color="0.4", lw=0.5))
    else:
        ax[1].annotate(NAME[s], (d[s]["growth_ref_pct"], d[s]["growth_map_pct"]), xytext=OFF[s], textcoords="offset points", fontsize=6, ha="right" if s in ("brno", "rzeszow", "bydgoszcz") else "left")
ax[1].plot([0, 125], [0, 125], color="0.6", lw=0.8); ax[1].set_xlim(0, 125); ax[1].set_ylim(0, 125)
ax[1].set_xlabel("Built-up growth 1990–2015, WSF Evolution [%]"); ax[1].set_ylabel("Built-up growth 1990–2015, series [%]")
ax[1].scatter([], [], color="0.3", s=18, label="pretrained model (filled)"); ax[1].scatter([], [], facecolor="white", edgecolor="0.3", s=18, label="local model (open)")
ax[1].legend(fontsize=6, frameon=False, loc="upper left")
for a, t, x in zip(ax, "ab", (-0.17, -0.2)):
    a.text(x, 1.04, f"({t})", transform=a.transAxes, fontsize=9, fontweight="bold")
fig.tight_layout(); [fig.savefig(F + "Figure_2." + e, dpi=300) for e in ("png", "pdf", "svg")]; plt.close(fig)

# ---------------- Figure 3
fig, ax = plt.subplots(1, 2, figsize=(7.2, 3.3), gridspec_kw={"width_ratios": [1, 1.3]})
TH = ["0.45", "0.55", "0.65", "0.75", "0.85"]
for i, s in enumerate(ORDER):
    ax[0].plot([float(t) for t in TH], [out["growth_by_threshold"][s][t] for t in TH], "-", marker=MK[i], color=CB[i], ms=3.5, lw=1.1, label=NAME[s])
    ax[0].plot(0.895 + 0.009 * i, d[s]["growth_ref_pct"], marker=MK[i], color=CB[i], ms=4, ls="", clip_on=False)
ax[0].set_xlabel("Probability threshold τ"); ax[0].set_ylabel("Built-up growth 1990–2015 [%]"); ax[0].set_xlim(0.42, 0.95); ax[0].set_xticks([0.45, 0.55, 0.65, 0.75, 0.85])
ax[0].legend(fontsize=6, frameon=False, ncol=2, loc="upper left"); ax[0].annotate("WSF\nEvolution", (0.917, 112), fontsize=5.5, ha="center")
lab_order = [t["variant"] for t in tab]
for k, (lab, rr) in enumerate(rowsets):
    err = [r["growth_err_pp"] for r in rr]
    for r in rr:
        i = ORDER.index(r["site"]); ax[1].scatter(r["growth_err_pp"], k, s=11, marker=MK[i], color=CB[i], zorder=2)
    ax[1].plot([np.median(err)] * 2, [k - 0.4, k + 0.4], color="k", lw=2, zorder=4)
ax[1].axvline(0, color="0.6", lw=0.8); ax[1].set_yticks(range(len(rowsets))); ax[1].set_yticklabels(lab_order, fontsize=6.3); ax[1].invert_yaxis()
ax[1].set_xlabel("Growth difference, series minus WSF Evolution [pp]")
ax[0].text(-0.17, 1.03, "(a)", transform=ax[0].transAxes, fontsize=9, fontweight="bold"); ax[1].text(-0.55, 1.03, "(b)", transform=ax[1].transAxes, fontsize=9, fontweight="bold")
fig.tight_layout(); [fig.savefig(F + "Figure_3." + e, dpi=300) for e in ("png", "pdf", "svg")]; plt.close(fig)

# ---------------- sites, runtime, Figure 4
sites = []
for s in ORDER:
    md = json.load(open(OUT / s / "gotowy" / "metadane.json")); ml = json.load(open(OUT / s / "lokalny.json"))
    sites.append(dict(key=s, site=NAME[s], km2=md["obszar_km2"], crs=md["crs"], scenes=sum(len(v) for v in md["sceny"].values()), runtime_s=md["czas_s"],
                      local_extra_s=ml.get("czas_s"), growth_wsf=d[s]["growth_ref_pct"]))
out["sites"] = sites
fig, ax = plt.subplots(figsize=(4.6, 2.6))
for i, x in enumerate(sites):
    ax.scatter(x["km2"], x["runtime_s"] / 60, color=CB[i], marker=MK[i], s=24, label=x["site"])
A6 = json.load(open(ROOT / "a6.json"))
xs = [x["km2"] for x in sites] + [9.1]; ys = [x["runtime_s"] for x in sites] + [A6["c70a"]["time_s"]]
ax.scatter(9.1, A6["c70a"]["time_s"] / 60, color="0.5", marker="o", s=18, facecolor="white", label="Toruń centre, 9.1 km²")
b1, b0 = np.polyfit(xs, ys, 1); xx = np.array([0, 200]); ax.plot(xx, (b0 + b1 * xx) / 60, color="0.4", lw=0.8, ls="--", label=f"fit: {b0/60:.1f} min + {b1:.1f} s/km²")
out["runtime_fit"] = dict(intercept_s=b0, slope_s_per_km2=b1, n=len(xs))
ax.set_xlabel("Area [km²]"); ax.set_ylabel("Run time, 9 epochs [min]"); ax.set_xlim(0, 200); ax.set_ylim(0, 15); ax.legend(fontsize=7, frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1.0), ncol=1)
fig.tight_layout(); [fig.savefig(F + "Figure_4." + e, dpi=300) for e in ("png", "pdf", "svg")]; plt.close(fig)
xs = np.array([x["km2"] for x in sites]); ys = np.array([x["runtime_s"] for x in sites])
out["runtime_slope_s_per_km2_origin"] = float(np.sum(xs * ys) / np.sum(xs * xs)); out["runtime_scenes_corr"] = float(np.corrcoef([x["scenes"] for x in sites], ys)[0, 1])
json.dump(out, open(str(ROOT / "results.json"), "w"), indent=1, ensure_ascii=False, default=float)
for t in tab:
    print(f'{t["variant"][:30]:30} F1 {t["mean_f1"]:.1f} pooled {t["pooled_f1"]:.1f} first {t["f1_first"]:.1f} ch {t["change_f1"]:.1f} med {t["median_growth_err"]:.1f} MAE {t["mae_growth"]:.1f} | out5 {t["out5"]["mean_f1"]:.1f}/{t["out5"]["mae_growth"]:.1f} noR {t["no_rzeszow"]["mae_growth"]:.1f} rho {t["rho"]} p {t["rho_p"]}')
print({k: v for k, v in out.items() if k in ("paired_wsf", "paired_seriesA", "corr_meanf1_mae", "ablation_18_check", "seriesA_growth")})
