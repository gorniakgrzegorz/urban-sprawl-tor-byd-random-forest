"""Zapisuje punkty uczące modeli rf_torbyd_2025 (te same losowania co w trenuj_model_torbyd.py).

Użycie (z folderu aplikacja, po trenuj_model_torbyd.py): python narzedzia/zapisz_punkty.py tor_v3_rf_4kl_2025.tif byd_v3_rf_4kl_2025.tif
"""
import sys, pathlib, numpy as np, rasterio
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from landcoverrewind import model
D = []
for path in sys.argv[1:3]:
    F = np.load(f"cache_uczenia/{pathlib.Path(path).stem}_cechy2025.npy")
    with rasterio.open(path) as s:
        lab = s.read(1)
    D.append((F, np.where(lab == 0, 255, lab)))
for nazwa, mapuj in (("rf_torbyd_2025_binarny", lambda l: np.where(l == 255, 255, (l == 1).astype("uint8"))),
                     ("rf_torbyd_2025_4klasy", lambda l: l)):
    Xs, ys = [], []
    for k, (F, lab) in enumerate(D):
        X, y = model.losuj_punkty(mapuj(lab), F, na_klase=1500 // len(D), ziarno=42 + k)
        Xs.append(X); ys.append(y)
    X, y = np.vstack(Xs).astype("float32"), np.concatenate(ys).astype("uint8")
    np.savez_compressed(f"modele/{nazwa}_punkty.npz", X=X, y=y)
    rf, _ = model.wczytaj(nazwa); rf2 = model.ucz(X, y)
    print(nazwa, X.shape, "zgodność predykcji z zapisanym modelem:", (rf.predict(model._sel(X, 18)) == rf2.predict(model._sel(X, 18))).mean())
