"""Model Random Forest: uczenie, zapis, wczytanie i predykcja.

Hiperparametry jak w modelu projektu (GEE smileRandomForest): 300 drzew, 4 cechy na podział,
minimalna liczebność liścia 1, ziarno 42, 1500 punktów na klasę.
"""
from __future__ import annotations
import json, pathlib
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from .cechy import NAZWY

KATALOG = pathlib.Path(__file__).resolve().parent.parent / "modele"
# Model używa 18 z 19 cech: amplituda NDVI (cecha 19) okazała się niestabilna między epokami
# (zawyżona w epoce 1985, co zaniżało wykrycia zabudowy), dlatego pominięto ją przy uczeniu.
IDX = list(range(18))


def _sel(X, n):
    """Wybiera kolumny cech zgodne z modelem (n = liczba cech, na których model uczono)."""
    return X[:, IDX] if (X.shape[1] == 19 and n == 18) else X


def losuj_punkty(etykiety: np.ndarray, F: np.ndarray, na_klase=1500, ziarno=42, maska=None):
    """Losowanie warstwowe: po `na_klase` pikseli z każdej klasy (bez braków danych w cechach)."""
    rng = np.random.default_rng(ziarno)
    ok = np.all(np.isfinite(F), axis=0) & (etykiety != 255)
    if maska is not None:
        ok &= maska
    X, y = [], []
    for k in np.unique(etykiety[ok]):
        idx = np.flatnonzero(ok & (etykiety == k))
        wyb = rng.choice(idx, size=min(na_klase, idx.size), replace=False)
        X.append(F.reshape(F.shape[0], -1)[:, wyb].T); y.append(np.full(wyb.size, k))
    return np.vstack(X), np.concatenate(y)


def ucz(X, y, ziarno=42):
    rf = RandomForestClassifier(n_estimators=300, max_features=4, min_samples_leaf=1,
                                n_jobs=-1, random_state=ziarno, oob_score=True)
    rf.fit(X[:, IDX] if X.shape[1] == 19 else X, y)
    return rf


def zapisz(rf, nazwa: str, karta: dict, katalog=None):
    kat = pathlib.Path(katalog) if katalog else KATALOG
    kat.mkdir(exist_ok=True, parents=True)
    joblib.dump(rf, kat / f"{nazwa}.joblib", compress=3)
    karta = dict(karta, cechy=[NAZWY[i] for i in IDX] if rf.n_features_in_ == 18 else NAZWY, klasy=[int(c) for c in rf.classes_],
                 oob=float(getattr(rf, "oob_score_", np.nan)))
    (kat / f"{nazwa}.json").write_text(json.dumps(karta, ensure_ascii=False, indent=1), encoding="utf-8")


def wczytaj(nazwa_lub_sciezka: str):
    """Wczytuje model; gdy plik .joblib nie pasuje do wersji scikit-learn, odtwarza model z zapisanych punktów uczących."""
    p = pathlib.Path(nazwa_lub_sciezka)
    if not p.suffix:
        p = KATALOG / f"{nazwa_lub_sciezka}.joblib"
    karta = json.loads(p.with_suffix(".json").read_text(encoding="utf-8")) if p.with_suffix(".json").exists() else {}
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error", category=UserWarning)
            return joblib.load(p), karta
    except Exception:
        pkt = p.with_name(p.stem + "_punkty.npz")
        d = np.load(pkt)
        return ucz(d["X"], d["y"], int(karta.get("ziarno", 42))), karta


def przewiduj(rf, F: np.ndarray, blok=200_000):
    """Prawdopodobieństwa klas (n_klas, H, W); piksele bez danych = NaN."""
    C, H, W = F.shape
    X = _sel(F.reshape(C, -1).T, rf.n_features_in_)
    ok = np.all(np.isfinite(X), axis=1)
    P = np.full((X.shape[0], len(rf.classes_)), np.nan, "float32")
    idx = np.flatnonzero(ok)
    for i in range(0, idx.size, blok):
        j = idx[i:i + blok]
        P[j] = rf.predict_proba(X[j])
    return P.T.reshape(len(rf.classes_), H, W)
