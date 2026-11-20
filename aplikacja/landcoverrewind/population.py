"""SDG indicator 11.3.1: ratio of land consumption rate to population growth rate (LCRPGR).

The built-up series is combined with a population grid of two dates (for example the Polish census grids
NSP 2011 and NSP 2021 of 1 km published by Statistics Poland, or any polygon layer with a population field).

Definitions follow the UN-Habitat metadata of indicator 11.3.1 (last update 23 April 2025):
  LCR = (Urb_t1 - Urb_t0) / Urb_t0 / y        (linear form, default)   or ln(Urb_t1 / Urb_t0) / y (log form)
  PGR = ln(Pop_t1 / Pop_t0) / y
  LCRPGR = LCR / PGR
Built-up area at a census date is interpolated linearly between the two nearest series epochs.
"""
from __future__ import annotations
import math
import warnings
import numpy as np
import geopandas as gpd
from rasterio import features as rfeatures
from rasterio.transform import array_bounds
from shapely.geometry import box as shp_box

STABLE_PGR = 0.0013  # |PGR| below this (about 0.13 %/year, i.e. a change below about 1.3 % in ten years) is treated as stable population
MIN_POP = 100  # cells with fewer inhabitants at t0 get no cell ratio (very small populations give extreme rates)


def built_at(B, year):
    """Built-up raster (float 0-1 per pixel) at `year`, linear interpolation between the bracketing epochs."""
    ep = sorted(B)
    if year <= ep[0]:
        return B[ep[0]].astype("float32")
    if year >= ep[-1]:
        return B[ep[-1]].astype("float32")
    a = max(t for t in ep if t <= year); b = min(t for t in ep if t >= year)
    if a == b:
        return B[a].astype("float32")
    w = (year - a) / (b - a)
    return (1 - w) * B[a].astype("float32") + w * B[b].astype("float32")


def rates(a0, a1, p0, p1, years, lcr_form="linear"):
    """LCR, PGR and LCRPGR with a status label explaining when the ratio is not interpretable."""
    nan = float("nan")
    if not (a0 > 0 and p0 > 0 and p1 > 0 and years > 0):
        return dict(lcr=nan, pgr=nan, lcrpgr=nan, status="no built-up or population at t0")
    lcr = (a1 - a0) / a0 / years if lcr_form == "linear" else math.log(a1 / a0) / years if a1 > 0 else nan
    pgr = math.log(p1 / p0) / years
    ratio = lcr / pgr if pgr != 0 else nan
    if abs(pgr) < STABLE_PGR:
        status = "population stable"
        ratio = nan  # not interpretable; kept as NaN so that a GIS filter cannot select it by mistake
    elif pgr < 0:
        status = "population decline"
    else:
        status = "ok"
    return dict(lcr=lcr, pgr=pgr, lcrpgr=ratio, status=status)


def read_population(paths, value_fields, id_field=None):
    """One file with two population fields, or two files (one per date) joined by `id_field`.
    Returns a GeoDataFrame with columns pop0, pop1 and geometry."""
    if len(paths) == 1:
        g = gpd.read_file(paths[0])
        missing = [f for f in value_fields if f not in g.columns]
        if missing:
            raise ValueError(f"population field(s) {missing} not found; available: {list(g.columns)}")
        g = g.rename(columns={value_fields[0]: "pop0", value_fields[1]: "pop1"})
    else:
        f0, f1 = gpd.read_file(paths[0], rows=1), gpd.read_file(paths[1], rows=1)
        for f, fld, path in ((f0, value_fields[0], paths[0]), (f1, value_fields[-1], paths[1])):
            if fld not in f.columns or id_field not in f.columns:
                raise ValueError(f"fields {id_field!r} and {fld!r} are required in {path}; available: {list(f.columns)}")
        g0 = gpd.read_file(paths[0])[[id_field, value_fields[0], "geometry"]].rename(columns={value_fields[0]: "pop0"})
        g1 = gpd.read_file(paths[1])[[id_field, value_fields[-1]]].rename(columns={value_fields[-1]: "pop1"})
        g = g0.merge(g1, on=id_field, how="inner")
    if g.crs is None:
        raise ValueError("the population layer has no coordinate reference system")
    for c in ("pop0", "pop1"):
        g[c] = g[c].astype(float)  # missing values stay NaN (no data), they are not treated as zero population
    return g[["pop0", "pop1", "geometry"] + ([id_field] if id_field and id_field in g.columns else [])]


