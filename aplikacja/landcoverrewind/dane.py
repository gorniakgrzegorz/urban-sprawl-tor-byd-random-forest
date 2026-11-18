"""Dostęp do danych bez konta: katalog STAC Microsoft Planetary Computer.

Kolekcje (wszystkie otwarte, odczyt anonimowy, podpis SAS nadawany automatycznie):
  landsat-c2-l2        Landsat 4/5 TM, 7 ETM+, 8/9 OLI, Collection 2 Level 2 (odbicie powierzchniowe)
  io-lulc-annual-v02   Impact Observatory / Esri, roczne mapy pokrycia terenu 10 m (2017–2024)
"""
from __future__ import annotations
import numpy as np
import pystac_client
import planetary_computer as pc
from odc.stac import load as stac_load
from odc.geo.geobox import GeoBox
from odc.geo.geom import Geometry

import os, dask
os.environ.setdefault("GDAL_HTTP_MULTIPLEX", "YES")
os.environ.setdefault("GDAL_HTTP_VERSION", "2")
os.environ.setdefault("VSI_CACHE", "TRUE")
os.environ.setdefault("GDAL_CACHEMAX", "512")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.TIF,.tiff")
os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
dask.config.set(scheduler="threads", num_workers=int(os.environ.get("URBANRF_WATKI", 8)))

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
BANDS = ["blue", "green", "red", "nir08", "swir16", "swir22"]
# okresy pracy sensorów przyjęte w projekcie (jak w notatniku GEE)
SENSOR_YEARS = {"landsat-4": (1982, 1993), "landsat-5": (1984, 2012), "landsat-7": (2000, 2012),
                "landsat-8": (2013, 2100), "landsat-9": (2022, 2100)}
# harmonizacja ETM+ (i TM, przybliżenie) do OLI: Roy i in. 2016, doi:10.1016/j.rse.2015.12.024
ROY_SLOPE = np.array([0.8474, 0.8483, 0.9047, 0.8462, 0.8937, 0.9071])
ROY_OFFSET = np.array([0.0003, 0.0088, 0.0061, 0.0412, 0.0254, 0.0172])


def katalog():
    return pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace)


def siatka(geom_4326: Geometry, crs: str | None = None, res: int = 30) -> GeoBox:
    """Siatka 30 m dla obszaru; domyślnie strefa UTM środka obszaru, węzły w wielokrotnościach 30 m."""
    if crs is None:
        c = geom_4326.centroid.coords[0]
        zone = int((c[0] + 180) // 6) + 1
        crs = f"EPSG:{32600 + zone if c[1] >= 0 else 32700 + zone}"
    g = geom_4326.to_crs(crs)
    x0, y0, x1, y1 = g.boundingbox
    x0, y0 = np.floor(x0 / res) * res, np.floor(y0 / res) * res
    x1, y1 = np.ceil(x1 / res) * res, np.ceil(y1 / res) * res
    from odc.geo.geobox import GeoBox as GB
    from odc.geo import BoundingBox
    return GB.from_bbox(BoundingBox(x0, y0, x1, y1, crs), crs=crs, resolution=res)


def sceny(geobox: GeoBox, lata: tuple[int, int], miesiace: tuple[int, int] | None, max_chmur: int = 70):
    """Sceny Landsat C2 L2 dla siatki, lat [a, b] i miesięcy [m1, m2] (włącznie)."""
    bbox = geobox.geographic_extent.boundingbox
    s = katalog().search(collections=["landsat-c2-l2"], bbox=list(bbox),
                         datetime=f"{lata[0]}-01-01/{lata[1]}-12-31",
                         query={"eo:cloud_cover": {"lt": max_chmur}})
    out = []
    for it in s.items():
        p = it.properties.get("platform", "")
        y, m = it.datetime.year, it.datetime.month
        if p not in SENSOR_YEARS or not (SENSOR_YEARS[p][0] <= y <= SENSOR_YEARS[p][1]):
            continue
        if miesiace and not (miesiace[0] <= m <= miesiace[1]):
            continue
        out.append(it)
    return out


def _wczytaj(items, geobox, bands, chunks):
    return stac_load(items, bands=bands, geobox=geobox, groupby="solar_day",
                     chunks=chunks, resampling={"qa_pixel": "nearest", "*": "bilinear"},
                     fail_on_error=False)


def odbicie(items, geobox, chunks=None):
    """Zwraca xarray (time, y, x) z sześcioma pasmami odbicia OLI-równoważnego, po masce chmur.

    Maska QA_PIXEL: bity 0–5 (wypełnienie, chmura rozszerzona, cirrus, chmura, cień, śnieg).
    Skalowanie Collection 2: SR = DN · 2,75e-5 − 0,2. TM/ETM+ harmonizowane do OLI (Roy i in. 2016).
    """
    import xarray as xr
    chunks = chunks or {"x": geobox.shape[1], "y": geobox.shape[0]}
    grupy = {"oli": [i for i in items if i.properties["platform"] in ("landsat-8", "landsat-9")],
             "tm": [i for i in items if i.properties["platform"] not in ("landsat-8", "landsat-9")]}
    parts = []
    for k, its in grupy.items():
        if not its:
            continue
        ds = _wczytaj(its, geobox, BANDS + ["qa_pixel"], chunks)
        qa = ds["qa_pixel"]
        clear = (qa & 0b111111) == 0
        for j, b in enumerate(BANDS):
            v = ds[b].where(ds[b] > 0).astype("float32") * 2.75e-5 - 0.2
            if k == "tm":
                v = v * ROY_SLOPE[j] + ROY_OFFSET[j]
            ds[b] = v.where(clear & (v > -0.05) & (v < 1.2))
        parts.append(ds[BANDS])
    if not parts:
        raise RuntimeError("Brak scen Landsat dla zadanych lat i miesięcy")
    return xr.concat(parts, dim="time").sortby("time")


def mapa_10m(kolekcja: str, rok: int, geobox: GeoBox, asset: str):
    """Mapa pokrycia 10 m (IO LULC lub ESA WorldCover) jako kod klas na siatce 10 m zgodnej z obszarem."""
    bbox = geobox.geographic_extent.boundingbox
    s = katalog().search(collections=[kolekcja], bbox=list(bbox), datetime=f"{rok}-01-01/{rok}-12-31")
    items = list(s.items())
    if not items:
        raise RuntimeError(f"Brak danych {kolekcja} {rok} dla obszaru")
    gb10 = GeoBox.from_bbox(geobox.boundingbox, crs=geobox.crs, resolution=10)
    ds = stac_load(items, bands=[asset], geobox=gb10, resampling="nearest", groupby="solar_day")
    a = ds[asset].max("time").values if "time" in ds.dims else ds[asset].values
    return a.astype("uint8"), gb10
