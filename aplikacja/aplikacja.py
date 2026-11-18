"""Aplikacja w przeglądarce: streamlit run aplikacja.py (w Windows: dwuklik w uruchom_windows.bat)."""
import pathlib, tempfile, traceback
import streamlit as st
import folium
from folium.plugins import Draw, Geocoder
from streamlit_folium import st_folium
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from odc.geo.geom import Geometry
from landcoverrewind import potok, EPOCHS, __version__

MAIL = "ggorniak@doktorant.umk.pl"
DOI = "10.5281/zenodo.24332552"
STOPKA = (f'<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;font-size:12px;color:#6b7280;margin-top:8px">'
          f'<span>© 2026 <a href="mailto:{MAIL}" title="Napisz do autora: {MAIL}">Grzegorz Górniak</a> · '
          f'Land Cover Rewind {__version__} · kod MIT, wyniki CC BY 4.0</span>'
          f'<span>DOI: <a href="https://doi.org/{DOI}" target="_blank" title="Rekord aplikacji w Zenodo">{DOI}</a></span></div>')

st.set_page_config(page_title="Land Cover Rewind 1985–2025", page_icon="🛰️", layout="wide")

# ---------------------------------------------------------------- nagłówek i instrukcja
st.title("Land Cover Rewind 1985–2025")
st.markdown("#### Jak rosła zabudowa i zmieniało się pokrycie terenu w Twojej okolicy")
st.markdown(
    "Aplikacja przegląda bezpłatne zdjęcia satelitarne z ostatnich czterdziestu lat i dla wskazanego obszaru "
    "rysuje mapy zabudowy co pięć lat, animację i wykres. Nie potrzebujesz konta ani znajomości GIS: zdjęcia "
    "pobierają się same z internetu, a obliczenia wykonuje Twój komputer.")

with st.expander("📋 Instrukcja krok po kroku (przeczytaj przy pierwszym uruchomieniu)", expanded=True):
    st.markdown("""
1. **Wskaż obszar.** Wpisz nazwę miejscowości w lupę w prawym górnym rogu mapy, aby ją odnaleźć. Potem kliknij
   ikonę **kwadratu** po lewej stronie mapy i przeciągnij myszą prostokąt wokół miejscowości (ikona **pięciokąta**
   pozwala obrysować dowolny kształt: klikaj kolejne narożniki, a na koniec kliknij pierwszy punkt).
   Zamiast rysować możesz w panelu po lewej wczytać plik z granicą obszaru.
2. **Sprawdź ustawienia w panelu po lewej.** Ustawienia domyślne są właściwe dla większości miejscowości w Polsce.
   Przy pierwszej próbie wybierz 2–3 lata (np. 1990, 2005, 2025), aby szybko zobaczyć wynik.
3. **Kliknij „Uruchom obliczenia”.** Pasek postępu pokaże, który rok jest liczony. Nie zamykaj okna ani
   czarnego okna konsoli w tle. Mały obszar (kilka km²) liczy się zwykle w około minutę, obszar wielkości
   średniego miasta (około 150 km²) ze wszystkimi latami od kilku do kilkunastu minut.
4. **Obejrzyj i pobierz wyniki.** Pod mapą pojawią się animacje, mapa „roku powstania” zabudowy, tabele
   z objaśnieniami i przycisk pobrania wszystkich plików w jednym archiwum ZIP.
""")

with st.expander("🔎 Co dzieje się w środku? (w prostych słowach)"):
    st.markdown("""
- **Zdjęcia.** Satelity Landsat fotografują Polskę od lat 80. co kilkanaście dni. Dla każdego wybranego roku
  aplikacja bierze wszystkie zdjęcia z trzech lat (rok wcześniej, ten rok, rok później) i usuwa z nich chmury.
- **Rozpoznawanie.** Program komputerowy (model *Random Forest*, „las decyzyjny”) nauczył się na dzisiejszych mapach
  Torunia i Bydgoszczy, jak budynki, drogi i place odbijają światło, także w barwach niewidocznych dla oka.
  Teraz ogląda stare zdjęcia i dla każdego kwadratu 30 × 30 m ocenia, jak bardzo prawdopodobne jest, że stoi tam zabudowa.
- **Porządek.** Kwadrat uznaje się za zabudowany, gdy pewność przekracza próg (domyślnie 0,65, czyli 65%).
  Obowiązują dwie zasady: zabudowa może pojawić się tylko tam, gdzie współczesne mapy satelitarne pokazują ją
  dziś, oraz zabudowa raz wykryta pozostaje zabudową (rozbiórek seria nie pokazuje).
- **Wyniki.** Z serii map aplikacja liczy powierzchnię zabudowy, liczbę skupisk zabudowy i sposób, w jaki
  przybywało nowych budynków (dogęszczanie, rozrastanie się na obrzeżach, nowe osiedla w szczerym polu).
- **Dokładność.** To przybliżenie: w projekcie mapy zgadzały się z niezależnymi danymi w 62–77% (miara F1),
  a najstarszy rok (1985) pomija część zabudowy. Wynik warto porównać ze starymi mapami lub zdjęciami lotniczymi.
""")

