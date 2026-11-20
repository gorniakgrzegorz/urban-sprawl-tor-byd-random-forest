"""Land Cover Rewind browser app: `streamlit run app.py` (on Windows: double-click run_windows.bat)."""
import pathlib
import tempfile
import traceback
import streamlit as st
import folium
from folium.plugins import Draw, Geocoder
from streamlit_folium import st_folium
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from odc.geo.geom import Geometry
from landcoverrewind import pipeline, EPOCHS, __version__
from ui_text import TEXT

MAIL = "ggorniak@doktorant.umk.pl"
DOI = "10.5281/zenodo.24332551"
st.set_page_config(page_title="Land Cover Rewind 1985–2025", page_icon="🛰️", layout="wide")

with st.sidebar:
    lang = st.radio(TEXT["pl"]["lang"], ["pl", "en"], horizontal=True,
                    format_func=lambda x: {"pl": "Polski", "en": "English"}[x],
                    index=0 if st.query_params.get("lang", "pl") != "en" else 1)
T = TEXT[lang]


def num(v, nd):
    """Number formatted for the interface language (decimal comma and thin spacing in Polish)."""
    s = f"{v:,.{nd}f}"
    return s.replace(",", " ").replace(".", ",") if lang == "pl" else s


FOOTER = (f'<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;font-size:12px;color:#6b7280;margin-top:8px">'
          f'<span>© 2026 <a href="mailto:{MAIL}" title="{T["foot_mail"]}: {MAIL}">Grzegorz Górniak</a> · '
          f'Land Cover Rewind {__version__} · {T["foot_lic"]}</span>'
          f'<span>DOI: <a href="https://doi.org/{DOI}" target="_blank" title="{T["foot_rec"]}">{DOI}</a></span></div>')

st.title("Land Cover Rewind 1985–2025")
st.markdown("#### " + T["subtitle"])
st.markdown(T["intro"])
with st.expander(T["howto_title"], expanded=True):
    st.markdown(T["howto"])
with st.expander(T["inside_title"]):
    st.markdown(T["inside"])
with st.expander(T["glossary_title"]):
    st.markdown(T["glossary"])

with st.sidebar:
    st.header(T["step1"])
    st.caption(T["step1_cap"])
    upload = st.file_uploader(T["upload"], type=["gpkg", "geojson", "json", "zip"], help=T["upload_help"])
    st.header(T["step2"])
    st.caption(T["step2_cap"])
    epochs = st.multiselect(T["epochs"], EPOCHS, default=EPOCHS, help=T["epochs_help"])
    mode = st.radio(T["mode"], ["pretrained", "local"],
                    format_func=lambda x: {"pretrained": T["mode_pre"], "local": T["mode_loc"]}[x], help=T["mode_help"])
    threshold = st.select_slider(T["thr"], options=[round(0.30 + 0.05 * i, 2) for i in range(12)], value=0.65,
                                 format_func=lambda v: num(v, 2), help=T["thr_help"])
    max_cloud = st.slider(T["cloud"], 20, 90, 70, 5, help=T["cloud_help"])
    folder = st.text_input(T["folder"], "results", help=T["folder_help"])
    st.markdown("---")
    st.markdown(FOOTER, unsafe_allow_html=True)

geom, file_error, no_crs = None, None, False
if upload is not None:
    try:
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / upload.name
            p.write_bytes(upload.getvalue())
            gdf = gpd.read_file(f"zip://{p}" if p.suffix == ".zip" else p)
            no_crs = gdf.crs is None
            gdf = gdf.to_crs(4326) if gdf.crs else gdf.set_crs(4326)
        geom = gdf.union_all()
    except Exception as e:
        file_error = e
if file_error is not None:
    st.error(T["file_err"])
elif upload is not None and no_crs:
    st.warning(T["no_crs"])

st.subheader(T["map_title"])
st.markdown(T["map_help"])
m = folium.Map(location=[53.07, 18.35], zoom_start=9, tiles="OpenStreetMap")
Geocoder(collapsed=False, position="topright", add_marker=False).add_to(m)
Draw(draw_options=dict(polyline=False, circle=False, marker=False, circlemarker=False),
     edit_options=dict(edit=False)).add_to(m)
if geom is not None:
    folium.GeoJson(gpd.GeoSeries([geom], crs=4326).__geo_interface__).add_to(m)
    b = geom.bounds
    m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])
drawn = st_folium(m, height=480, use_container_width=True)
if geom is None and drawn and drawn.get("last_active_drawing"):
    geom = shape(drawn["last_active_drawing"]["geometry"])


