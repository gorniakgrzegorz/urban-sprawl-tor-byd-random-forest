"""Account-free data access through the Microsoft Planetary Computer STAC API.

Collections (open, anonymous read, SAS signing handled by the planetary-computer package):
  landsat-c2-l2        Landsat 4/5 TM, 7 ETM+, 8/9 OLI, Collection 2 Level 2 surface reflectance
  io-lulc-annual-v02   Impact Observatory/Esri annual 10 m land use/land cover, maps for 2017-2023
  esa-worldcover       ESA WorldCover 10 m, 2020 and 2021 (optional extent mask)
"""
from __future__ import annotations
import os
import numpy as np
import pyproj
import dask
import pystac_client
import planetary_computer as pc
from odc.stac import load as stac_load
from odc.geo import BoundingBox
from odc.geo.geobox import GeoBox
from odc.geo.geom import Geometry

for _k, _v in {"GDAL_HTTP_MULTIPLEX": "YES", "GDAL_HTTP_VERSION": "2", "VSI_CACHE": "TRUE",
               "GDAL_CACHEMAX": "512", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff",
               "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES", "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
               "GDAL_HTTP_MAX_RETRY": "5", "GDAL_HTTP_RETRY_DELAY": "2"}.items():
    os.environ.setdefault(_k, _v)
THREADS = int(os.environ.get("LCR_THREADS", os.environ.get("URBANRF_WATKI", 8)))
dask.config.set(scheduler="threads", num_workers=THREADS)

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
BANDS = ["blue", "green", "red", "nir08", "swir16", "swir22"]
# Years in which each platform is used (TM until the end of its archive, ETM+ only 2000-2012).
SENSOR_YEARS = {"landsat-4": (1982, 1993), "landsat-5": (1984, 2012), "landsat-7": (2000, 2012),
                "landsat-8": (2013, 2100), "landsat-9": (2022, 2100)}
# ETM+ to OLI OLS coefficients of Roy et al. (2016), doi:10.1016/j.rse.2015.12.024.
# The same coefficients are applied to TM as an approximation (no separate TM-OLI calibration).
ROY_SLOPE = np.array([0.8474, 0.8483, 0.9047, 0.8462, 0.8937, 0.9071])
ROY_OFFSET = np.array([0.0003, 0.0088, 0.0061, 0.0412, 0.0254, 0.0172])
QA_MASK = 0b111111  # QA_PIXEL bits 0-5: fill, dilated cloud, cirrus, cloud, cloud shadow, snow


def catalog():
    return pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace)


LAST_ITEMS = {}  # STAC item ids of the most recent 10 m map loaded per collection (recorded in metadata.json)


def check_crs(crs: str) -> None:
    """The 30 m grid and the areas in hectares require a projected CRS in metres."""
    c = pyproj.CRS.from_user_input(crs)
    if not c.is_projected or c.axis_info[0].unit_name not in ("metre", "meter"):
        raise ValueError(f"{crs} is not a projected coordinate reference system in metres; use e.g. a UTM zone or EPSG:2180")
    method = (c.coordinate_operation.method_name if c.coordinate_operation else "").lower()
    if "mercator" in method and "transverse" not in method:
        raise ValueError(f"{crs} (Mercator) distorts areas strongly; use a UTM zone or a national CRS such as EPSG:2180")


