"""Series constraints, first-detection epoch, growth forms and landscape metrics."""
from __future__ import annotations
import numpy as np
from scipy import ndimage as ndi
from rasterio.features import geometry_mask
from . import data

K8 = np.ones((3, 3), int); K8[1, 1] = 0
IO_BUILT = 7  # IO LULC class "built area"


def area_mask(geom, geobox):
    g = geom.to_crs(geobox.crs)
    return geometry_mask([g.geom], out_shape=geobox.shape, transform=geobox.affine, invert=True)


def built_fraction(a10, shape30, code=IO_BUILT):
    """Share of the nine 10 m cells of each 30 m cell that carry the given class code."""
    return (data.to_blocks(a10, shape30) == code).mean(axis=-1)


def extent_mask(geobox, log=print, min_share=5 / 9, years=(2017, 2023)):
    """Extent constraint M: 30 m pixels in which at least 5 of 9 10 m cells are built-up in IO LULC 2017 or 2023 (the first and the last map in the catalogue).

    Counterpart of the Dynamic World 2015 and 2025 union used in the reference project (which needs a Google account).
    The variant was chosen by comparison with the reference series in Torun and Bydgoszcz (see the paper, Section 2.4).
    """
    M = np.zeros(geobox.shape, bool)
    for year in years:
        try:
            a, _ = data.load_10m_map("io-lulc-annual-v02", year, geobox, "data")
            M |= built_fraction(a, geobox.shape) >= min_share - 1e-9
            log(f"  extent mask: IO LULC {year} loaded")
        except Exception as e:  # missing year: the mask is built from the remaining one
            log(f"  extent mask: IO LULC {year} skipped ({e})")
    return M


def monotonic_series(p: dict[int, np.ndarray], threshold: float, M: np.ndarray | None):
    """Monotonic series B_t = M AND (p_s >= threshold for any s <= t). Returns {epoch: bool map}."""
    out, acc = {}, None
    for t in sorted(p):
        r = np.nan_to_num(p[t], nan=0) >= threshold
        acc = r if acc is None else (acc | r)
        out[t] = acc & M if M is not None else acc.copy()
    return out


def first_detection(B: dict[int, np.ndarray]):
    """Epoch in which each pixel is built-up for the first time (-1 = never)."""
    ep = sorted(B)
    fd = np.full(B[ep[0]].shape, -1, "int16")
    for t in reversed(ep):
        fd[B[t]] = t
    return fd


def growth_forms(B: dict[int, np.ndarray], area):
    """Share of infill, edge expansion and leapfrog in the new built-up land of each period (3 x 3 neighbours)."""
    ep = sorted(B); rows = []
    for a, b in zip(ep[:-1], ep[1:]):
        new = B[b] & ~B[a] & area
        n = ndi.convolve(B[a].astype(int), K8, mode="constant")
        tot = new.sum()
        fi, fe, fl = (new & (n >= 4)).sum(), (new & (n >= 1) & (n <= 3)).sum(), (new & (n == 0)).sum()
        rows.append(dict(period=f"{a}-{b}", new_ha=tot * 0.09,
                         infill_pct=100 * fi / tot if tot else np.nan,
                         edge_expansion_pct=100 * fe / tot if tot else np.nan,
                         leapfrog_pct=100 * fl / tot if tot else np.nan))
    return rows


def metrics(b, area, res=30):
    """Number of patches (8-neighbourhood), mean patch size, class-level LPI and edge density."""
    x = b & area
    lab, n = ndi.label(x, structure=np.ones((3, 3)))
    ha = x.sum() * res * res / 1e4
    sizes = np.bincount(lab.ravel())[1:] * res * res / 1e4 if n else np.array([0])
    # edges only between pixel pairs inside the area (the study-area boundary is not counted)
    edges = ((x[1:, :] != x[:-1, :]) & area[1:, :] & area[:-1, :]).sum() + \
            ((x[:, 1:] != x[:, :-1]) & area[:, 1:] & area[:, :-1]).sum()
    km2 = area.sum() * res * res / 1e6
    return dict(built_up_ha=ha, patches=int(n), mean_patch_ha=float(sizes.mean()) if n else 0.0,
                lpi_class_pct=float(100 * sizes.max() / ha) if ha else 0.0,
                edge_density_km_per_km2=float(edges * res / 1000 / km2) if km2 else 0.0)


def epoch_table(B, area, base=None):
    ep = sorted(B); base = base or ep[0]; rows = []
    a0 = B[base][area].sum() * 0.09
    for t in ep:
        m = metrics(B[t], area)
        m["epoch"] = t
        # linear rate relative to the base epoch: 100 * (A_t / A_base - 1) / (t - base)
        m["linear_rate_from_base_pct_per_year"] = (100 * (m["built_up_ha"] / a0 - 1) / (t - base)) if (t > base and a0) else np.nan
        rows.append(m)
    return rows
