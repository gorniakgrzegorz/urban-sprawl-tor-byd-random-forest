"""Nineteen features per epoch t (Landsat window t-1 ... t+1); the classifier uses the first 18.

 1-6   summer median (June-September): blue, green, red, nir, swir1, swir2
 7-12  summer indices: NDVI, NDBI, NDWI, MNDWI, BU = NDBI - NDVI, BSI
13-14  NIR texture (GLCM, 7 x 7 window): contrast, entropy
15-18  spring median (March-May) indices: NDVI, NDBI, BU, BSI
19     NDVI amplitude over the window (95th minus 5th percentile of clear observations);
       computed but not used by the models (unstable between epochs)
Large areas are processed in tiles; each band of each scene is read once.
"""
from __future__ import annotations
import warnings
import numpy as np
from scipy.ndimage import uniform_filter
from . import data

NAMES = ["blue", "green", "red", "nir", "swir1", "swir2", "ndvi", "ndbi", "ndwi", "mndwi", "bu", "bsi",
         "glcm_contrast", "glcm_entropy", "ndvi_spring", "ndbi_spring", "bu_spring", "bsi_spring", "ndvi_amplitude"]


def _nd(a, b):
    with np.errstate(invalid="ignore", divide="ignore"):
        return (a - b) / (a + b)


def indices(b):
    """Spectral indices from a stack of six bands (blue, green, red, nir, swir1, swir2)."""
    blue, green, red, nir, sw1, _ = b
    ndvi, ndbi = _nd(nir, red), _nd(sw1, nir)
    return dict(ndvi=ndvi, ndbi=ndbi, ndwi=_nd(green, nir), mndwi=_nd(green, sw1), bu=ndbi - ndvi,
                bsi=_nd(sw1 + red, nir + blue))


def _shift(a, dy, dx):
    H, W = a.shape
    out = a.copy()
    if dx >= 0:
        out[:H - dy, :W - dx] = a[dy:, dx:]
    else:
        out[:H - dy, -dx:] = a[dy:, :W + dx]
    return out


def glcm(nir, window=7, levels_contrast=32, levels_entropy=8, value_range=(0.0, 0.6)):
    """GLCM contrast and entropy in a moving window, averaged over 0, 45, 90 and 135 degrees.

    Reflectance in value_range is quantised to 32 levels for contrast and 8 for entropy (memory limit).
    The scale differs from Google Earth Engine glcmTexture, so models are trained on features from this code.
    """
    x = np.nan_to_num(nir, nan=float(np.nanmedian(nir)))
    lo, hi = value_range
    qc = np.clip(((x - lo) / (hi - lo) * levels_contrast).astype(int), 0, levels_contrast - 1)
    qe = np.clip(((x - lo) / (hi - lo) * levels_entropy).astype(int), 0, levels_entropy - 1)
    contrast = np.zeros(x.shape, "float32"); entropy = np.zeros(x.shape, "float32")
    for dy, dx in [(0, 1), (1, 1), (1, 0), (1, -1)]:
        sc, se = _shift(qc, dy, dx), _shift(qe, dy, dx)
        d = (qc - sc).astype("float32")
        contrast += uniform_filter(d * d, window, mode="nearest")
        p1, p2 = qe * levels_entropy + se, se * levels_entropy + qe
        for k in np.unique(np.concatenate([p1.ravel(), p2.ravel()])):
            p = 0.5 * (uniform_filter((p1 == k).astype("float32"), window, mode="nearest")
                       + uniform_filter((p2 == k).astype("float32"), window, mode="nearest"))
            entropy -= np.where(p > 1e-6, p * np.log(np.maximum(p, 1e-6)), 0).astype("float32")
    return contrast / 4, entropy / 4


def _median(a):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanmedian(a, axis=0).astype("float32")


def _tile_features(summer, spring, other, gb, pool):
    """Summer and spring composites and NDVI percentiles for one tile."""
    S = P = None; red_all, nir_all = [], []
    if summer:
        d = data.load_reflectance(summer, gb, data.BANDS, pool)
        S = np.stack([_median(d[b]) for b in data.BANDS]); red_all.append(d["red"]); nir_all.append(d["nir08"]); del d
    if spring:
        d = data.load_reflectance(spring, gb, ("blue", "red", "nir08", "swir16"), pool)
        P = np.full((6,) + gb.shape, np.nan, "float32")
        for b in ("blue", "red", "nir08", "swir16"):
            P[data.BANDS.index(b)] = _median(d[b])
        red_all.append(d["red"]); nir_all.append(d["nir08"]); del d
    if other:
        d = data.load_reflectance(other, gb, ("red", "nir08"), pool)
        red_all.append(d["red"]); nir_all.append(d["nir08"]); del d
    r, n = np.concatenate(red_all), np.concatenate(nir_all); del red_all, nir_all
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        nd = (n - r) / (n + r); del r, n
        q = np.nanpercentile(nd, [5, 95], axis=0).astype("float32")
    return S, P, q


def epoch_features(t: int, geobox, log=print, max_cloud=70, tile=768, pool=None):
    """Feature stack (19, H, W) and input description for epoch t."""
    years = (t - 1, t + 1)
    log(f"  epoch {t}: searching Landsat scenes {years[0]}-{years[1]}")
    items = data.search_scenes(geobox, years, max_cloud)
    if not items:
        raise RuntimeError(f"No Landsat scenes for epoch {t}")
    summer = [i for i in items if 6 <= i.datetime.month <= 9]
    spring = [i for i in items if 3 <= i.datetime.month <= 5]
    other = [i for i in items if i not in summer and i not in spring]
    log(f"    scenes: summer {len(summer)}, spring {len(spring)}, other months {len(other)}")
    if not summer:
        raise RuntimeError(f"No summer scenes for epoch {t}")
    H, W = geobox.shape
    S = np.full((6, H, W), np.nan, "float32"); P = np.full((6, H, W), np.nan, "float32")
    Q = np.full((2, H, W), np.nan, "float32")
    tiles = [(y, x) for y in range(0, H, tile) for x in range(0, W, tile)]
    has_spring = False
    for k, (y, x) in enumerate(tiles, 1):
        gb = geobox[y:min(y + tile, H), x:min(x + tile, W)]; h, w = gb.shape
        s, p, q = _tile_features(summer, spring, other, gb, pool)
        S[:, y:y + h, x:x + w] = s; Q[:, y:y + h, x:x + w] = q
        if p is not None:
            P[:, y:y + h, x:x + w] = p; has_spring = True
        if len(tiles) > 1:
            log(f"    tile {k}/{len(tiles)} done")
    i_summer = indices(S)
    i_spring = indices(P) if has_spring else i_summer
    if not has_spring:
        log("    no spring scenes: spring features replaced by summer features")
    contrast, entropy = glcm(S[3])
    F = np.stack([*S, i_summer["ndvi"], i_summer["ndbi"], i_summer["ndwi"], i_summer["mndwi"], i_summer["bu"],
                  i_summer["bsi"], contrast, entropy, i_spring["ndvi"], i_spring["ndbi"], i_spring["bu"],
                  i_spring["bsi"], Q[1] - Q[0]]).astype("float32")
    return F, dict(epoch=t, scenes=len(items), scenes_summer=len(summer), scenes_spring=len(spring),
                   sensors=", ".join(sorted({i.properties["platform"] for i in items})),
                   scene_ids=sorted(i.id for i in items))
