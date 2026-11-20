"""PNG maps, GIF animations and the area chart. Labels are available in English and Polish."""
from __future__ import annotations
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

COLORS_4 = {1: "#67000d", 2: "#4daf4a", 3: "#3182bd", 4: "#fee8a6"}
TEXT = {
    "en": dict(classes={1: "built-up", 2: "trees and forest", 3: "water", 4: "other (grass, crops, bare soil)"},
               built="built-up", not_built="not built-up", ha="built-up", year="Year (epoch)",
               area="Built-up area [ha]", legend="Period in which built-up land first appears (30 m pixel)"),
    "pl": dict(classes={1: "zabudowa", 2: "lasy i drzewa", 3: "wody", 4: "pozostałe (trawy, uprawy, odsłonięta gleba)"},
               built="zabudowa", not_built="brak zabudowy", ha="zabudowa", year="Rok (epoka)",
               area="Powierzchnia zabudowy [ha]", legend="Okres, w którym zabudowa pojawiła się po raz pierwszy (piksel 30 m)"),
}


def first_detection_map(fd, area, epochs, path, lang="en"):
    L = TEXT[lang]
    cmap = plt.get_cmap("viridis", len(epochs))
    rgba = np.ones(fd.shape + (4,)); rgba[..., :3] = 0.93
    rgba[~area] = (1, 1, 1, 1)
    for i, t in enumerate(epochs):
        rgba[fd == t] = cmap(i)
    fig, ax = plt.subplots(figsize=(7, 7 * fd.shape[0] / fd.shape[1] + 1.2))
    ax.imshow(rgba, interpolation="nearest"); ax.set_axis_off()
    labels = [f"≤ {epochs[0]}"] + [f"{a + 1}–{b}" for a, b in zip(epochs[:-1], epochs[1:])]
    fig.legend(handles=[Patch(fc=cmap(i), label=s) for i, s in enumerate(labels)], loc="lower center",
               ncol=min(5, len(labels)), fontsize=7, title=L["legend"], title_fontsize=8)
    fig.subplots_adjust(bottom=0.16, top=0.94, left=0.02, right=0.98)
    fig.savefig(path, dpi=200); plt.close(fig)


def frame(B_t, area, k4=None):
    rgba = np.ones(B_t.shape + (4,))
    if k4 is not None:
        for k, c in COLORS_4.items():
            rgba[k4 == k, :3] = matplotlib.colors.to_rgb(c)
    else:
        rgba[..., :3] = 0.93
        rgba[B_t] = (0.40, 0.0, 0.05, 1)
    rgba[~area] = (1, 1, 1, 1)
    return rgba


def animation(B, area, path, k4=None, ms=900, lang="en"):
    from PIL import Image
    L = TEXT[lang]; frames = []
    for t in sorted(B):
        fig, ax = plt.subplots(figsize=(6, 6 * B[t].shape[0] / B[t].shape[1] + 0.6), dpi=110)
        ax.imshow(frame(B[t], area, None if k4 is None else k4[t]), interpolation="nearest")
        ax.set_axis_off()
        if k4 is None:
            leg = [Patch(fc="#660d0d", label=L["built"]), Patch(fc="#ededed", ec="#999", label=L["not_built"])]
        else:
            leg = [Patch(fc=COLORS_4[k], label=L["classes"][k]) for k in COLORS_4]
        ax.legend(handles=leg, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=2, fontsize=8, frameon=False)
        ax.set_title(f"{t}   {L['ha']}: {B[t][area].sum() * 0.09:,.0f} ha".replace(",", " "), loc="left",
                     fontsize=11, fontweight="bold")
        fig.tight_layout(); fig.canvas.draw()
        frames.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3])); plt.close(fig)
    frames[0].save(path, save_all=True, append_images=frames[1:] + [frames[-1]] * 2, duration=ms, loop=0)