def utm_crs(geom_4326: Geometry) -> str:
    lon, lat = geom_4326.centroid.coords[0]
    zone = int((lon + 180) // 6) + 1
    return f"EPSG:{(32600 if lat >= 0 else 32700) + zone}"


def make_grid(geom_4326: Geometry, crs: str | None = None, res: int = 30) -> GeoBox:
    """30 m grid covering the area, aligned to multiples of the resolution (UTM zone of the centroid by default)."""
    crs = crs or utm_crs(geom_4326)
    check_crs(crs)
    x0, y0, x1, y1 = geom_4326.to_crs(crs).boundingbox
    x0, y0 = np.floor(x0 / res) * res, np.floor(y0 / res) * res
    x1, y1 = np.ceil(x1 / res) * res, np.ceil(y1 / res) * res
    return GeoBox.from_bbox(BoundingBox(x0, y0, x1, y1, crs), crs=crs, resolution=res)


def search_scenes(geobox: GeoBox, years: tuple[int, int], max_cloud: int = 70):
    """Landsat C2 L2 items intersecting the grid for years [a, b], filtered by platform period and scene cloud cover."""
    bbox = list(geobox.geographic_extent.boundingbox)
    search = catalog().search(collections=["landsat-c2-l2"], bbox=bbox,
                              datetime=f"{years[0]}-01-01/{years[1]}-12-31",
                              query={"eo:cloud_cover": {"lt": max_cloud}})
    items = []
    for it in search.items():
        platform, year = it.properties.get("platform", ""), it.datetime.year
        if platform in SENSOR_YEARS and SENSOR_YEARS[platform][0] <= year <= SENSOR_YEARS[platform][1]:
            items.append(it)
    return items


def load_reflectance(items, geobox: GeoBox, bands, pool: int | None = None) -> dict:
    """Cloud-masked, OLI-equivalent reflectance for the requested bands as arrays (time, y, x)."""
    out = {b: [] for b in bands}
    for group in ("oli", "tm"):
        its = [i for i in items if (i.properties["platform"] in ("landsat-8", "landsat-9")) == (group == "oli")]
        if not its:
            continue
        ds = stac_load(its, bands=list(bands) + ["qa_pixel"], geobox=geobox, groupby="solar_day", pool=pool or THREADS,
                       resampling={"qa_pixel": "nearest", "*": "bilinear"}, fail_on_error=False)
        clear = (ds["qa_pixel"].values & QA_MASK) == 0
        for b in bands:
            j = BANDS.index(b)
            raw = ds[b].values
            v = raw.astype("float32") * 2.75e-5 - 0.2  # Collection 2 Level 2 scaling
            if group == "tm":
                v = v * ROY_SLOPE[j] + ROY_OFFSET[j]
            v[(raw == 0) | ~clear | (v < -0.05) | (v > 1.2)] = np.nan
            out[b].append(v)
        del ds, clear
    return {b: (np.concatenate(v) if v else None) for b, v in out.items()}


def load_10m_map(collection: str, year: int, geobox: GeoBox, asset: str = "data"):
    """Categorical 10 m map (IO LULC or ESA WorldCover) on a 10 m grid nested in the 30 m grid."""
    items = list(catalog().search(collections=[collection], bbox=list(geobox.geographic_extent.boundingbox),
                                  datetime=f"{year}-01-01/{year}-12-31").items())
    # keep only the map of the requested year: the annual items end on 1 January of the next year, so a search
    # for year Y also returns the item of year Y-1 (and a search for a year after the last map returns that map)
    items = [it for it in items if str(it.properties.get("start_datetime") or it.datetime.isoformat())[:4] == str(year)]
    if not items:
        raise RuntimeError(f"No {collection} map for {year} in this area")
    LAST_ITEMS[collection] = sorted(it.id for it in items)
    gb10 = GeoBox.from_bbox(geobox.boundingbox, crs=geobox.crs, resolution=10)
    ds = stac_load(items, bands=[asset], geobox=gb10, resampling="nearest", groupby="solar_day")
    a = ds[asset].max("time").values if "time" in ds.dims else ds[asset].values
    return a.astype("uint8"), gb10


def to_blocks(a10: np.ndarray, shape30: tuple[int, int]) -> np.ndarray:
    """Reshape a 10 m array to (H, W, 9): the nine 10 m cells inside each 30 m cell (padded with 0)."""
    H, W = shape30
    a = a10[:H * 3, :W * 3]
    if a.shape != (H * 3, W * 3):
        a = np.pad(a, ((0, H * 3 - a.shape[0]), (0, W * 3 - a.shape[1])))
    return a.reshape(H, 3, W, 3).transpose(0, 2, 1, 3).reshape(H, W, 9)
