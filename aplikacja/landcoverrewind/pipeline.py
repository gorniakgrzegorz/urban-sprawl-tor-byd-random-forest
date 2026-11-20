"""End-to-end run for a user-defined area."""
from __future__ import annotations
import csv
import hashlib
import json
import pathlib
import time
import zipfile
import numpy as np
import rasterio
from . import data, features, model, series, viz, population, EPOCHS, __version__

# IO LULC classes -> 1 built-up, 2 trees and forest, 3 water, 4 other
IO_TO_4 = {1: 3, 2: 2, 4: 3, 5: 4, 7: 1, 8: 4, 11: 4}
PRETRAINED = ("rf_torun_bydgoszcz_2025_binary", "rf_torun_bydgoszcz_2025_4class")


def teacher_labels(geobox, year=2024, log=print):
    """30 m labels from IO LULC (Sentinel-2, 10 m): built-up when at least 5 of 9 cells are built-up,
    otherwise the dominant class; mixed pixels (1-4 built-up cells) and pixels with < 5 valid cells are ignored (255)."""
    a, _ = data.load_10m_map("io-lulc-annual-v02", year, geobox, "data")
    k = np.full(a.shape, 255, "uint8")
    for src, dst in IO_TO_4.items():
        k[a == src] = dst
    blk = data.to_blocks(k, geobox.shape)
    cnt = np.stack([(blk == c).sum(-1) for c in (1, 2, 3, 4)], -1)
    lab = (cnt.argmax(-1) + 1).astype("uint8")
    lab[cnt[..., 0] >= 5] = 1
    lab[(cnt[..., 0] > 0) & (cnt[..., 0] < 5)] = 255
    lab[cnt.sum(-1) < 5] = 255
    log(f"  teacher labels IO LULC {year}: " + ", ".join(f"{c}: {(lab == c).sum()}" for c in (1, 2, 3, 4)))
    return lab


def write_tif(path, a, geobox, dtype, nodata=None):
    prof = dict(driver="GTiff", height=a.shape[0], width=a.shape[1], count=1, dtype=dtype, crs=str(geobox.crs),
                transform=geobox.affine, compress="deflate", nodata=nodata)
    with rasterio.open(path, "w", **prof) as d:
        d.write(a.astype(dtype), 1)


def _rounded(rows, nd=2):
    """Round floats for CSV output; missing values become empty cells."""
    return [{k: ("" if np.isnan(v) else round(v, nd)) if isinstance(v, float) else v for k, v in r.items()} for r in rows]


