"""Rebuild the pretrained models rf_torun_bydgoszcz_2025 (for transparency; users do not need to run this).

Labels: 2025 maps of the reference project (Torun and Bydgoszcz, 30 m, EPSG:2180; class 1 = built-up land of
series A, 2 = trees and forest, 3 = water, 4 = other), derived from Dynamic World 2025 label transfer.
Features: the 19 features of epoch 2025 (scenes 2024-2026) from Planetary Computer, computed with this package.
Two models are trained, binary (built-up / other) and four-class, on 18 features (without NDVI amplitude).

Usage (from the application folder):
  python tools/train_pretrained.py tor_v3_rf_4kl_2025.tif byd_v3_rf_4kl_2025.tif
(label rasters: Zenodo record 10.5281/zenodo.24155226)
"""
import sys, json, pathlib, time
import numpy as np, rasterio
from odc.geo.geobox import GeoBox
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from landcoverrewind import features, model

CACHE = pathlib.Path("training_cache"); CACHE.mkdir(exist_ok=True)
TARGETS = (("rf_torun_bydgoszcz_2025_binary", lambda l: np.where(l == 255, 255, (l == 1).astype("uint8"))),
           ("rf_torun_bydgoszcz_2025_4class", lambda l: l))


def city_data(path):
    with rasterio.open(path) as s:
        lab = s.read(1); gb = GeoBox(s.shape, s.transform, s.crs)
    f = CACHE / (pathlib.Path(path).stem + "_features2025.npy")
    if f.exists():
        F = np.load(f)
    else:
        F, info = features.epoch_features(2025, gb, log=lambda m: print(m, flush=True))
        np.save(f, F); (CACHE / (f.stem + ".json")).write_text(json.dumps(info))
    return F, np.where(lab == 0, 255, lab)


def main(paths):
    t0 = time.time(); D = [city_data(p) for p in paths]
    for name, relabel in TARGETS:
        Xs, ys = [], []
        for k, (F, lab) in enumerate(D):
            X, y = model.sample_points(relabel(lab), F, per_class=1500 // len(D), seed=42 + k)
            Xs.append(X); ys.append(y)
        X, y = np.vstack(Xs).astype("float32"), np.concatenate(ys).astype("uint8")
        rf = model.train(X, y)
        np.savez_compressed(model.MODEL_DIR / f"{name}_points.npz", X=X, y=y)
        # spatial transfer test: trained on one city, evaluated on the other
        transfer = {}
        for a in range(len(D)):
            b = 1 - a
            Xa, ya = model.sample_points(relabel(D[a][1]), D[a][0], per_class=1500, seed=7)
            ra = model.train(Xa, ya)
            Xb, yb = model.sample_points(relabel(D[b][1]), D[b][0], per_class=5000, seed=8)
            Xb = model.select_features(Xb, ra.n_features_in_)
            pred = (ra.predict_proba(Xb)[:, 1] >= 0.65).astype(int) if name.endswith("binary") else ra.predict(Xb)
            transfer[f"{pathlib.Path(paths[a]).stem[:3]}->{pathlib.Path(paths[b]).stem[:3]}"] = float((pred == yb).mean())
        card = json.loads((model.MODEL_DIR / f"{name}.json").read_text()) if (model.MODEL_DIR / f"{name}.json").exists() else {}
        card.update(name=name, date=time.strftime("%Y-%m-%d"), cross_city_transfer_accuracy=transfer)
        model.save(rf, name, card)
        print(name, "OOB", round(rf.oob_score_, 4), transfer, flush=True)
    print("time", round(time.time() - t0), "s")


if __name__ == "__main__":
    main(sys.argv[1:])