def area_chart(table, path, lang="en"):
    L = TEXT[lang]
    ep = [r["epoch"] for r in table]; ha = [r["built_up_ha"] for r in table]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.plot(ep, ha, "o-", color="#67000d")
    ax.set_xlabel(L["year"]); ax.set_ylabel(L["area"]); ax.grid(alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(path, dpi=200); plt.close(fig)


SDG_TEXT = {
    "en": dict(cls=["< 0 (built-up grows, population falls)", "0–1 (population grows faster)", "1–2 (built-up grows faster)",
                    "> 2 (built-up grows much faster)", "population falls, no built-up growth",
                    "not interpretable (stable or small population, no data)", "cell partly outside the area"],
               x="Population growth rate PGR [%/year]", y="Land consumption rate LCR [%/year]", one="LCRPGR = 1"),
    "pl": dict(cls=["< 0 (zabudowa rośnie, ludność maleje)", "0–1 (ludność rośnie szybciej)", "1–2 (zabudowa rośnie szybciej)",
                    "> 2 (zabudowa rośnie znacznie szybciej)", "ludność maleje, zabudowa nie rośnie",
                    "nieinterpretowalny (ludność stała lub mała, brak danych)", "komórka częściowo poza obszarem"],
               x="Tempo wzrostu ludności PGR [%/rok]", y="Tempo zużycia terenu LCR [%/rok]", one="LCRPGR = 1"),
}
SDG_COLORS = ["#7b3294", "#018571", "#fdae61", "#d7191c", "#92c5de", "#bdbdbd", "#f7f7f7"]


def sdg_classes(c):
    """Class index of every cell (order of SDG_COLORS)."""
    cls = np.full(len(c), 5)
    lcr, pgr = c.lcr.values, c.pgr.values
    ok = c.status.isin(["ok", "population decline"]).values
    dec = ok & (pgr < 0)
    cls[dec & (lcr > 0)] = 0
    cls[dec & ~(lcr > 0)] = 4
    gro = ok & (pgr > 0)
    r = np.where(gro, lcr / np.where(pgr == 0, np.nan, pgr), np.nan)
    cls[gro & (r < 1)] = 1; cls[gro & (r >= 1) & (r < 2)] = 2; cls[gro & (r >= 2)] = 3
    cls[(c.status == "cell not fully inside the area").values] = 6
    return cls


def sdg_figure(cells, area_outline, path, lang="en"):
    """Map of cell LCRPGR classes and a phase diagram of LCR against PGR."""
    L = SDG_TEXT[lang]
    c = cells.copy(); c["cls"] = sdg_classes(c)
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 5.8), gridspec_kw=dict(width_ratios=[1.15, 1]))
    for i, col in enumerate(SDG_COLORS):
        sub = c[c.cls == i]
        if len(sub):
            sub.plot(ax=a, color=col, edgecolor="#9e9e9e" if i == 6 else "white", linewidth=0.3)
    if area_outline is not None:
        area_outline.boundary.plot(ax=a, color="black", linewidth=0.8)
    a.set_axis_off()
    present = sorted(set(c.cls))
    a.legend(handles=[Patch(fc=SDG_COLORS[i], ec="#9e9e9e", label=L["cls"][i]) for i in present], loc="upper center",
             bbox_to_anchor=(0.5, -0.02), ncol=1, fontsize=7.5, frameon=False)
    full = c[c.cls < 6].dropna(subset=["pgr", "lcr"])
    b.axhline(0, color="#999", lw=0.6); b.axvline(0, color="#999", lw=0.6)
    lim = max(0.5, float(np.nanpercentile(np.abs(np.r_[full.pgr.values, full.lcr.values]) * 100, 95))) if len(full) else 1
    xx = np.linspace(0, lim, 10); b.plot(xx, xx, ls="--", color="#555", lw=0.8, label=L["one"])
    b.scatter(full.pgr * 100, full.lcr * 100, s=12, c=[SDG_COLORS[k] for k in full.cls], edgecolor="none")
    b.set_xlim(-lim, lim); b.set_ylim(-lim * 0.2, lim)
    b.set_xlabel(L["x"]); b.set_ylabel(L["y"]); b.legend(loc="upper left", fontsize=8, frameon=False)
    for s_ in ("top", "right"):
        b.spines[s_].set_visible(False)
    fig.subplots_adjust(left=0.01, right=0.98, bottom=0.27, top=0.97, wspace=0.12)
    fig.savefig(path, dpi=200); plt.close(fig)
