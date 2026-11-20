# Land Cover Rewind 1985–2025 (wersja polska)

Aplikacja odtwarza mapy zabudowy i pokrycia terenu w epokach 1985–2025 (co pięć lat) dla obszaru wskazanego przez użytkownika. Powtarza procedurę z projektu *urban-sprawl-tor-byd-random-forest* (Górniak i Kunz): klasyfikator Random Forest uczony na współczesnej mapie 10 m klasyfikuje kompozyty Landsat z dawnych lat, a więz zasięgu i reguła nieodwracalności zabudowy porządkują wynik w serię monotoniczną.

Wersja angielska: [README.md](README.md); samouczek (EN): [USER_GUIDE.md](USER_GUIDE.md). Aplikacja ma interfejs polski i angielski (przełącznik u góry panelu bocznego).

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24332551.svg)](https://doi.org/10.5281/zenodo.24332551)

**W skrócie:** na podstawie bezpłatnych zdjęć satelitarnych z ostatnich czterdziestu lat aplikacja rysuje dla wskazanej miejscowości mapy zabudowy co pięć lat, animację i wykres. Nie trzeba znać GIS ani programowania: instrukcja na ekranie prowadzi krok po kroku.

**Nie wymaga konta Google ani żadnego innego konta.** Zdjęcia satelitarne i mapy pokrycia terenu pobierane są anonimowo z katalogu STAC [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com); obliczenia wykonuje komputer użytkownika.

## Instalacja w systemie Windows (bez znajomości programowania)

1. **Zainstaluj Python 3.12.** Wejdź na https://www.python.org/downloads/windows/, pobierz instalator *Python 3.12* (Windows installer 64-bit) i uruchom go. **Zaznacz pole „Add python.exe to PATH”** na pierwszym ekranie instalatora, potem kliknij *Install Now*. Nowsze wersje (3.14 i dalsze) nie są jeszcze sprawdzone.
2. **Pobierz aplikację.** Pobierz archiwum ZIP aplikacji (z rekordu Zenodo albo ze strony repozytorium GitHub: zielony przycisk *Code* → *Download ZIP*) i rozpakuj je (prawy przycisk myszy → *Wyodrębnij wszystkie*).
3. **Uruchom.** W rozpakowanym folderze `aplikacja` kliknij dwukrotnie plik `run_windows.bat`. Pierwsze uruchomienie instaluje potrzebne pakiety (około 5–10 minut, zależnie od łącza); czarne okno konsoli musi pozostać otwarte przez cały czas pracy aplikacji.
4. **Pracuj w przeglądarce.** Aplikacja otworzy się sama w przeglądarce (adres http://localhost:8501). Na ekranie znajdziesz instrukcję krok po kroku: wskaż obszar na mapie, sprawdź ustawienia, kliknij **Uruchom obliczenia**, obejrzyj i pobierz wyniki.

Wymagania: połączenie z internetem (sprawdzono na komputerze z 8 GB pamięci RAM i dwoma rdzeniami; szczytowego zużycia pamięci nie mierzono), około 2 GB miejsca na dysku na pakiety.

## Dla zaawansowanych: Linux, macOS, wiersz poleceń, Docker

```bash
cd aplikacja
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
pytest -q   # testy jednostkowe na danych syntetycznych, bez internetu
```

W PowerShell aktywacja środowiska może wymagać polecenia `Set-ExecutionPolicy -Scope Process RemoteSigned`.

Wiersz poleceń (bez okna, z paskiem postępu w konsoli):

```bash
python landcoverrewind_cli.py --bbox 18.55 52.98 18.70 53.06 --out wyniki_torun --lang pl
python landcoverrewind_cli.py --file examples/torun_centre.geojson --epochs 1990 2005 2025 --mode local --lang pl
```

Docker: `docker build -t landcoverrewind . && docker run -p 8501:8501 landcoverrewind`, a następnie http://localhost:8501.

> Modele wstępnie wyuczone są czytane z folderu `models/` obok pakietu, dlatego aplikację, wiersz poleceń i interfejs programistyczny uruchamia się z rozpakowanego folderu źródłowego (albo z obrazu Docker); `pip install -e .` zachowuje ten układ. Plik `requirements-lock.txt` podaje dokładne wersje bibliotek użyte w testach i w opublikowanej ocenie; identyczne bit po bicie wyniki uzyskuje się przy tych samych wersjach bibliotek i niezmienionych danych dostawcy.

## Co powstaje

| Plik | Zawartość |
|---|---|
| `built_up_<epoka>.tif` | zabudowa serii monotonicznej (1 = zabudowa, 0 = brak, 255 = poza obszarem), 30 m |
| `built_up_probability_<epoka>.tif` | prawdopodobieństwo zabudowy przed więzami, 0–100 (255 = brak danych) |
| `land_cover_4class_<epoka>.tif` | 1 zabudowa, 2 lasy i drzewa, 3 wody, 4 pozostałe, 0 = brak danych lub poza obszarem |
| `first_detection_epoch.tif` | epoka, w której piksel pierwszy raz jest zabudową; 0 = nigdy niezabudowany, −1 = poza obszarem |
| `epoch_metrics.csv` | `built_up_ha` powierzchnia zabudowy [ha], `patches` liczba skupisk zabudowy (płatów), `mean_patch_ha` średnia wielkość płatu [ha], `lpi_class_pct` udział największego płatu w zabudowie [%], `edge_density_km_per_km2` długość granic zabudowy [km/km²], `linear_rate_from_base_pct_per_year` średni roczny przyrost od 1990 r. albo od najstarszej wybranej epoki, gdy 1990 nie wybrano [%/rok]; liczby zaokrąglone do 0,01, pusta komórka = brak danych |
| `growth_forms.csv` | `new_ha` nowa zabudowa w okresie [ha] i jej udział [%]: `infill_pct` dogęszczanie, `edge_expansion_pct` rozrastanie się na obrzeżach, `leapfrog_pct` nowe skupiska bez kontaktu z istniejącą zabudową (tylko przy co najmniej dwóch epokach) |
| `input_scenes.csv` | liczba scen i dni pozyskania oraz sensory w każdej epoce |
| `built_up_animation.gif`, `land_cover_animation.gif`, `first_detection_map.png`, `built_up_area_chart.png` | wizualizacje z opisami w języku interfejsu |
| `metadata.json` | wersja programu, ustawienia, data obliczeń i identyfikatory scen Landsat każdej epoki (okno epoki 2025 obejmuje lata 2024–2026, więc wynik tej epoki może się zmieniać, dopóki przybywają sceny z 2026 r.; zapis identyfikatorów pozwala odtworzyć obliczenia) |
| `results.zip` | wszystko powyżej w jednym pliku |

## Wskaźnik SDG 11.3.1 (ludność)

Po obliczeniach aplikacja (panel „Wskaźnik SDG 11.3.1”) i wiersz poleceń łączą serię zabudowy z siatką ludności z dwóch lat i liczą stosunek tempa zużycia terenu do tempa wzrostu ludności (LCRPGR) dla całego obszaru i każdej komórki siatki. Działa każda warstwa poligonów z ludnością: jeden plik z dwiema kolumnami albo dwa pliki łączone identyfikatorem komórki, np. siatki kilometrowe GUS z NSP 2011 i NSP 2021 (pole `tot`, identyfikator `code`).

```
python landcoverrewind_cli.py --file miasto.gpkg --population nsp2011.gpkg nsp2021.gpkg --pop-fields tot tot --pop-years 2011 2021
```

Domyślnie LCR ma postać liniową z metadanych UN-Habitat (2025) (`--lcr-form log` daje postać logarytmiczną), PGR jest logarytmiczne, a zabudowę w datach spisów interpoluje się między najbliższymi epokami. Iloraz komórki podaje się tylko dla komórek leżących w całości w obszarze; przy stałej ludności (|PGR| < 0,0013 na rok) iloraz oznacza się jako nieinterpretowalny. Pliki: `sdg_11_3_1_cells.gpkg/.csv`, `sdg_11_3_1_summary.json`, `sdg_11_3_1.png`.

## Jak to działa

1. **Siatka.** Obszar dostaje siatkę 30 m w strefie UTM swojego środka (albo w układzie podanym opcją `--crs`).
2. **Sceny.** Dla epoki *t* wyszukiwane są sceny Landsat Collection 2 Level 2 z lat *t* − 1 … *t* + 1 (Landsat 4/5 TM do 2012 r., 7 ETM+ w latach 2000–2012, 8 OLI od 2013 r., 9 OLI od 2022 r.), z zachmurzeniem sceny poniżej 70%.
3. **Maska chmur i harmonizacja.** Piksele z bitami 0–5 pasma QA_PIXEL (wypełnienie, chmura rozszerzona, cirrus, chmura, cień, śnieg) są usuwane; odbicie to DN · 2,75e-5 − 0,2; TM i ETM+ harmonizowane do OLI współczynnikami Roy i in. (2016).
4. **Cechy.** Mediana lata (VI–IX) w sześciu pasmach, wskaźniki NDVI, NDBI, NDWI, MNDWI, BU, BSI, kontrast i entropia GLCM pasma NIR w oknie 7 × 7 oraz cztery wskaźniki mediany przedwiośnia (III–V): 18 cech modelu. Liczona jest też amplituda NDVI (95. minus 5. percentyl w oknie lat), dziewiętnasta cecha modelu GEE, ale model jej nie używa: w teście dla Grudziądza była zawyżona w epoce 1985 i zaniżała tam wykrycia zabudowy, a jej pominięcie zmniejszyło też różnicę wobec serii A w Toruniu i Bydgoszczy. Obszary większe niż 768 × 768 pikseli liczone są w kaflach.
5. **Model.**
   - `pretrained` (gotowy, domyślny): Random Forest `rf_torun_bydgoszcz_2025` uczony na mapach 2025 projektu (Toruń i Bydgoszcz; etykiety z transferu Dynamic World 2025) i cechach liczonych tym kodem. Zalecany dla Polski i podobnego krajobrazu Europy Środkowej.
   - `local` (lokalny): model (zapisywany w folderze wyników) uczony w obszarze użytkownika na etykietach Impact Observatory LULC 2024 (10 m, Sentinel-2), sprowadzonych do czterech klas i do 30 m (zabudowa, gdy co najmniej 5 z 9 pikseli 10 m jest zabudową; piksele z 1–4 pikselami zabudowy pomijane; pozostałe według klasy dominującej), 1500 punktów na klasę, ziarno 42. Zalecany poza Polską.
   - Oba warianty: 300 drzew, 4 cechy na podział, minimalny liść 1 (jak w modelu GEE projektu), ziarno 42.
6. **Więzy.** Seria A: B<sub>t</sub> = M ∩ ⋃<sub>s ≤ t</sub> (p<sub>s</sub> ≥ 0,65). Maska zasięgu M to piksele 30 m, w których co najmniej 5 z 9 pikseli 10 m jest zabudową w IO LULC 2017 lub 2024; zastępuje maskę Dynamic World 2015 ∪ 2025 z projektu, dostępną tylko w Google Earth Engine. Próg wybrano jak w projekcie na epoce rozwojowej 2005: progi 0,55 i 0,65 dały tę samą F1 serii 2005 względem serii A projektu (87% w Toruniu, 88% w Bydgoszczy), a próg 0,75 niższą (85% i 86%); wybrano 0,65, bo daje mniejszą różnicę powierzchni (tabela w `models/threshold_calibration.json`).
7. **Wskaźniki i wizualizacje** jak w artykułach projektu: płaty w sąsiedztwie ośmiu pikseli, gęstość krawędzi bez granicy obszaru, formy przyrostu według liczby zabudowanych sąsiadów w oknie 3 × 3.

Czas: dla obszaru około 150 km² od kilku do kilkunastu minut na wszystkie epoki, zależnie od łącza i liczby scen; obszary większe niż 768 × 768 pikseli liczone są w kaflach. Cechy epok zapisywane są w `<folder wyników>/cache` pod nazwą zależną od siatki, więc ponowne uruchomienie dla tego samego obszaru z innym progiem trwa sekundy. Liczbę wątków pobierania ustawia zmienna środowiskowa `LCR_THREADS` (domyślnie 8).

## Sprawdzian

Aplikację uruchomiono dla miast Toruń i Bydgoszcz (granice administracyjne, siatka 30 m EPSG:2180) i porównano piksel po pikselu z serią A projektu z Google Earth Engine (`tools/compare_reference.py`, wynik w `models/app_test.json`). F1 względem serii A wynosiła 83–92%, a aplikacja wskazywała o 9,5–19,6% więcej zabudowy niż seria A, najwięcej w epoce 1990. Próg wybrano na epoce 2005; epoka 1990 jest testem, a zgodność w 2025 r. dotyczy roku i miast, na których uczono model, więc nie jest niezależną oceną. Tryb lokalny (bez map projektu) dał w Toruniu prawie te same wartości. Model `rf_torun_bydgoszcz_2025` uczony w jednym mieście i oceniany w drugim zachował trafność 88,6–90,3% (zabudowa) i 87,7–88,4% (cztery klasy) na zrównoważonej próbie pikseli map 2025. Są to zgodności z mapami projektu, a nie dokładności wobec niezależnych danych.

Przykład obszaru spoza miejsc uczenia: Grudziądz z okolicą (140 km², wszystkie epoki 1985–2025); epoka 1985 nadal pokazuje mniej zabudowy niż 1990 (2226 wobec 2947 ha), co odpowiada artefaktowi pierwszej epoki opisanemu w artykułach.

## Ograniczenia, które trzeba znać

- Mapy historyczne są przybliżeniem: w projekcie zgodność F1 serii A z niezależnymi źródłami wynosiła 62–77%, a epoka 1985 pomija część istniejącej zabudowy (artefakt pierwszej epoki). Wskaźniki dynamiki liczymy od 1990 r.
- Seria monotoniczna nie rejestruje rozbiórek; zabudowa raz wykryta pozostaje zabudową.
- Model `pretrained` uczono w dwóch miastach jednego regionu. W innym klimacie, przy innej zabudowie lub innym rolnictwie użyj trybu `local` i sprawdź wynik na ortofotomapie.
- Cechy GLCM liczone są inaczej niż w GEE (skala tekstury), a amplituda NDVI nie jest używana, dlatego modelu z GEE nie da się przenieść bez ponownego uczenia; model `rf_torun_bydgoszcz_2025` uczono na cechach z tego kodu.
- Lata 1975 i 1980 (Landsat MSS) nie są obsługiwane: wymagają drugiego etapu transferu i normalizacji radiometrycznej opisanej w artykule.
- Klasy niezabudowane (lasy, wody, pozostałe) mają większy błąd niż zabudowa; ich zmiany interpretuj ostrożnie.

## Odtworzenie modelu

`tools/train_pretrained.py` odtwarza modele z plików etykiet `tor_v3_rf_4kl_2025.tif` i `byd_v3_rf_4kl_2025.tif` (mapy czteroklasowe 2025 projektu; jeśli w rekordzie Zenodo 10.5281/zenodo.24155226 mają inne nazwy, podaj ich ścieżki) i zapisuje punkty uczące (`models/*_points.npz`), z których aplikacja odtwarza model, gdy plik `.joblib` nie pasuje do zainstalowanej wersji scikit-learn. Karta modelu z hiperparametrami i wynikiem testu przeniesienia między miastami jest w `models/*.json`.

## Autor i kontakt

© 2026 [Grzegorz Górniak](mailto:ggorniak@doktorant.umk.pl), Uniwersytet Mikołaja Kopernika w Toruniu. Uwagi i zgłoszenia błędów: ggorniak@doktorant.umk.pl.

## Licencja i cytowanie

Kod: MIT. Modele i wyniki: CC BY 4.0. Cytuj aplikację: Górniak, G., Kunz, M., 2026. Land Cover Rewind 1985–2025. Zenodo. https://doi.org/10.5281/zenodo.24332551. Metoda i dane projektu: Górniak, G., Kunz, M., 2026a. Reconstructing built-up land in Toruń and Bydgoszcz (Poland) 1975–2025 from Landsat with a Dynamic World-trained Random Forest: code and result data. Zenodo. https://doi.org/10.5281/zenodo.24076776 (oraz Górniak, G., Kunz, M., 2026b, rastry GeoTIFF: https://doi.org/10.5281/zenodo.24155226)

Dane: Landsat Collection 2 (U.S. Geological Survey) i Impact Observatory/Esri 10 m Annual Land Use Land Cover (CC BY 4.0), udostępniane przez Microsoft Planetary Computer.
