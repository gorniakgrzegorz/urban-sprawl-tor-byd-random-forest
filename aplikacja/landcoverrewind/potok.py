"""Cały przebieg dla obszaru wskazanego przez użytkownika."""
from __future__ import annotations
import json, pathlib, time, zipfile, csv, hashlib
import numpy as np
import rasterio
from . import dane, cechy, model, seria, wizualizacja as wiz, EPOCHS

IO2KL = {1: 3, 2: 2, 4: 3, 5: 4, 7: 1, 8: 4, 11: 4}  # IO LULC → 1 zabudowa, 2 lasy i drzewa, 3 wody, 4 pozostałe


def etykiety_nauczyciela(geobox, rok=2024, log=print):
    """Etykiety 30 m z mapy IO LULC (Sentinel-2, 10 m): zabudowa, gdy ≥ 5 z 9 pikseli 10 m; inaczej klasa dominująca."""
    a, _ = dane.mapa_10m("io-lulc-annual-v02", rok, geobox, "data")
    H, W = geobox.shape
    a = a[:H * 3, :W * 3]
    if a.shape != (H * 3, W * 3):
        a = np.pad(a, ((0, H * 3 - a.shape[0]), (0, W * 3 - a.shape[1])))
    k = np.full(a.shape, 255, "uint8")
    for src, dst in IO2KL.items():
        k[a == src] = dst
    blk = k.reshape(H, 3, W, 3).transpose(0, 2, 1, 3).reshape(H, W, 9)
    cnt = np.stack([(blk == c).sum(-1) for c in (1, 2, 3, 4)], -1)
    lab = (cnt.argmax(-1) + 1).astype("uint8")
    lab[cnt[..., 0] >= 5] = 1
    lab[(cnt[..., 0] > 0) & (cnt[..., 0] < 5)] = 255  # piksele mieszane (1–4 z 9 pikseli zabudowy) pomijane
    lab[cnt.sum(-1) < 5] = 255
    log(f"  etykiety nauczyciela IO LULC {rok}: " + ", ".join(f"{c}: {(lab == c).sum()}" for c in (1, 2, 3, 4)))
    return lab


def zapisz_tif(sciezka, a, geobox, dtype, nodata=None):
    prof = dict(driver="GTiff", height=a.shape[0], width=a.shape[1], count=1, dtype=dtype, crs=str(geobox.crs),
                transform=geobox.affine, compress="deflate", nodata=nodata)
    with rasterio.open(sciezka, "w", **prof) as d:
        d.write(a.astype(dtype), 1)


def _zaokr(rows, nd=2):
    """Zaokrąglenie liczb do zapisu CSV; brak wartości jako pusta komórka."""
    out = []
    for r in rows:
        q = {}
        for k, v in r.items():
            if isinstance(v, float):
                q[k] = "" if np.isnan(v) else round(v, nd)
            else:
                q[k] = v
        out.append(q)
    return out