with st.expander("📖 Słowniczek"):
    st.markdown("""
- **Epoka** – rok, dla którego powstaje mapa (1985, 1990, … 2025); mapa łączy zdjęcia z tego roku i dwóch sąsiednich.
- **Piksel 30 m** – najmniejszy kwadrat mapy, 30 × 30 m (mniej więcej działka z domem i ogrodem).
- **Zabudowa** – budynki, drogi, parkingi, place i inne powierzchnie utwardzone.
- **Model gotowy / lokalny** – sposób, w jaki program uczy się rozpoznawać zabudowę (opis przy przełączniku w panelu).
- **Próg** – jak pewny musi być program, by uznać kwadrat za zabudowany.
- **Skupisko zabudowy (płat)** – grupa stykających się zabudowanych kwadratów.
- **GeoTIFF (.tif)** – mapa z położeniem geograficznym; otworzysz ją w bezpłatnym programie QGIS.
- **CSV (.csv)** – tabela; otworzysz ją w Excelu lub LibreOffice.
- **GPKG, GeoJSON, SHP** – formaty plików z granicami obszarów (np. pobrane z serwisów gmin lub z QGIS).
""")

# ---------------------------------------------------------------- panel boczny
with st.sidebar:
    st.header("Krok 1. Obszar")
    st.caption("Najprościej narysować obszar na mapie po prawej. Plik z granicą jest potrzebny tylko, jeśli go masz.")
    plik = st.file_uploader(
        "Wczytaj plik z granicą obszaru (nieobowiązkowe)", type=["gpkg", "geojson", "json", "zip"],
        help="Plik GeoPackage (.gpkg), GeoJSON (.geojson) albo spakowany do .zip komplet plików Shapefile (.shp, .shx, .dbf, .prj). "
             "Jeśli nie masz takiego pliku, po prostu narysuj obszar na mapie.")
    st.header("Krok 2. Ustawienia")
    st.caption("Ustawienia domyślne są właściwe dla większości miejscowości w Polsce.")
    epoki = st.multiselect(
        "Lata (epoki) do obliczenia", EPOCHS, default=EPOCHS,
        help="Każdy rok to osobna mapa i kilka zestawów zdjęć do pobrania. Mniej lat = szybciej. "
             "Formy przyrostu wymagają co najmniej dwóch lat; tempo wzrostu liczone jest od 1990 r., jeśli ten rok jest wybrany.")
    tryb = st.radio(
        "Sposób rozpoznawania zabudowy", ["gotowy", "lokalny"],
        format_func=lambda x: {"gotowy": "Model gotowy (zalecany w Polsce)",
                               "lokalny": "Model uczony na moim obszarze"}[x],
        help="Model gotowy: nauczony wcześniej na Toruniu i Bydgoszczy, działa od razu. "
             "Model uczony na Twoim obszarze: aplikacja uczy się na współczesnej mapie pokrycia terenu Twojego obszaru "
             "(Impact Observatory 2024); wybierz go poza Polską lub gdy krajobraz bardzo różni się od okolic Torunia. Trwa nieco dłużej.")
    prog = st.select_slider(
        "Próg pewności rozpoznania zabudowy", options=[round(0.30 + 0.05 * i, 2) for i in range(12)], value=0.65,
        format_func=lambda v: f"{v:.2f}".replace(".", ","),
        help="Jak pewny musi być program, by uznać kwadrat za zabudowany. Wyższy próg = mniej zabudowy i mniej fałszywych wykryć; "
             "niższy = więcej zabudowy, ale więcej pomyłek. Zalecane 0,65 (dobrane na mapach Torunia i Bydgoszczy); zmieniaj tylko świadomie.")
    max_chmur = st.slider(
        "Pomijaj zdjęcia bardziej zachmurzone niż [%]", 20, 90, 70, 5,
        help="Zdjęcia, na których chmury zakrywają więcej niż podany odsetek kadru, są pomijane. Na pozostałych chmury są usuwane "
             "automatycznie. Zostaw 70; zwiększ, jeśli aplikacja zgłosi brak zdjęć dla jakiegoś roku.")
    katalog = st.text_input(
        "Nazwa folderu na wyniki", "wyniki",
        help="Folder powstanie obok pliku aplikacja.py (w folderze aplikacji). Pełną ścieżkę zobaczysz po zakończeniu obliczeń. "
             "Dla innego obszaru wpisz inną nazwę, aby nie nadpisać poprzednich wyników.")
    st.markdown("---")
    st.markdown(STOPKA, unsafe_allow_html=True)

