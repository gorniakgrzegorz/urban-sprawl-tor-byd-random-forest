"""Więzy serii, epoka pierwszej detekcji, formy przyrostu i wskaźniki krajobrazowe."""
from __future__ import annotations
import numpy as np
from scipy import ndimage as ndi
from rasterio.features import geometry_mask
from . import dane

K8 = np.ones((3, 3), int); K8[1, 1] = 0


def maska_obszaru(geom, geobox):
    g = geom.to_crs(geobox.crs)
    return geometry_mask([g.geom], out_shape=geobox.shape, transform=geobox.affine, invert=True)


def maska_zasiegu(geobox, log=print, udzial=5 / 9):
    """Więz zasięgu M: piksele 30 m, w których co najmniej 5 z 9 pikseli 10 m jest zabudową w IO LULC 2017 lub 2024.

    Odpowiednik maski Dynamic World 2015 ∪ 2025 z projektu (tamte dane wymagają konta Google). Wariant wybrano
    porównaniem z serią A projektu w Toruniu i Bydgoszczy (zgodność wyższa niż przy zasięgu „dowolny piksel 10 m”
    i niż przy ESA WorldCover 2021).
    """
    M = np.zeros(geobox.shape, bool)
    H, W = geobox.shape
    for rok in (2017, 2024):
        try:
            a, _ = dane.mapa_10m("io-lulc-annual-v02", rok, geobox, "data")
            a = a[:H * 3, :W * 3]
            if a.shape != (H * 3, W * 3):
                a = np.pad(a, ((0, H * 3 - a.shape[0]), (0, W * 3 - a.shape[1])))
            M |= (a == 7).reshape(H, 3, W, 3).mean(axis=(1, 3)) >= udzial - 1e-9
            log(f"  maska zasięgu: IO LULC {rok} wczytana")
        except Exception as e:
            log(f"  maska zasięgu: pominięto IO LULC {rok} ({e})")
    return M


def seria_A(p: dict[int, np.ndarray], prog: float, M: np.ndarray | None):
    """Seria monotoniczna: B_t = M ∩ ⋃_{s ≤ t} (p_s ≥ próg). Zwraca dict epoka → mapa bool."""
    out, acc = {}, None
    for t in sorted(p):
        r = np.nan_to_num(p[t], nan=0) >= prog
        acc = r if acc is None else (acc | r)
        out[t] = acc & M if M is not None else acc.copy()
    return out


def pierwsza_detekcja(B: dict[int, np.ndarray]):
    ep = sorted(B)
    fd = np.full(B[ep[0]].shape, -1, "int16")
    for t in reversed(ep):
        fd[B[t]] = t
    return fd


def formy(B: dict[int, np.ndarray], obszar):
    """Udział wypełniania, przyrostu krawędziowego i przeskoku w nowej zabudowie każdego okresu (sąsiedzi 3 × 3)."""
    ep = sorted(B); rows = []
    for a, b in zip(ep[:-1], ep[1:]):
        new = B[b] & ~B[a] & obszar
        n = ndi.convolve(B[a].astype(int), K8, mode="constant")
        tot = new.sum()
        fi, fe, fl = (new & (n >= 4)).sum(), (new & (n >= 1) & (n <= 3)).sum(), (new & (n == 0)).sum()
        rows.append(dict(okres=f"{a}–{b}", nowa_ha=tot * 0.09,
                         wypelnianie_proc=100 * fi / tot if tot else np.nan,
                         krawedziowy_proc=100 * fe / tot if tot else np.nan,
                         przeskok_proc=100 * fl / tot if tot else np.nan))
    return rows


def metryki(b, obszar, res=30):
    """Liczba płatów (sąsiedztwo 8), średnia wielkość płatu, LPI klasowe, gęstość krawędzi."""
    x = b & obszar
    lab, n = ndi.label(x, structure=np.ones((3, 3)))
    area = x.sum() * res * res / 1e4
    sizes = np.bincount(lab.ravel())[1:] * res * res / 1e4 if n else np.array([0])
    # krawędzie tylko między parami pikseli leżących w obszarze (bez granicy obszaru badań, jak w artykułach)
    edges = ((x[1:, :] != x[:-1, :]) & obszar[1:, :] & obszar[:-1, :]).sum() + \
            ((x[:, 1:] != x[:, :-1]) & obszar[:, 1:] & obszar[:, :-1]).sum()
    km2 = obszar.sum() * res * res / 1e6
    return dict(zabudowa_ha=area, platy=int(n), sredni_plat_ha=float(sizes.mean()) if n else 0.0,
                lpi_klasowe_proc=float(100 * sizes.max() / area) if area else 0.0,
                gestosc_krawedzi_km_km2=float(edges * res / 1000 / km2) if km2 else 0.0)


def tabela(B, obszar, baza=None):
    ep = sorted(B); baza = baza or ep[0]; rows = []
    for t in ep:
        m = metryki(B[t], obszar)
        a0 = B[baza][obszar].sum() * 0.09
        m["epoka"] = t
        m["tempo_liniowe_od_bazy_proc_rok"] = (100 * (m["zabudowa_ha"] / a0 - 1) / (t - baza)) if (t > baza and a0) else np.nan
        rows.append(m)
    return rows
