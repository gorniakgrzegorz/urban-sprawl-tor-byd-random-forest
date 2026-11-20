"""Unit tests on synthetic arrays; no network access is needed."""
import numpy as np
import pytest
from landcoverrewind import data, features, model, series, pipeline


def test_to_blocks_and_fraction():
    a = np.zeros((6, 6), "uint8")
    a[:3, :3] = 7          # whole first 30 m cell built-up
    a[3:, 3:5] = 7         # 6 of 9 cells of the last 30 m cell
    blk = data.to_blocks(a, (2, 2))
    assert blk.shape == (2, 2, 9)
    f = series.built_fraction(a, (2, 2))
    assert f[0, 0] == 1 and f[1, 1] == pytest.approx(6 / 9) and f[0, 1] == 0


def test_to_blocks_pads_partial_cells():
    a = np.full((5, 4), 7, "uint8")  # 10 m grid smaller than 2 x 2 cells of 30 m
    f = series.built_fraction(a, (2, 2))
    assert f[0, 0] == 1 and f[1, 1] < 5 / 9


def test_monotonic_series_and_mask():
    p = {1990: np.array([[0.9, 0.1], [0.2, np.nan]]), 2000: np.array([[0.1, 0.7], [0.2, 0.9]])}
    M = np.array([[True, True], [False, True]])
    B = series.monotonic_series(p, 0.65, M)
    assert B[1990].tolist() == [[True, False], [False, False]]
    assert B[2000].tolist() == [[True, True], [False, True]]   # 1990 detection kept, unmasked pixel stays out
    assert all((B[2000] >= B[1990]).ravel())


def test_first_detection():
    B = {1990: np.array([[1, 0, 0]], bool), 2000: np.array([[1, 1, 0]], bool)}
    assert series.first_detection(B).tolist() == [[1990, 2000, -1]]


def test_growth_forms_classes():
    a = np.zeros((7, 7), bool); a[3, 1:6] = True; a[2:5, 3] = True
    b = a.copy(); b[2, 2] = True; b[0, 6] = True   # (2,2) touches 4 built cells: infill; (0,6) isolated: leapfrog
    b[3, 6] = True                                  # touches 1 built cell: edge expansion
    area = np.ones_like(a)
    r = series.growth_forms({1990: a, 2000: b}, area)[0]
    assert r["new_ha"] == pytest.approx(3 * 0.09)
    assert r["infill_pct"] + r["edge_expansion_pct"] + r["leapfrog_pct"] == pytest.approx(100)
    assert r["leapfrog_pct"] == pytest.approx(100 / 3)


def test_metrics_simple():
    b = np.zeros((10, 10), bool); b[2:4, 2:4] = True; b[7, 7] = True
    m = series.metrics(b, np.ones_like(b))
    assert m["patches"] == 2 and m["built_up_ha"] == pytest.approx(5 * 0.09)
    assert m["lpi_class_pct"] == pytest.approx(80)
    # 2 x 2 block has 8 edges, single pixel 4, each 30 m long; area 0.09 km2
    assert m["edge_density_km_per_km2"] == pytest.approx(12 * 0.03 / 0.09)


def test_epoch_table_rate():
    b0 = np.zeros((10, 10), bool); b0[:2] = True
    b1 = b0.copy(); b1[2] = True
    rows = series.epoch_table({1990: b0, 2000: b1}, np.ones_like(b0), base=1990)
    assert rows[1]["linear_rate_from_base_pct_per_year"] == pytest.approx(100 * (30 / 20 - 1) / 10)


def test_indices_and_glcm():
    rng = np.random.default_rng(0)
    b = rng.uniform(0.02, 0.4, (6, 20, 20)).astype("float32")
    ind = features.indices(b)
    assert np.allclose(ind["bu"], ind["ndbi"] - ind["ndvi"], equal_nan=True)
    c, e = features.glcm(b[3])
    assert c.shape == e.shape == (20, 20) and np.all(e >= 0)
    flat_c, flat_e = features.glcm(np.full((20, 20), 0.2, "float32"))
    assert np.allclose(flat_c, 0) and np.allclose(flat_e, 0, atol=1e-5)


def test_sampling_and_training_reproducible():
    rng = np.random.default_rng(1)
    F = rng.normal(size=(19, 40, 40)).astype("float32")
    lab = (F[6] > 0).astype("uint8"); lab[:2] = 255
    X1, y1 = model.sample_points(lab, F, per_class=200, seed=3)
    X2, y2 = model.sample_points(lab, F, per_class=200, seed=3)
    assert np.array_equal(X1, X2) and set(np.unique(y1)) == {0, 1}
    rf_a, rf_b = model.train(X1, y1, n_jobs=1), model.train(X2, y2, n_jobs=1)
    assert rf_a.n_features_in_ == 18
    P = model.predict(rf_a, F)
    assert P.shape == (2, 40, 40) and np.array_equal(P, model.predict(rf_b, F))