def sdg_11_3_1(B, area, transform, crs, pop, years, lcr_form="linear", full_cover=0.99, new_ha=0.5,
               area_geom=None, min_pop=MIN_POP):
    """Cell table and whole-area summary of indicator 11.3.1.

    B: dict epoch -> bool built-up raster; area: bool raster of the analysed area; transform, crs: raster grid;
    pop: GeoDataFrame with pop0, pop1 (from read_population); years: (census year t0, census year t1).
    Population of the whole area uses areal weighting of cells cut by the area boundary; cell indicators
    are computed only for cells covered by the area in at least `full_cover` of their surface and with at least
    `min_pop` inhabitants at t0 (the first census year). `area_geom` (shapely geometry in `crs`) gives the exact cell share inside the area;
    without it the share is the fraction of the cell's 30 m pixels that lie inside the area raster, multiplied by the share of the cell within the raster extent.
    """
    if not B:
        raise ValueError("empty built-up series")
    ep = sorted(B)
    for yr in (years[0], years[1]):
        if yr < ep[0] or yr > ep[-1]:
            warnings.warn(f"population date {yr} lies outside the series epochs {ep[0]}-{ep[-1]}; the nearest epoch is used")
    y0, y1 = years; dy = y1 - y0
    g = pop.to_crs(crs).reset_index(drop=True)
    px = abs(transform.a * transform.e)
    ids = rfeatures.rasterize(((geom, i + 1) for i, geom in enumerate(g.geometry)), out_shape=area.shape,
                              transform=transform, fill=0, dtype="int32")
    n = len(g) + 1
    inside = area & (ids > 0)
    k = ids[inside]
    cnt = np.bincount(k, minlength=n)
    a0 = np.bincount(k, built_at(B, y0)[inside], minlength=n) * px / 1e4
    a1 = np.bincount(k, built_at(B, y1)[inside], minlength=n) * px / 1e4
    if area_geom is not None:
        g["cover"] = np.clip(g.geometry.intersection(area_geom).area.values / g.geometry.area.values, 0, 1)
    else:
        # share of the cell's pixels inside the area, times the share of the cell lying within the raster extent
        # (a cell extending beyond the raster must not count as fully inside)
        cnt_all = np.bincount(ids.ravel(), minlength=n)
        H, W = area.shape
        b = array_bounds(H, W, transform)  # (west, south, east, north)
        extent = shp_box(b[0], b[1], b[2], b[3])
        in_raster = g.geometry.intersection(extent).area.values / g.geometry.area.values
        g["cover"] = np.clip(np.where(cnt_all[1:] > 0, cnt[1:] / np.maximum(cnt_all[1:], 1), 0.0) * in_raster, 0, 1)
    grid_share = float(inside.sum() / max(area.sum(), 1))
    if grid_share < 0.99:
        warnings.warn(f"the population grid covers {100 * grid_share:.1f}% of the area; built-up area is computed for the covered part only")
    g["built_t0_ha"] = a0[1:]; g["built_t1_ha"] = a1[1:]
    g["new_built_ha"] = g.built_t1_ha - g.built_t0_ha
    nanr = lambda st: dict(lcr=np.nan, pgr=np.nan, lcrpgr=np.nan, status=st)
    rows = [nanr("cell not fully inside the area") if r.cover < full_cover
            else nanr("population below minimum") if 0 < r.pop0 < min_pop
            else rates(r.built_t0_ha, r.built_t1_ha, r.pop0, r.pop1, dy, lcr_form) for r in g.itertuples()]
    for key in ("lcr", "pgr", "lcrpgr", "status"):
        g[key] = [r[key] for r in rows]
    g["built_per_capita_t0_m2"] = np.where(g.pop0 > 0, g.built_t0_ha * 1e4 / g.pop0.replace(0, np.nan), np.nan)
    g["built_per_capita_t1_m2"] = np.where(g.pop1 > 0, g.built_t1_ha * 1e4 / g.pop1.replace(0, np.nan), np.nan)
    ok_pop = (g.pop0 > 0) & (g.pop1 > 0)
    g["pgr_cell"] = np.where(ok_pop, np.log(g.pop1.where(ok_pop, 1) / g.pop0.where(ok_pop, 1)) / dy, np.nan)
    trend = np.where(g.pgr_cell.abs() < STABLE_PGR, "stable", np.where(g.pgr_cell > 0, "growth", "decline"))
    trend = np.where(g.pgr_cell.isna() | (g.cover < full_cover), "n.a.", trend)
    g["type"] = [f"population {t}, {'new built-up' if nb >= new_ha else 'no new built-up'}" if t != "n.a." else "n.a."
                 for t, nb in zip(trend, g.new_built_ha)]
    P0 = float((g.pop0 * g.cover).sum()); P1 = float((g.pop1 * g.cover).sum())
    A0 = float(a0.sum()); A1 = float(a1.sum())
    full = g[g.cover >= full_cover]
    summary = dict(years=[y0, y1], lcr_form=lcr_form, population_t0=round(P0), population_t1=round(P1),
                   built_t0_ha=round(A0, 1), built_t1_ha=round(A1, 1),
                   built_per_capita_t0_m2=round(A0 * 1e4 / P0, 1) if P0 else None,
                   built_per_capita_t1_m2=round(A1 * 1e4 / P1, 1) if P1 else None,
                   cells=int((g.cover > 0).sum()), cells_full=int(len(full)), grid_coverage_of_area=round(grid_share, 4),
                   min_pop=min_pop, full_cover=full_cover, cells_below_min_pop=int((full.status == "population below minimum").sum()),
                   **{k: (round(v, 5) if isinstance(v, float) and not math.isnan(v) else v)
                      for k, v in rates(A0, A1, P0, P1, dy, lcr_form).items()})
    with_ratio = full[full.status.isin(["ok", "population decline"])]
    summary["cells_with_ratio"] = int(len(with_ratio))
    summary["cells_ratio_above_1_pct"] = round(100 * float((with_ratio.lcrpgr > 1).mean()), 1) if len(with_ratio) else None
    summary["new_built_in_declining_cells_pct"] = (round(100 * float(full.loc[full.pgr_cell <= -STABLE_PGR, "new_built_ha"].clip(lower=0).sum()
                                                                     / full.new_built_ha.clip(lower=0).sum()), 1)
                                                   if full.new_built_ha.clip(lower=0).sum() > 0 else None)
    return g[g.cover > 0].reset_index(drop=True), summary
