"""Mapy PNG, animacja GIF i wykres powierzchni (etykiety po polsku dla użytkowników aplikacji)."""
from __future__ import annotations
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

KOLORY_4 = {1: "#67000d", 2: "#4daf4a", 3: "#3182bd", 4: "#fee8a6"}
NAZWY_4 = {1: "zabudowa", 2: "lasy i drzewa", 3: "wody", 4: "pozostałe (trawy, uprawy, odsłonięta gleba)"}


def mapa_detekcji(fd, obszar, epoki, sciezka, tytul=""):
    cmap = plt.get_cmap("viridis", len(epoki))
    rgba = np.ones(fd.shape + (4,)); rgba[..., :3] = 0.93
    rgba[~obszar] = (1, 1, 1, 1)
    for i, t in enumerate(epoki):
        rgba[fd == t] = cmap(i)
    fig, ax = plt.subplots(figsize=(7, 7 * fd.shape[0] / fd.shape[1] + 1.2))
    ax.imshow(rgba, interpolation="nearest"); ax.set_axis_off()
    if tytul:
        ax.set_title(tytul, loc="left", fontsize=10, fontweight="bold")
    lab = [f"≤ {epoki[0]}"] + [f"{a + 1}–{b}" for a, b in zip(epoki[:-1], epoki[1:])]
    fig.legend(handles=[Patch(fc=cmap(i), label=l) for i, l in enumerate(lab)], loc="lower center",
               ncol=min(5, len(lab)), fontsize=7, title="Okres, w którym zabudowa pojawiła się po raz pierwszy (piksel 30 m)", title_fontsize=8)
    fig.subplots_adjust(bottom=0.16, top=0.94, left=0.02, right=0.98)
    fig.savefig(sciezka, dpi=200); plt.close(fig)


def klatka(B_t, obszar, t, kl4=None):
    rgba = np.ones(B_t.shape + (4,))
    if kl4 is not None:
        for k, c in KOLORY_4.items():
            rgba[kl4 == k, :3] = matplotlib.colors.to_rgb(c)
    else:
        rgba[..., :3] = 0.93
        rgba[B_t] = (0.40, 0.0, 0.05, 1)
    rgba[~obszar] = (1, 1, 1, 1)
    return rgba


def animacja(B, obszar, sciezka, kl4=None, czas_ms=900):
    from PIL import Image
    ram = []
    for t in sorted(B):
        fig, ax = plt.subplots(figsize=(6, 6 * B[t].shape[0] / B[t].shape[1] + 0.6), dpi=110)
        ax.imshow(klatka(B[t], obszar, t, None if kl4 is None else kl4[t]), interpolation="nearest")
        ax.set_axis_off()
        if kl4 is None:
            leg = [Patch(fc="#660d0d", label="zabudowa"), Patch(fc="#ededed", ec="#999", label="brak zabudowy")]
        else:
            leg = [Patch(fc=KOLORY_4[k], label=NAZWY_4[k]) for k in KOLORY_4]
        ax.legend(handles=leg, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=2, fontsize=8, frameon=False)
        ax.set_title(f"{t}   zabudowa: {B[t][obszar].sum() * 0.09:,.0f} ha".replace(",", " "), loc="left", fontsize=11, fontweight="bold")
        fig.tight_layout(); fig.canvas.draw()
        ram.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3])); plt.close(fig)
    ram[0].save(sciezka, save_all=True, append_images=ram[1:] + [ram[-1]] * 2, duration=czas_ms, loop=0)


def wykres_powierzchni(tab, sciezka):
    ep = [r["epoka"] for r in tab]; ha = [r["zabudowa_ha"] for r in tab]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.plot(ep, ha, "o-", color="#67000d")
    ax.set_xlabel("Rok (epoka)"); ax.set_ylabel("Powierzchnia zabudowy [ha]"); ax.grid(alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(sciezka, dpi=200); plt.close(fig)