def uruchom(geom, epoki=None, tryb="gotowy", prog=0.65, katalog="wyniki", crs=None, max_chmur=70, log=print, postep=None):
    """postep(ułamek 0–1, opis kroku) pozwala interfejsowi pokazać pasek postępu."""
    t0 = time.time()
    epoki = sorted(epoki or EPOCHS)
    n_krokow = len(epoki) + 4 + (1 if tryb == "lokalny" else 0)
    stan = {"k": 0}

    def krok(opis):
        if postep:
            postep(min(stan["k"] / n_krokow, 0.99), opis)
        stan["k"] += 1
    krok("Przygotowanie siatki obliczeniowej dla wskazanego obszaru")
    out = pathlib.Path(katalog); out.mkdir(parents=True, exist_ok=True)
    cache = out / "cache"; cache.mkdir(exist_ok=True)
    gb = dane.siatka(geom, crs)
    obszar = seria.maska_obszaru(geom, gb)
    km2 = obszar.sum() * 900 / 1e6
    log(f"Obszar: {km2:.1f} km², siatka {gb.shape[1]} × {gb.shape[0]} pikseli 30 m, układ {gb.crs}")

    klucz = hashlib.md5(f"{gb.crs}|{tuple(gb.affine)}|{gb.shape}|{max_chmur}".encode()).hexdigest()[:10]

    def F_epoki(t):
        # nazwa pliku zawiera skrót siatki i limitu chmur, więc inny obszar nie użyje cudzych cech
        f = cache / f"cechy_{t}_{klucz}.npy"
        if f.exists():
            return np.load(f), json.loads(f.with_suffix(".json").read_text())
        F, info = cechy.cechy_epoki(t, gb, log, max_chmur)
        np.save(f, F); f.with_suffix(".json").write_text(json.dumps(info))
        return F, info

    if tryb == "lokalny":
        krok("Uczenie modelu na Twoim obszarze (mapa pokrycia terenu 2024 i zdjęcia 2024–2026)")
    if tryb == "gotowy":
        rf2, karta2 = model.wczytaj("rf_torbyd_2025_binarny")
        rf4, _ = model.wczytaj("rf_torbyd_2025_4klasy")
        log("Model: rf_torbyd_2025 (uczony na mapach 2025 Torunia i Bydgoszczy)")
    else:
        log("Model: uczenie lokalne na etykietach IO LULC 2024 i cechach epoki 2025")
        F25, _ = F_epoki(2025)
        lab = etykiety_nauczyciela(gb, 2024, log)
        X, y = model.losuj_punkty(np.where(lab == 255, 255, (lab == 1).astype("uint8")), F25, maska=obszar)
        rf2 = model.ucz(X, y)
        X4, y4 = model.losuj_punkty(lab, F25, maska=obszar)
        rf4 = model.ucz(X4, y4)
        model.zapisz(rf2, "model_lokalny_binarny", dict(nazwa="model_lokalny_binarny", etykiety="IO LULC 2024", epoka_uczenia=2025), katalog=out.resolve(), pominiete=[t for t in epoki if t not in P])
        log(f"  OOB: binarny {rf2.oob_score_:.3f}, czteroklasowy {rf4.oob_score_:.3f}")

    P, K4, opis = {}, {}, []
    i_bud = list(rf2.classes_).index(1)
    for i, t in enumerate(epoki, 1):
        krok(f"Epoka {t} ({i} z {len(epoki)}): pobieranie zdjęć satelitarnych z lat {t - 1}–{t + 1}, usuwanie chmur i rozpoznawanie zabudowy")
        try:
            F, info = F_epoki(t)
        except Exception as e:
            log(f"  epoka {t} pominięta: {e}"); continue
        P[t] = model.przewiduj(rf2, F)[i_bud]
        pr4 = model.przewiduj(rf4, F)
        cl = np.array(rf4.classes_)
        nb = [j for j, c in enumerate(cl) if c != 1]
        K4[t] = cl[nb][np.nanargmax(np.nan_to_num(pr4[nb], nan=-1), axis=0)].astype("uint8")
        K4[t][np.isnan(pr4[0])] = 0  # brak danych
        opis.append(info)
        zapisz_tif(out / f"p_zabudowy_{t}.tif", np.where(np.isnan(P[t]), 255, np.round(P[t] * 100)), gb, "uint8", 255)
    if not P:
        raise RuntimeError("Nie udało się policzyć żadnej epoki")
    krok("Porządkowanie serii map: zabudowa raz wykryta pozostaje zabudową")
    log("Więz zasięgu (IO LULC 2017 i 2024) i kumulacja serii…")
    M = seria.maska_zasiegu(gb, log)
    if not M.any():
        raise RuntimeError("Nie wczytano maski zasięgu IO LULC albo w obszarze nie ma zabudowy według IO LULC 2017 i 2024")
    B = seria.seria_A(P, prog, M)
    for t in B:
        K4[t][B[t]] = 1
        zapisz_tif(out / f"seria_A_{t}.tif", np.where(obszar, B[t], 255), gb, "uint8", 255)
        zapisz_tif(out / f"pokrycie_4klasy_{t}.tif", np.where(obszar, K4[t], 0), gb, "uint8", 0)
    fd = seria.pierwsza_detekcja(B)
    # w obszarze: epoka pierwszej detekcji albo 0 (nigdy niezabudowany); poza obszarem −1 (brak danych)
    zapisz_tif(out / "epoka_pierwszej_detekcji.tif", np.where(obszar, np.where(fd < 0, 0, fd), -1), gb, "int16", -1)
    tab = seria.tabela(B, obszar, baza=1990 if 1990 in B else None)
    fr = seria.formy(B, obszar)
    krok("Liczenie wskaźników i zapis map GeoTIFF oraz tabel CSV")
    for nazwa, rows in (("wskazniki_epok.csv", _zaokr(tab)), ("formy_przyrostu.csv", _zaokr(fr, 1)), ("dane_wejsciowe.csv", opis)):
        if not rows:  # np. formy przyrostu przy jednej epoce
            continue
        with open(out / nazwa, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    ep = sorted(B)
    krok("Rysowanie map, animacji i wykresu")
    wiz.mapa_detekcji(fd, obszar, ep, out / "mapa_epoka_detekcji.png")
    wiz.animacja(B, obszar, out / "animacja_zabudowa.gif")
    wiz.animacja(B, obszar, out / "animacja_pokrycie.gif", kl4=K4)
    wiz.wykres_powierzchni(tab, out / "wykres_powierzchni.png")
    meta = dict(obszar_km2=round(float(km2), 2), crs=str(gb.crs), epoki=ep, tryb=tryb, prog=prog,
                sceny={o["epoka"]: o.get("id_scen", []) for o in opis}, data_obliczen=time.strftime("%Y-%m-%d"),
                czas_s=round(time.time() - t0), zrodlo="Microsoft Planetary Computer (landsat-c2-l2, io-lulc-annual-v02)")
    (out / "metadane.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    with zipfile.ZipFile(out / "wyniki.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in out.iterdir():
            if p.is_file() and p.suffix != ".zip":
                z.write(p, p.name)
    if postep:
        postep(1.0, f"Gotowe w {meta['czas_s']} s")
    log(f"Gotowe w {meta['czas_s']} s: {out.resolve()}")
    return dict(B=B, K4=K4, P=P, tab=tab, formy=fr, opis=opis, obszar=obszar, geobox=gb, katalog=out.resolve(), pominiete=[t for t in epoki if t not in P])