def test_teacher_labels(monkeypatch):
    from odc.geo.geobox import GeoBox
    from odc.geo import BoundingBox
    gb = GeoBox.from_bbox(BoundingBox(0, 0, 90, 60, "EPSG:32634"), crs="EPSG:32634", resolution=30)
    a = np.full((6, 9), 2, "uint8")   # trees everywhere
    a[:3, :3] = 7                     # one fully built cell
    a[3:, 3:5] = 7                    # 6 of 9 built: built-up
    a[:3, 6] = 7                      # 3 of 9 built: mixed, ignored
    monkeypatch.setattr(data, "load_10m_map", lambda *k, **kw: (a, None))
    lab = pipeline.teacher_labels(gb, log=lambda m: None)
    assert lab.tolist() == [[1, 2, 255], [2, 1, 2]]


def test_pretrained_models_load():
    for name in pipeline.PRETRAINED:
        rf, card = model.load(name)
        assert rf.n_features_in_ == 18 and card["features"] == features.NAMES[:18]


def test_sdg_rates_and_cells():
    import math
    import geopandas as gpd
    from affine import Affine
    from shapely.geometry import box
    from landcoverrewind import population
    r = population.rates(100.0, 120.0, 1000.0, 1100.0, 10)
    assert math.isclose(r["lcr"], 0.02) and math.isclose(r["pgr"], math.log(1.1) / 10)
    assert r["status"] == "ok" and math.isclose(r["lcrpgr"], 0.02 / (math.log(1.1) / 10))
    assert population.rates(100.0, 120.0, 1000.0, 900.0, 10)["status"] == "population decline"
    assert population.rates(100.0, 120.0, 1000.0, 1005.0, 10)["status"] == "population stable"
    # 60 x 60 pixels of 30 m = two 900 m cells side by side (each 30 x 30 pixels)
    tr = Affine(30, 0, 0, 0, -30, 1800)
    area = np.zeros((60, 60), bool); area[:30, :] = True
    B = {2010: np.zeros((60, 60), bool), 2020: np.zeros((60, 60), bool)}
    B[2010][:10, :10] = True; B[2020][:10, :20] = True
    pop = gpd.GeoDataFrame(dict(pop0=[1000.0, 500.0], pop1=[1100.0, 400.0]),
                           geometry=[box(0, 900, 900, 1800), box(900, 900, 1800, 1800)], crs="EPSG:2180")
    cells, s = population.sdg_11_3_1(B, area, tr, "EPSG:2180", pop, (2010, 2020))
    assert len(cells) == 2 and s["cells_full"] == 2
    assert math.isclose(cells.built_t0_ha[0], 9.0) and math.isclose(cells.built_t1_ha[0], 18.0)
    assert math.isclose(cells.lcr[0], 0.1) and cells.status[1] == "no built-up or population at t0"
    assert s["population_t0"] == 1500 and s["population_t1"] == 1500 and s["status"] == "population stable"
    half = population.built_at(B, 2015)
    assert math.isclose(float(half.sum()), 150.0)


def _grid(dx=0.0):
    import geopandas as gpd
    from shapely.geometry import box
    cells = [box(dx + i * 1000, j * 1000, dx + (i + 1) * 1000, (j + 1) * 1000) for j in range(2) for i in range(2)]
    return gpd.GeoDataFrame(dict(code=["a", "b", "c", "d"], pop0=[500.0] * 4, pop1=[600.0] * 4), geometry=cells, crs="EPSG:2180")


def test_sdg_cover_shifted_grid_and_area_geometry():
    from affine import Affine
    from shapely.geometry import box
    from landcoverrewind import population
    tr = Affine(30, 0, -300, 0, -30, 2300)      # 30 m raster not aligned with the 1 km grid shifted by 15 m
    H, W = 90, 90
    area = np.ones((H, W), bool)
    B = {2010: np.zeros((H, W), bool), 2020: np.ones((H, W), bool)}
    g = _grid(15.0)
    _, s_px = population.sdg_11_3_1(B, area, tr, "EPSG:2180", g, (2010, 2020))
    _, s_geom = population.sdg_11_3_1(B, area, tr, "EPSG:2180", g, (2010, 2020), area_geom=box(-300, -400, 2400, 2300))
    assert s_px["cells_full"] == 4 and s_geom["cells_full"] == 4
    assert s_geom["population_t0"] == 2000 and s_px["population_t0"] == 2000