def friendly_error(e: Exception) -> str:
    t = f"{type(e).__name__}: {e}".lower()
    if isinstance(e, MemoryError) or "unable to allocate" in t:
        return T["err_mem"]
    if any(s in t for s in ("connection", "timed out", "timeout", "max retries", "name or service", "getaddrinfo",
                            "ssl", "503", "502", "temporarily")):
        return T["err_net"]
    if "no epoch" in t:
        return T["err_noepoch"]
    if "extent mask" in t:
        return T["err_mask"]
    return T["err_other"]


st.subheader(T["step3"])
if geom is None:
    st.info(T["need_area"])
else:
    km2 = gpd.GeoSeries([geom], crs=4326).to_crs(3035).area.iloc[0] / 1e6
    st.success(T["area_ok"].format(km2=num(km2, 1), n=len(epochs)))
    if km2 > 2500:
        st.warning(T["area_big"])
if not epochs:
    st.warning(T["need_epoch"])
elif len(epochs) == 1:
    st.caption(T["one_epoch"])

STEPS = {"prepare": T["p_prepare"], "train": T["p_train"], "series": T["p_series"], "tables": T["p_tables"],
         "figures": T["p_figures"], "done": T["p_done"]}


def describe(step):
    if step.startswith("epoch "):
        t, rest = step[6:].split(" ", 1)
        i, n = rest.strip("()").split("/")
        return T["p_epoch"].format(t=t, i=i, n=n, a=int(t) - 1, b=int(t) + 1)
    return STEPS.get(step, step)


if st.button(T["run"], type="primary", disabled=(geom is None or not epochs)):
    bar = st.progress(0.0, text=T["starting"])
    box = st.expander(T["details"]).empty()
    lines = []

    def log(msg):
        lines.append(str(msg)); box.code("\n".join(lines[-40:]))

    def progress(u, step):
        bar.progress(float(u), text=f"{int(round(100 * u))}% · {describe(step)}")

    try:
        r = pipeline.run(Geometry(geom, "EPSG:4326"), epochs, mode, threshold, folder, None, max_cloud, log, progress, lang=lang)
        st.session_state["result"] = dict(out_dir=str(r["out_dir"]), table=r["table"], forms=r["forms"], skipped=r["skipped"])
        st.session_state["full"] = dict(B=r["B"], area=r["area"], geobox=r["geobox"], out_dir=r["out_dir"], geom=geom)
        st.session_state.pop("sdg", None)
    except Exception as e:
        bar.empty()
        st.error(friendly_error(e))
        with st.expander(T["err_details"]):
            st.code(traceback.format_exc())
        st.session_state.pop("result", None)

COLS_TABLE = {"epoch": "c_epoch", "built_up_ha": "c_ha", "patches": "c_patches", "mean_patch_ha": "c_mean",
              "lpi_class_pct": "c_lpi", "edge_density_km_per_km2": "c_ed", "linear_rate_from_base_pct_per_year": "c_rate"}
COLS_FORMS = {"period": "c_period", "new_ha": "c_new", "infill_pct": "c_infill", "edge_expansion_pct": "c_edge",
              "leapfrog_pct": "c_leap"}


def table(rows, cols, nd):
    df = pd.DataFrame(rows)
    df = df[[k for k in cols if k in df.columns]].rename(columns={k: T[v] for k, v in cols.items()})
    for c in df.columns:
        if pd.api.types.is_float_dtype(df[c]):
            df[c] = df[c].map(lambda v: ("n.d." if lang == "pl" else "n.a.") if pd.isna(v) else num(v, nd))
    return df


