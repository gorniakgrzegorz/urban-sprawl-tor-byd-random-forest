"""Dziewiętnaście cech dla epoki t (okno lat t−1…t+1), wzorowanych na modelu projektu w GEE.

1–6   pasma kompozytu letniego (VI–IX, mediana): blue, green, red, nir, swir1, swir2
7–12  wskaźniki z kompozytu letniego: NDVI, NDBI, NDWI, MNDWI, BU = NDBI − NDVI, BSI
13–14 tekstura pasma NIR (GLCM, okno 7 × 7 = 210 m): kontrast, entropia
15–18 wskaźniki kompozytu przedwiośnia (III–V, mediana): NDVI, NDBI, BU, BSI
19    amplituda NDVI w oknie lat (95. minus 5. percentyl NDVI czystych scen; w GEE: maksimum minus minimum);
      liczona, ale nieużywana przez model (niestabilna między epokami)

Każde pasmo sceny pobierane jest raz (pasma przedwiośnia i pozostałych miesięcy tylko w zakresie
potrzebnym do wskaźników), a duże obszary liczone są w kaflach.
"""
from __future__ import annotations
import numpy as np
from scipy.ndimage import uniform_filter
from . import dane

NAZWY = ["blue", "green", "red", "nir", "swir1", "swir2", "ndvi", "ndbi", "ndwi", "mndwi", "bu", "bsi",
         "glcm_kontrast", "glcm_entropia", "ndvi_sucha", "ndbi_sucha", "bu_sucha", "bsi_sucha", "ndvi_ampl"]


def _nd(a, b):
    with np.errstate(invalid="ignore", divide="ignore"):
        return (a - b) / (a + b)


def wskazniki(b):
    blue, green, red, nir, sw1, sw2 = b
    ndvi = _nd(nir, red); ndbi = _nd(sw1, nir)
    bsi = _nd(sw1 + red, nir + blue)
    return dict(ndvi=ndvi, ndbi=ndbi, ndwi=_nd(green, nir), mndwi=_nd(green, sw1), bu=ndbi - ndvi, bsi=bsi)


def _shift(a, dy, dx):
    H, W = a.shape
    out = a.copy()
    if dx >= 0:
        out[:H - dy, :W - dx] = a[dy:, dx:]
    else:
        out[:H - dy, -dx:] = a[dy:, :W + dx]
    return out


def glcm(nir, okno=7, poziomy_k=32, poziomy_e=8, zakres=(0.0, 0.6)):
    """Kontrast i entropia GLCM w oknie przesuwnym, średnia z kierunków 0°, 45°, 90°, 135°.

    Kontrast na 32 poziomach, entropia na 8 poziomach (ograniczenie pamięci); skala różni się
    od GEE glcmTexture, dlatego model uczono na cechach liczonych tym samym kodem.
    """
    x = np.nan_to_num(nir, nan=float(np.nanmedian(nir)))
    lo, hi = zakres
    qk = np.clip(((x - lo) / (hi - lo) * poziomy_k).astype(int), 0, poziomy_k - 1)
    qe = np.clip(((x - lo) / (hi - lo) * poziomy_e).astype(int), 0, poziomy_e - 1)
    kon = np.zeros(x.shape, "float32"); ent = np.zeros(x.shape, "float32")
    for dy, dx in [(0, 1), (1, 1), (1, 0), (1, -1)]:
        sk = _shift(qk, dy, dx); se = _shift(qe, dy, dx)
        d = (qk - sk).astype("float32")
        kon += uniform_filter(d * d, okno, mode="nearest")
        p1 = qe * poziomy_e + se; p2 = se * poziomy_e + qe
        for k in np.unique(np.concatenate([p1.ravel(), p2.ravel()])):
            p = 0.5 * (uniform_filter((p1 == k).astype("float32"), okno, mode="nearest")
                       + uniform_filter((p2 == k).astype("float32"), okno, mode="nearest"))
            ent -= np.where(p > 1e-6, p * np.log(np.maximum(p, 1e-6)), 0).astype("float32")
    return kon / 4, ent / 4


def _pasma(items, gb, pasma, pool):
    """Wczytuje wskazane pasma scen (time, y, x) jako odbicie OLI-równoważne z maską chmur; zwraca dict pasmo → tablica."""
    out = {b: [] for b in pasma}
    for grupa in ("oli", "tm"):
        its = [i for i in items if (i.properties["platform"] in ("landsat-8", "landsat-9")) == (grupa == "oli")]
        if not its:
            continue
        ds = dane.stac_load(its, bands=list(pasma) + ["qa_pixel"], geobox=gb, groupby="solar_day", pool=pool,
                            resampling={"qa_pixel": "nearest", "*": "bilinear"}, fail_on_error=False)
        clear = ((ds["qa_pixel"].values & 0b111111) == 0)
        for b in pasma:
            j = dane.BANDS.index(b)
            raw = ds[b].values
            v = raw.astype("float32") * 2.75e-5 - 0.2
            if grupa == "tm":
                v = v * dane.ROY_SLOPE[j] + dane.ROY_OFFSET[j]
            v[(raw == 0) | ~clear | (v < -0.05) | (v > 1.2)] = np.nan
            out[b].append(v)
        del ds, clear
    return {b: (np.concatenate(v) if v else None) for b, v in out.items()}