# ---------------------------------------------------------------- mapa
geom, blad_pliku = None, None
if plik is not None:
    try:
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / plik.name
            p.write_bytes(plik.getvalue())
            gdf = gpd.read_file(f"zip://{p}" if p.suffix == ".zip" else p)
            gdf = gdf.to_crs(4326) if gdf.crs else gdf.set_crs(4326)
        geom = gdf.union_all()
    except Exception as e:
        blad_pliku = e
if blad_pliku is not None:
    st.error("Nie udało się odczytać pliku z granicą. Sprawdź, czy to GeoPackage, GeoJSON albo plik .zip z kompletem plików "
             "Shapefile (.shp, .shx, .dbf, .prj). Możesz też po prostu narysować obszar na mapie.")

st.subheader("Krok 1. Wskaż obszar na mapie")
st.markdown("🔍 Lupa w prawym górnym rogu: wyszukaj miejscowość. ⬛ Kwadrat po lewej: kliknij go i przeciągnij prostokąt. "
            "⬟ Pięciokąt: obrysuj dowolny kształt. 🗑 Kosz: usuń rysunek i zacznij od nowa.")
m = folium.Map(location=[53.07, 18.35], zoom_start=9, tiles="OpenStreetMap")
Geocoder(collapsed=False, position="topright", add_marker=False).add_to(m)
Draw(draw_options=dict(polyline=False, circle=False, marker=False, circlemarker=False),
     edit_options=dict(edit=False)).add_to(m)
if geom is not None:
    folium.GeoJson(gpd.GeoSeries([geom], crs=4326).__geo_interface__).add_to(m)
    b = geom.bounds; m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])
mapa = st_folium(m, height=480, use_container_width=True)
if geom is None and mapa and mapa.get("last_active_drawing"):
    geom = shape(mapa["last_active_drawing"]["geometry"])


def przyjazny_blad(e: Exception) -> str:
    t = f"{type(e).__name__}: {e}".lower()
    if isinstance(e, MemoryError) or "unable to allocate" in t:
        return "Zabrakło pamięci komputera. Wybierz mniejszy obszar albo mniej lat i uruchom ponownie."
    if any(s in t for s in ("connection", "timed out", "timeout", "max retries", "name or service", "getaddrinfo",
                            "ssl", "503", "502", "temporarily")):
        return ("Brak połączenia z serwerem zdjęć satelitarnych (Microsoft Planetary Computer). Sprawdź internet i kliknij "
                "„Uruchom obliczenia” ponownie; już pobrane lata zostały zapamiętane i nie będą liczone od nowa.")
    if "żadnej epoki" in t:
        return ("Dla tego obszaru nie udało się zebrać zdjęć w żadnym z wybranych lat. Zwiększ próg zachmurzenia w panelu "
                "po lewej albo wybierz inne lata.")
    if "maski zasięgu" in t:
        return ("Współczesna mapa pokrycia terenu nie pokazuje w tym obszarze zabudowy albo nie udało się jej pobrać. "
                "Jeśli w obszarze są budynki, spróbuj ponownie za chwilę albo powiększ obszar.")
    return "Obliczenia przerwał nieoczekiwany błąd. Spróbuj ponownie; jeśli błąd się powtórzy, prześlij autorowi treść ze „Szczegółów błędu”."