r = st.session_state.get("result")
if r:
    out = pathlib.Path(r["out_dir"])
    st.subheader(T["step4"])
    st.success(T["done"].format(out=out))
    if r["skipped"]:
        st.warning(T["skipped"].format(ep=", ".join(map(str, r["skipped"]))))
    c1, c2 = st.columns(2)
    c1.image(str(out / "built_up_animation.gif"), use_container_width=True, caption=T["cap_anim"])
    c2.image(str(out / "land_cover_animation.gif"), use_container_width=True, caption=T["cap_anim4"])
    c3, c4 = st.columns(2)
    c3.image(str(out / "first_detection_map.png"), use_container_width=True, caption=T["cap_fd"])
    if (out / "built_up_area_chart.png").exists():
        c4.image(str(out / "built_up_area_chart.png"), use_container_width=True, caption=T["cap_chart"])
    st.markdown("#### " + T["tab_title"])
    st.dataframe(table(r["table"], COLS_TABLE, 2), use_container_width=True, hide_index=True)
    st.caption(T["tab_cap"])
    if r["forms"]:
        st.markdown("#### " + T["forms_title"])
        st.dataframe(table(r["forms"], COLS_FORMS, 1), use_container_width=True, hide_index=True)
        st.caption(T["forms_cap"])
    full = st.session_state.get("full")
    if full is not None:
        with st.expander(T["sdg_title"]):
            st.markdown(T["sdg_intro"])
            pfiles = st.file_uploader(T["sdg_files"], type=["gpkg", "geojson", "json", "zip"], accept_multiple_files=True, key="pop")
            if pfiles:
                tmp = pathlib.Path(tempfile.mkdtemp())
                paths = []
                if len(pfiles) > 2:
                    st.warning(T["sdg_many"])
                for f in pfiles[:2]:
                    q = tmp / f.name; q.write_bytes(f.getvalue())
                    paths.append(f"zip://{q}" if q.suffix == ".zip" else str(q))
                cols = [list(gpd.read_file(p_, rows=1).columns.drop("geometry")) for p_ in paths]
                idf = st.selectbox(T["sdg_id"], cols[0], index=cols[0].index("code") if "code" in cols[0] else 0) if len(paths) == 2 else None
                num_cols = cols[0]
                f0 = st.selectbox(T["sdg_f0"], num_cols, index=num_cols.index("tot") if "tot" in num_cols else 0)
                f1 = st.selectbox(T["sdg_f1"], cols[-1], index=cols[-1].index("tot") if "tot" in cols[-1] else min(1, len(cols[-1]) - 1))
                cy0, cy1 = st.columns(2)
                y0 = cy0.number_input(T["sdg_y0"], 1985, 2025, 2011); y1 = cy1.number_input(T["sdg_y1"], 1985, 2026, 2021)
                if len(paths) == 1 and f0 == f1:
                    st.warning(T["sdg_same"])
                last = max(full["B"]) if full["B"] else 2025
                if y1 > last or y0 < min(full["B"] or [1985]):
                    st.warning(T["sdg_range"].format(a=min(full["B"] or [1985]), b=last))
                form = st.radio(T["sdg_form"], ["linear", "log"], horizontal=True, format_func=lambda x: T["sdg_lin"] if x == "linear" else T["sdg_log"])
                if st.button(T["sdg_run"], disabled=(y1 <= y0 or (len(paths) == 1 and f0 == f1))):
                    try:
                        _, summ = pipeline.run_sdg(full, paths, [f0, f1], (int(y0), int(y1)), idf, form, lang,
                                                   area_geom=Geometry(full["geom"], "EPSG:4326"))
                        st.session_state["sdg"] = summ
                    except Exception:
                        st.error(T["sdg_err"])
                        with st.expander(T["err_details"]):
                            st.code(traceback.format_exc())
            s_ = st.session_state.get("sdg")
            if s_:
                nd_ = "n.d." if lang == "pl" else "n.a."
                miss_ = lambda v: v is None or (isinstance(v, float) and v != v)
                pct_ = lambda v: nd_ if miss_(v) else num(100 * v, 2)
                nn_ = lambda v, d: nd_ if miss_(v) else num(v, d)
                st.success(T["sdg_res"].format(p0=num(s_["population_t0"], 0), p1=num(s_["population_t1"], 0),
                                                a0=num(s_["built_t0_ha"], 1), a1=num(s_["built_t1_ha"], 1),
                                                c0=nn_(s_["built_per_capita_t0_m2"], 0), c1=nn_(s_["built_per_capita_t1_m2"], 0),
                                                lcr=pct_(s_["lcr"]), pgr=pct_(s_["pgr"]),
                                                r=nn_(s_["lcrpgr"], 2), st=T["sdg_status"].get(s_["status"], s_["status"])))
                st.markdown(T["sdg_cells"].format(n=s_["cells_full"], m=s_["cells_with_ratio"],
                                                  gt=nn_(s_["cells_ratio_above_1_pct"], 1), dec=nn_(s_["new_built_in_declining_cells_pct"], 1)))
                if (out / "sdg_11_3_1.png").exists():
                    st.image(str(out / "sdg_11_3_1.png"), use_container_width=True, caption=T["sdg_cap"])
    st.markdown("#### " + T["dl_title"])
    st.download_button(T["dl"], (out / "results.zip").read_bytes(), file_name="results.zip", mime="application/zip", type="primary")
    st.markdown(T["files"])
    st.caption(T["cite"].format(doi=DOI))

st.markdown("---")
st.markdown(T["data_note"])
st.markdown(FOOTER, unsafe_allow_html=True)