def _mediana(a):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanmedian(a, axis=0).astype("float32")


def _cechy_kafla(lato, sucha, reszta, gb, pool):
    """Kompozyty i percentyle NDVI dla jednego kafla (pasma wczytywane osobno, aby ograniczyć pamięć)."""
    import warnings
    L = S = None; red_all, nir_all = [], []
    if lato:
        d = _pasma(lato, gb, dane.BANDS, pool)
        L = np.stack([_mediana(d[b]) for b in dane.BANDS]); red_all.append(d["red"]); nir_all.append(d["nir08"]); del d
    if sucha:
        d = _pasma(sucha, gb, ("blue", "red", "nir08", "swir16"), pool)
        S = np.full((6,) + gb.shape, np.nan, "float32")
        for b in ("blue", "red", "nir08", "swir16"):
            S[dane.BANDS.index(b)] = _mediana(d[b])
        red_all.append(d["red"]); nir_all.append(d["nir08"]); del d
    if reszta:
        d = _pasma(reszta, gb, ("red", "nir08"), pool)
        red_all.append(d["red"]); nir_all.append(d["nir08"]); del d
    r = np.concatenate(red_all); n = np.concatenate(nir_all); del red_all, nir_all
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        nd = (n - r) / (n + r); del r, n
        q = np.nanpercentile(nd, [5, 95], axis=0).astype("float32")
    return L, S, q


def cechy_epoki(t: int, geobox, log=print, max_chmur=70, kafel=768, pool=None):
    """Macierz cech (19, H, W) i opis danych dla epoki t.

    Każde pasmo każdej sceny pobierane jest raz; obszary większe niż kafel × kafel pikseli liczone są w kaflach.
    """
    import os
    pool = pool or int(os.environ.get("URBANRF_WATKI", 8))
    lata = (t - 1, t + 1)
    log(f"  epoka {t}: wyszukiwanie scen Landsat {lata[0]}–{lata[1]}")
    items = dane.sceny(geobox, lata, None, max_chmur)
    if not items:
        raise RuntimeError(f"Brak scen Landsat dla epoki {t}")
    lato = [i for i in items if 6 <= i.datetime.month <= 9]
    sucha = [i for i in items if 3 <= i.datetime.month <= 5]
    reszta = [i for i in items if i not in lato and i not in sucha]
    log(f"    sceny: lato {len(lato)}, przedwiośnie {len(sucha)}, pozostałe miesiące {len(reszta)}")
    if not lato:
        raise RuntimeError(f"Brak scen letnich dla epoki {t}")
    H, W = geobox.shape
    L = np.full((6, H, W), np.nan, "float32"); S = np.full((6, H, W), np.nan, "float32")
    Q = np.full((2, H, W), np.nan, "float32")
    kafle = [(y, x) for y in range(0, H, kafel) for x in range(0, W, kafel)]
    ma_s = False
    for k, (y, x) in enumerate(kafle, 1):
        gb = geobox[y:min(y + kafel, H), x:min(x + kafel, W)]; h, w = gb.shape
        l, s, q = _cechy_kafla(lato, sucha, reszta, gb, pool)
        L[:, y:y + h, x:x + w] = l; Q[:, y:y + h, x:x + w] = q
        if s is not None:
            S[:, y:y + h, x:x + w] = s; ma_s = True
        if len(kafle) > 1:
            log(f"    kafel {k}/{len(kafle)} gotowy")
    wl = wskazniki(L)
    ws = wskazniki(S) if ma_s else wl
    if not ma_s:
        log("    brak scen przedwiośnia: cechy przedwiośnia zastąpione letnimi")
    kon, ent = glcm(L[3])
    F = np.stack([*L, wl["ndvi"], wl["ndbi"], wl["ndwi"], wl["mndwi"], wl["bu"], wl["bsi"], kon, ent,
                  ws["ndvi"], ws["ndbi"], ws["bu"], ws["bsi"], Q[1] - Q[0]]).astype("float32")
    sensory = sorted({i.properties["platform"] for i in items})
    return F, dict(epoka=t, sceny=len(items), sceny_lato=len(lato), sceny_przedwiosnie=len(sucha),
                   sensory=", ".join(sensory), id_scen=sorted(i.id for i in items))