# ---------------------------------------------------------------- uruchomienie
st.subheader("Krok 3. Uruchom obliczenia")
if geom is None:
    st.info("Najpierw wskaż obszar na mapie powyżej albo wczytaj plik w panelu po lewej. Przycisk uruchomienia będzie wtedy aktywny.")
    km2 = 0
else:
    km2 = gpd.GeoSeries([geom], crs=4326).to_crs(3035).area.iloc[0] / 1e6
    st.success(f"Wskazany obszar: {km2:,.1f} km²".replace(",", " ").replace(".", ",") +
               f". Wybrane lata: {len(epoki)}.")
    if km2 > 2500:
        st.warning("Obszar większy niż 2500 km² może wymagać ponad 8 GB pamięci. Podziel go na mniejsze części.")
if not epoki:
    st.warning("Wybierz co najmniej jeden rok w panelu po lewej.")
elif len(epoki) == 1:
    st.caption("Wybrano jeden rok: powstanie mapa zabudowy, ale formy przyrostu i tempo wzrostu wymagają co najmniej dwóch lat.")

if st.button("▶ Uruchom obliczenia", type="primary", disabled=(geom is None or not epoki)):
    pasek = st.progress(0.0, text="Rozpoczynanie…")
    szczegoly = st.expander("Szczegóły techniczne (dla zaawansowanych)")
    logbox = szczegoly.empty(); linie = []

    def log(msg):
        linie.append(str(msg)); logbox.code("\n".join(linie[-40:]))

    def postep(u, opis):
        pasek.progress(float(u), text=f"{int(round(100 * u))}% · {opis}")

    try:
        w = potok.uruchom(Geometry(geom, "EPSG:4326"), epoki, tryb, prog, katalog, None, max_chmur, log, postep)
        st.session_state["wynik"] = dict(katalog=str(w["katalog"]), tab=w["tab"], formy=w["formy"],
                                         pominiete=w.get("pominiete", []))
    except Exception as e:
        pasek.empty()
        st.error(przyjazny_blad(e))
        with st.expander("Szczegóły błędu"):
            st.code(traceback.format_exc())
        st.session_state.pop("wynik", None)

# ---------------------------------------------------------------- wyniki (zapamiętane, nie znikają po pobraniu)
KOL_TAB = {"epoka": "Rok", "zabudowa_ha": "Powierzchnia zabudowy [ha]", "platy": "Liczba skupisk zabudowy",
           "sredni_plat_ha": "Średnia wielkość skupiska [ha]", "lpi_klasowe_proc": "Udział największego skupiska [%]",
           "gestosc_krawedzi_km_km2": "Długość granic zabudowy [km na km²]",
           "tempo_liniowe_od_bazy_proc_rok": "Średni roczny przyrost od roku bazowego [%/rok]"}
KOL_FORMY = {"okres": "Okres", "nowa_ha": "Nowa zabudowa [ha]", "wypelnianie_proc": "Dogęszczanie [%]",
             "krawedziowy_proc": "Rozrastanie się na obrzeżach [%]", "przeskok_proc": "Nowe skupiska w polu [%]"}


def tabela_pl(rows, kol, nd):
    df = pd.DataFrame(rows)
    df = df[[k for k in kol if k in df.columns]].rename(columns=kol)
    for c in df.columns:
        if pd.api.types.is_float_dtype(df[c]):
            df[c] = df[c].map(lambda v: "n.d." if pd.isna(v) else f"{v:,.{nd}f}".replace(",", " ").replace(".", ","))
    return df