def run(geom, epochs=None, mode="pretrained", threshold=0.65, out_dir="results", crs=None, max_cloud=70,
        log=print, progress=None, lang="en", extent_years=(2017, 2024)):
    """Reconstruct the built-up series and four-class maps for `geom` (odc.geo Geometry).

    mode: "pretrained" uses the Torun/Bydgoszcz 2025 models; "local" trains on IO LULC 2024 labels in the area.
    progress(fraction 0-1, step description) lets a user interface show a progress bar.
    Returns a dict with the series B, four-class maps K4, probabilities P, extent mask M and tables.
    """
    mode = {"gotowy": "pretrained", "lokalny": "local"}.get(mode, mode)
    t0 = time.time()
    epochs = sorted(epochs or EPOCHS)
    n_steps = len(epochs) + 4 + (1 if mode == "local" else 0)
    state = {"k": 0}

    def step(text):
        if progress:
            progress(min(state["k"] / n_steps, 0.99), text)
        state["k"] += 1

    step("prepare")
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    cache = out / "cache"; cache.mkdir(exist_ok=True)
    gb = data.make_grid(geom, crs)
    area = series.area_mask(geom, gb)
    km2 = area.sum() * 900 / 1e6
    log(f"Area: {km2:.1f} km2, grid {gb.shape[1]} x {gb.shape[0]} pixels of 30 m, CRS {gb.crs}")
    key = hashlib.md5(f"{gb.crs}|{tuple(gb.affine)}|{gb.shape}|{max_cloud}".encode()).hexdigest()[:10]

    def epoch_features(t):
        # the cache key includes the grid and the cloud limit, so a different area never reuses these features
        f = cache / f"features_{t}_{key}.npy"
        if f.exists():
            return np.load(f), json.loads(f.with_suffix(".json").read_text())
        F, info = features.epoch_features(t, gb, log, max_cloud)
        np.save(f, F); f.with_suffix(".json").write_text(json.dumps(info))
        return F, info

    if mode == "pretrained":
        rf2, _ = model.load(PRETRAINED[0])
        rf4, _ = model.load(PRETRAINED[1])
        log("Model: rf_torun_bydgoszcz_2025 (trained on the 2025 maps of Torun and Bydgoszcz)")
    elif mode == "local":
        step("train")
        log("Model: local training on IO LULC 2024 labels and epoch 2025 features")
        F25, _ = epoch_features(2025)
        lab = teacher_labels(gb, 2024, log)
        X, y = model.sample_points(np.where(lab == 255, 255, (lab == 1).astype("uint8")), F25, mask=area)
        rf2 = model.train(X, y)
        X4, y4 = model.sample_points(lab, F25, mask=area)
        rf4 = model.train(X4, y4)
        model.save(rf2, "local_model_binary", dict(name="local_model_binary", labels="IO LULC 2024", training_epoch=2025),
                   directory=out.resolve())
        log(f"  OOB: binary {rf2.oob_score_:.3f}, four-class {rf4.oob_score_:.3f}")
    else:
        raise ValueError(f"unknown mode: {mode}")

    P, K4, inputs = {}, {}, []
    i_built = list(rf2.classes_).index(1)
    for i, t in enumerate(epochs, 1):
        step(f"epoch {t} ({i}/{len(epochs)})")
        try:
            F, info = epoch_features(t)
        except Exception as e:
            log(f"  epoch {t} skipped: {e}"); continue
        P[t] = model.predict(rf2, F)[i_built]
        p4 = model.predict(rf4, F)
        cl = np.array(rf4.classes_)
        nb = [j for j, c in enumerate(cl) if c != 1]
        K4[t] = cl[nb][np.nanargmax(np.nan_to_num(p4[nb], nan=-1), axis=0)].astype("uint8")
        K4[t][np.isnan(p4[0])] = 0  # no data
        inputs.append(info)
        write_tif(out / f"built_up_probability_{t}.tif", np.where(np.isnan(P[t]), 255, np.round(P[t] * 100)), gb, "uint8", 255)
    if not P:
        raise RuntimeError("No epoch could be computed")
    step("series")
    M = series.extent_mask(gb, log, years=extent_years)
    if not M.any():
        raise RuntimeError("The IO LULC extent mask could not be loaded or contains no built-up land in this area")
    B = series.monotonic_series(P, threshold, M)
    for t in B:
        K4[t][B[t]] = 1
        write_tif(out / f"built_up_{t}.tif", np.where(area, B[t], 255), gb, "uint8", 255)
        write_tif(out / f"land_cover_4class_{t}.tif", np.where(area, K4[t], 0), gb, "uint8", 0)
    fd = series.first_detection(B)
    # inside the area: first-detection epoch or 0 (never built-up); outside: -1 (no data)
    write_tif(out / "first_detection_epoch.tif", np.where(area, np.where(fd < 0, 0, fd), -1), gb, "int16", -1)
    table = series.epoch_table(B, area, base=1990 if 1990 in B else None)
    forms = series.growth_forms(B, area)
    step("tables")
    for name, rows in (("epoch_metrics.csv", _rounded(table)), ("growth_forms.csv", _rounded(forms, 1)),
                       ("input_scenes.csv", [{k: v for k, v in r.items() if k != "scene_ids"} for r in inputs])):
        if rows:
            with open(out / name, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    ep = sorted(B)
    step("figures")
    viz.first_detection_map(fd, area, ep, out / "first_detection_map.png", lang)
    viz.animation(B, area, out / "built_up_animation.gif", lang=lang)
    viz.animation(B, area, out / "land_cover_animation.gif", k4=K4, lang=lang)
    viz.area_chart(table, out / "built_up_area_chart.png", lang)
    meta = dict(software=f"landcoverrewind {__version__}", area_km2=round(float(km2), 2), crs=str(gb.crs), epochs=ep,
                mode=mode, threshold=threshold, max_cloud=max_cloud, extent_years=list(extent_years),
                scenes={o["epoch"]: o.get("scene_ids", []) for o in inputs}, date=time.strftime("%Y-%m-%d"),
                runtime_s=round(time.time() - t0), skipped_epochs=[t for t in epochs if t not in P],
                source="Microsoft Planetary Computer (landsat-c2-l2, io-lulc-annual-v02)")
    (out / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    with zipfile.ZipFile(out / "results.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in out.iterdir():
            # only files written by this run: a reused folder may hold outputs of an earlier run
            if p.is_file() and p.suffix != ".zip" and p.stat().st_mtime >= t0 - 1:
                z.write(p, p.name)
    if progress:
        progress(1.0, "done")
    log(f"Done in {meta['runtime_s']} s: {out.resolve()}")
    return dict(B=B, K4=K4, P=P, M=M, table=table, forms=forms, inputs=inputs, area=area, geobox=gb,
                out_dir=out.resolve(), skipped=[t for t in epochs if t not in P])


def run_sdg(result, pop_paths, value_fields, years, id_field=None, lcr_form="linear", lang="en", area_geom=None):
    """SDG 11.3.1 for a finished run: writes sdg_11_3_1_cells.gpkg/.csv, sdg_11_3_1_summary.json and
    sdg_11_3_1.png to the run folder and adds them to results.zip. Returns (cells, summary)."""
    out = pathlib.Path(result["out_dir"]); gb = result["geobox"]
    pop = population.read_population(list(pop_paths), list(value_fields), id_field)
    outline = None
    if area_geom is not None:
        import geopandas as gpd
        outline = gpd.GeoSeries([area_geom.geom], crs=str(area_geom.crs)).to_crs(str(gb.crs))
    cells, summary = population.sdg_11_3_1(result["B"], result["area"], gb.affine, str(gb.crs), pop, tuple(years), lcr_form,
                                           area_geom=None if outline is None else outline.union_all())
    cells.to_file(out / "sdg_11_3_1_cells.gpkg", driver="GPKG")
    cells.drop(columns="geometry").to_csv(out / "sdg_11_3_1_cells.csv", index=False, float_format="%.5f")
    (out / "sdg_11_3_1_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    viz.sdg_figure(cells, outline, out / "sdg_11_3_1.png", lang)
    with zipfile.ZipFile(out / "results.zip", "a", zipfile.ZIP_DEFLATED) as z:
        names = set(z.namelist())
        for n in ("sdg_11_3_1_cells.gpkg", "sdg_11_3_1_cells.csv", "sdg_11_3_1_summary.json", "sdg_11_3_1.png"):
            if n not in names:
                z.write(out / n, n)
    return cells, summary