def test_read_population_two_files_and_run_sdg(tmp_path):
    import zipfile
    from affine import Affine
    from odc.geo.geobox import GeoBox
    from landcoverrewind import population, pipeline
    g = _grid()
    g[["code", "pop0", "geometry"]].rename(columns={"pop0": "tot"}).to_file(tmp_path / "p0.gpkg")
    g[["code", "pop1", "geometry"]].rename(columns={"pop1": "tot"}).to_file(tmp_path / "p1.gpkg")
    pop = population.read_population([tmp_path / "p0.gpkg", tmp_path / "p1.gpkg"], ["tot", "tot"], "code")
    assert list(pop.pop0) == [500.0] * 4 and list(pop.pop1) == [600.0] * 4
    tr = Affine(30, 0, 0, 0, -30, 1980); H = W = 66
    B = {2010: np.zeros((H, W), bool), 2020: np.zeros((H, W), bool)}
    B[2010][:5, :5] = True; B[2020][:10, :10] = True
    zipfile.ZipFile(tmp_path / "results.zip", "w").close()
    res = dict(B=B, area=np.ones((H, W), bool), geobox=GeoBox((H, W), tr, "EPSG:2180"), out_dir=tmp_path)
    cells, s = pipeline.run_sdg(res, [tmp_path / "p0.gpkg", tmp_path / "p1.gpkg"], ["tot", "tot"], (2010, 2020), "code")
    assert (tmp_path / "sdg_11_3_1.png").exists() and "sdg_11_3_1_cells.gpkg" in zipfile.ZipFile(tmp_path / "results.zip").namelist()
    assert s["status"] == "ok" and s["lcrpgr"] > 0


def test_sdg_cover_grid_beyond_raster():
    """Without an area outline, cells extending beyond the raster get a partial share and areal weighting."""
    from affine import Affine
    from landcoverrewind import population
    tr = Affine(30, 0, 0, 0, -30, 1500)          # 1.5 x 1.5 km raster, 1 km grid of four cells
    area = np.ones((50, 50), bool)
    B = {2010: np.zeros((50, 50), bool), 2020: np.ones((50, 50), bool)}
    g = _grid(0.0).assign(pop0=1000.0, pop1=1000.0)
    cells, s = population.sdg_11_3_1(B, area, tr, "EPSG:2180", g, (2010, 2020))
    assert s["population_t0"] == 2250 and s["cells_full"] == 1
    assert sorted(round(c, 2) for c in cells.cover) == [0.25, 0.5, 0.5, 1.0]


def test_check_crs_requires_projected_metres():
    import pytest
    from landcoverrewind import data
    data.check_crs("EPSG:2180"); data.check_crs("EPSG:32634")
    for bad in ("EPSG:4326", "EPSG:3857"):
        with pytest.raises(ValueError):
            data.check_crs(bad)


def test_accuracy_change_map_and_allocation():
    from landcoverrewind import accuracy as A
    b0 = np.array([[0, 1], [0, 0]], bool); b1 = np.array([[1, 1], [0, 0]], bool)
    m = A.change_map(b0, b1)
    assert m.tolist() == [[2, 1], [0, 0]]
    n = A.allocate({0: 9000, 1: 900, 2: 100}, 600, 100)
    assert n[2] == 100 and n[1] >= 100 and sum(n.values()) <= 600 + 2


def test_accuracy_estimator_unbiased_and_covers():
    """Stratified estimator recovers the true area of new built-up land; the 95% CI covers it in most draws."""
    from affine import Affine
    from landcoverrewind import accuracy as A
    rng = np.random.default_rng(7)
    ref0 = rng.random((200, 200)) < 0.3; ref1 = ref0 | (rng.random((200, 200)) < 0.05)
    b0 = ref0 ^ (rng.random((200, 200)) < 0.05); b1 = (b0 | ref1) ^ (rng.random((200, 200)) < 0.04); b1 |= b0
    m, r = A.change_map(b0, b1), A.change_map(ref0, ref1)
    counts = A.class_counts(m); true = (r == 2).sum() * 0.09
    est, cover = [], 0
    for s in range(60):
        pts = A.draw_sample(m, Affine.identity(), A.allocate(counts, 600, 100), seed=s)
        c = A.estimate([p["map_class"] for p in pts], [int(r[p["row"], p["col"]]) for p in pts], counts)["classes_detail"][2]
        est.append(c["adjusted_area_ha"]); cover += abs(c["adjusted_area_ha"] - true) <= c["adjusted_area_ci95_ha"]
    assert abs(np.mean(est) - true) / true < 0.05
    assert cover / 60 >= 0.85
    assert (m == 2).sum() * 0.09 > 1.5 * true  # the map itself overestimates new built-up land


def test_multiscale_agreement():
    from landcoverrewind import accuracy as A
    a = np.zeros((6, 6), bool); r = np.zeros((6, 6), bool)
    a[0, 0] = True; r[0, 1] = True  # one-pixel shift
    out = A.multiscale_agreement(a, r, sizes=(1, 3))
    assert out[1] == 0.0 and out[3] == 1.0 and out["area"] == 1.0