w = st.session_state.get("wynik")
if w:
    out = pathlib.Path(w["katalog"])
    st.subheader("Krok 4. Wyniki")
    st.success(f"Gotowe. Wszystkie pliki zapisano w folderze: {out}")
    if w["pominiete"]:
        st.warning("Pominięto lata bez wystarczającej liczby zdjęć: " + ", ".join(map(str, w["pominiete"])) +
                   ". Możesz zwiększyć próg zachmurzenia i uruchomić ponownie.")
    c1, c2 = st.columns(2)
    c1.image(str(out / "animacja_zabudowa.gif"), use_container_width=True,
             caption="Animacja: zabudowa (ciemnoczerwona) w kolejnych latach; nad mapą rok i powierzchnia zabudowy.")
    c2.image(str(out / "animacja_pokrycie.gif"), use_container_width=True,
             caption="Animacja: cztery rodzaje pokrycia terenu (zabudowa, lasy i drzewa, wody, pozostałe). "
                     "Klasy inne niż zabudowa są mniej dokładne.")
    c3, c4 = st.columns(2)
    c3.image(str(out / "mapa_epoka_detekcji.png"), use_container_width=True,
             caption="Kiedy pojawiła się zabudowa: kolor oznacza okres, w którym dany kwadrat 30 m po raz pierwszy "
                     "rozpoznano jako zabudowany. Pierwszy kolor (≤ najstarszy rok) to zabudowa istniejąca już na początku.")
    if (out / "wykres_powierzchni.png").exists():
        c4.image(str(out / "wykres_powierzchni.png"), use_container_width=True,
                 caption="Powierzchnia zabudowy w kolejnych latach [ha]. Pierwszy rok (1985) bywa zaniżony.")

    st.markdown("#### Wskaźniki dla każdego roku")
    st.dataframe(tabela_pl(w["tab"], KOL_TAB, 2), use_container_width=True, hide_index=True)
    st.caption("Skupisko zabudowy to grupa stykających się zabudowanych kwadratów. Mniej skupisk przy rosnącej powierzchni oznacza, "
               "że zabudowa się zrasta; więcej skupisk, że powstają nowe, rozproszone osiedla. Długość granic na km² rośnie, gdy "
               "zabudowa staje się bardziej poszarpana. Roczny przyrost liczony jest od 1990 r. (jeśli ten rok wybrano), "
               "w przeciwnym razie od najstarszego wybranego roku; „n.d.” oznacza brak danych.")
    if w["formy"]:
        st.markdown("#### W jaki sposób przybywało zabudowy")
        st.dataframe(tabela_pl(w["formy"], KOL_FORMY, 1), use_container_width=True, hide_index=True)
        st.caption("Dogęszczanie: nowa zabudowa otoczona istniejącą (luki w zabudowie). Rozrastanie się na obrzeżach: nowa zabudowa "
                   "dotykająca istniejącej. Nowe skupiska w polu: nowa zabudowa bez kontaktu z istniejącą. Trzy udziały sumują się do 100%.")

    st.markdown("#### Pobierz wyniki")
    st.download_button("⬇ Pobierz wszystkie wyniki (ZIP)", (out / "wyniki.zip").read_bytes(), file_name="wyniki.zip",
                       mime="application/zip", type="primary")
    st.markdown("""
| Plik w archiwum | Co zawiera | Czym otworzyć |
|---|---|---|
| `animacja_*.gif`, `mapa_epoka_detekcji.png`, `wykres_powierzchni.png` | animacje, mapa i wykres widoczne powyżej | przeglądarka, przeglądarka zdjęć |
| `wskazniki_epok.csv`, `formy_przyrostu.csv` | tabele powyżej (kolumny pod nazwami skróconymi, opis w README) | Excel, LibreOffice |
| `seria_A_<rok>.tif` | mapa zabudowy roku: 1 zabudowa, 0 brak | QGIS (bezpłatny) |
| `pokrycie_4klasy_<rok>.tif` | 1 zabudowa, 2 lasy i drzewa, 3 wody, 4 pozostałe | QGIS |
| `epoka_pierwszej_detekcji.tif` | rok pierwszego wykrycia zabudowy, 0 = nigdy | QGIS |
| `p_zabudowy_<rok>.tif` | pewność rozpoznania zabudowy 0–100 przed porządkowaniem serii | QGIS |
| `dane_wejsciowe.csv`, `metadane.json` | liczba i identyfikatory użytych zdjęć, ustawienia (do odtworzenia obliczeń) | Excel, edytor tekstu |
""")
    st.caption("Wyniki są przybliżeniem (zob. „Co dzieje się w środku?”). Cytując, podaj: Górniak G., Kunz M., 2026. "
               "Land Cover Rewind 1985–2025. Zenodo. https://doi.org/" + DOI)

st.markdown("---")
st.markdown("Dane: Landsat Collection 2 (U.S. Geological Survey) i Impact Observatory/Esri 10 m Annual Land Use Land Cover "
            "(CC BY 4.0), udostępniane przez Microsoft Planetary Computer; mapa podkładowa i wyszukiwarka © OpenStreetMap. "
            "Metoda: G. Górniak, M. Kunz, Uniwersytet Mikołaja Kopernika w Toruniu.")
st.markdown(STOPKA, unsafe_allow_html=True)
