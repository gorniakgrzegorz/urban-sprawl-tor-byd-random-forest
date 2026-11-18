"""Odtworzenie modelu wstępnie wytrenowanego `rf_torbyd_2025` (dla przejrzystości; użytkownik nie musi go uruchamiać).

Etykiety: mapy 2025 projektu (Toruń i Bydgoszcz, 30 m, EPSG:2180; klasa 1 = zabudowa serii A,
2 = lasy i drzewa, 3 = wody, 4 = pozostałe), pochodzące z transferu etykiet Dynamic World 2025.
Cechy: 19 cech epoki 2025 (sceny 2024–2026) z Planetary Computer, liczone kodem aplikacji.
Uczone są dwa modele: binarny (zabudowa / reszta) i czteroklasowy, na 18 cechach (bez amplitudy NDVI).

Użycie (z folderu aplikacja): python narzedzia/trenuj_model_torbyd.py tor_v3_rf_4kl_2025.tif byd_v3_rf_4kl_2025.tif
(pliki etykiet: rekord Zenodo 10.5281/zenodo.24155226)
"""
import sys, json, pathlib, time
import numpy as np, rasterio
from odc.geo.geobox import GeoBox
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from landcoverrewind import cechy, model

CACHE = pathlib.Path("cache_uczenia"); CACHE.mkdir(exist_ok=True)


def dane_miasta(path):
    with rasterio.open(path) as s:
        lab = s.read(1); gb = GeoBox(s.shape, s.transform, s.crs)
    f = CACHE / (pathlib.Path(path).stem + "_cechy2025.npy")
    if f.exists():
        F = np.load(f)
    else:
        F, info = cechy.cechy_epoki(2025, gb, log=lambda m: print(m, flush=True))
        np.save(f, F); (CACHE / (f.stem + ".json")).write_text(json.dumps(info))
    lab = np.where(lab == 0, 255, lab)
    return F, lab


def main(paths):
    t0 = time.time(); D = [dane_miasta(p) for p in paths]
    wyn = {}
    for nazwa, mapuj in (("rf_torbyd_2025_binarny", lambda l: np.where(l == 255, 255, (l == 1).astype("uint8"))),
                         ("rf_torbyd_2025_4klasy", lambda l: l)):
        Xs, ys = [], []
        for k, (F, lab) in enumerate(D):
            X, y = model.losuj_punkty(mapuj(lab), F, na_klase=1500 // len(D), ziarno=42 + k)
            Xs.append(X); ys.append(y)
        rf = model.ucz(np.vstack(Xs), np.concatenate(ys))
        # test przeniesienia przestrzennego: model uczony na jednym mieście, oceniany na drugim
        transfer = {}
        for a in range(len(D)):
            b = 1 - a
            Xa, ya = model.losuj_punkty(mapuj(D[a][1]), D[a][0], na_klase=1500, ziarno=7)
            ra = model.ucz(Xa, ya)
            Xb, yb = model.losuj_punkty(mapuj(D[b][1]), D[b][0], na_klase=5000, ziarno=8)
            if nazwa.endswith("binarny"):
                pred = (ra.predict_proba(model._sel(Xb, ra.n_features_in_))[:, 1] >= 0.65).astype(int)
            else:
                pred = ra.predict(model._sel(Xb, ra.n_features_in_))
            transfer[f"{pathlib.Path(paths[a]).stem[:3]}->{pathlib.Path(paths[b]).stem[:3]}"] = float((pred == yb).mean())
        karta = dict(nazwa=nazwa, data="2026-11-17", epoka_uczenia=2025, okno_lat=[2024, 2026],
                     etykiety="mapy 2025 projektu Toruń/Bydgoszcz (seria A i model czteroklasowy, transfer z Dynamic World 2025)",
                     punkty_na_klase=1500, ziarno=42, drzewa=300, cechy_na_podzial=4, min_lisc=1,
                     prog_zabudowy=0.65 if nazwa.endswith("binarny") else None,
                     prog_kalibracja="epoka rozwojowa 2005: F1 serii 2005 względem serii A projektu równa dla progów 0,55 i 0,65 (87% Toruń, 88% Bydgoszcz), niższa dla 0,75; wybrano 0,65 (mniejsza różnica powierzchni)" if nazwa.endswith("binarny") else None,
                     uwaga_cechy="amplituda NDVI pominięta: niestabilna między epokami (test Grudziądz 1985 i Toruń/Bydgoszcz)",
                     dane="Microsoft Planetary Computer, landsat-c2-l2", trafnosc_transferu_miedzy_miastami=transfer)
        model.zapisz(rf, nazwa, karta); wyn[nazwa] = transfer
        print(nazwa, "OOB", round(rf.oob_score_, 4), transfer, flush=True)
    print("czas", round(time.time() - t0), "s")


if __name__ == "__main__":
    main(sys.argv[1:])
