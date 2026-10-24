# Seria zabudowy Torunia i Bydgoszczy 1975–2025 z klasyfikatora Random Forest uczonego na etykietach Dynamic World

Kod analizy (notatnik Google Colab) i dane wynikowe do rekonstrukcji przyrostu zabudowy Torunia i Bydgoszczy w latach 1975–2025. Klasyfikator Random Forest uczony wyłącznie na współczesnych etykietach Dynamic World 2025 jest stosowany wstecz do archiwalnych zdjęć Landsat (1985–2025) i, przez most sensorowy w epoce 1985, do zdjęć Landsat MSS (1975 i 1980). Na tej podstawie liczone są wskaźniki urban sprawl, metryki krajobrazowe oraz wskaźnik SDG 11.3.1 (LCRPGR), także na siatce kilometrowej spisów powszechnych NSP 2011 i NSP 2021.

**Autorzy:** Grzegorz Górniak, Mieczysław Kunz
**Afiliacja:** Uniwersytet Mikołaja Kopernika w Toruniu, Wydział Nauk o Ziemi i Gospodarki Przestrzennej
**Kontakt:** ggorniak@doktorant.umk.pl
**Wersja:** 3.2 (2026-10-24)

## Zawartość repozytorium

| Folder / plik | Treść |
|---|---|
| `kod/Torun_Bydgoszcz_GeoAI_RF_urbansprawl_1985_2025.ipynb` | notatnik Google Colab: 24 rozdziały, 167 komórek kodu, każda sekcja opisana tytułem i jednym zdaniem; bez zapisanych wyników |
| `kod/environment_pip_freeze_2026-09-25.txt` | pełny zrzut `pip freeze` środowiska, w którym wykonano obliczenia (Google Colab, Python 3.13.15) |
| `requirements.txt` | wersje bibliotek importowanych w kodzie |
| `tabele/` | tabele wynikowe CSV; nazwa pliku: `<sekcja notatnika>_<miasto>_tab_<kod>_<opis>.csv` |
| `metadane/` | karty modeli (`model_card_RF_binarny.json`, `model_card_RF_MSS.json`), rejestr nauczonych klasyfikatorów (`REJESTR_MODELI.md`), spisy wyników (`00_SPIS_*.csv`), lista plików wejściowych ze źródłem i licencją, lista assetów Google Earth Engine |
| `weryfikacja/` | punkty walidacyjne i punkty ślepej fotointerpretacji z kluczami kodów |
| `dane_wejsciowe/` | dane własne i otwarte: granice stref, bariery, ludność gmin (GUS BDL), skorowidze arkuszy ortofotomapy |
| `dane_nsp/` | siatka 1 km ze wskaźnikami LCR, PGR i LCRPGR za dekadę spisową 2011–2021 (EPSG:2180) |
| `CITATION.cff`, `.zenodo.json` | metadane cytowania i depozytu Zenodo |
| `LICENSE`, `LICENSE_DANE.txt` | licencje kodu (MIT) i danych wynikowych (CC BY 4.0) |

## Układ notatnika

| Rozdziały | Zakres |
|---|---|
| 1–5 | pytania badawcze, środowisko, konfiguracja (`CONFIG`), obszar badań, kompozyty Sentinel-2 |
| 6–7 | Dynamic World jako źródło etykiet i jego walidacja względem Urban Atlas i ślepej fotointerpretacji |
| 8 | klasyfikator Random Forest: cechy Landsat, walidacja krzyżowa blokowa, ablacja, kalibracja progu, więzy, walidacja niezależna, model Sentinel-2 i model czteroklasowy |
| 9–16 | urban sprawl Torunia i Bydgoszczy: trajektorie, LCRPGR, bariery, kierunki, metryki krajobrazowe, mapy zmian, wskaźniki formy ekspansji |
| 17–20 | eksport GeoTIFF, spisy wyników, wykaz źródeł danych |
| 21, 23 | analizy uzupełniające: testy dokładności, odporności i wrażliwości |
| 22 | rozszerzenie serii do lat 1975 i 1980 (Landsat MSS) |
| 24 | wskaźnik SDG 11.3.1 na siatce kilometrowej NSP 2011 i NSP 2021 |

## Modele wynikowe

Szczegóły w kartach modeli i w rejestrze (`metadane/`).

- `rf_bin` (`a67b95fe`): Random Forest (300 drzew, 4 cechy przy podziale, minimalna liczebność liścia 1), 19 cech Landsat w siatce 30 m, etykiety wyłącznie z Dynamic World 2025, wyjście MULTIPROBABILITY, próg p(zabudowa) 0,55 kalibrowany na CORINE 2006, więzy zasięgu (Dynamic World 2015 ∪ 2025) i monotoniczności; seria A 1985–2025.
- `rf_s2` (`b457250d`): ten sam schemat na Sentinel-2 (10 m); seria B 2018–2025.
- `rf4` (`baee68ca`): model czteroklasowy (zabudowa, lasy i drzewa, wody, pozostałe) na Landsat.
- `rf_mss` (`840f9d4d`): Random Forest na cechach Landsat MSS (60 m) uczony na serii A z epoki 1985; mapy 1975 i 1980.

Wszystkie losowania używają ziarna 42.

## Jak odtworzyć obliczenia

1. Konto Google Earth Engine i własny projekt GEE. Nazwę projektu podaje się w zmiennej środowiskowej `PROJEKT_GEE` albo wpisuje w komórce rozdziału 2. Kod czyta gotowe assety, jeśli istnieją, a brakujące eksportuje; lista assetów jest w `metadane/`.
2. Folder na Dysku Google (domyślnie `Colab/Artykul_GeoAI_Torun_Random_Forest`) z plikami wejściowymi wymienionymi w `metadane/pliki_wejsciowe.csv`. Dane licencjonowane (Urban Atlas, arkusze ortofotomapy GUGiK, kafle WSF Evolution, granice gmin PRG, pełne siatki spisowe GUS) należy pobrać od dostawców.
3. Otworzyć notatnik w Google Colab i uruchamiać rozdziały po kolei. Parametry obszaru, epok, progów i więzów są w słowniku `CONFIG` (sekcja 3.1).
4. Wyniki zapisują się do folderu `eksporty_finalne/` z numerem sekcji w nazwie pliku.

## Znane ograniczenia

1. `tab_B6`, `tab_B6b` (ślepa fotointerpretacja archiwalnej ortofotomapy 2004–2005): druga, niezależna interpretacja nie została ukończona.
2. `tab_L7a`–`tab_L7d` (audyt klasyfikacji do ramki map i w strefach): porównanie p(zabudowa) na wspólnej siatce jest nieważne z powodu błędu rejestracji rastrów; zgodność powierzchni podaje `tab_K0`.
3. `tab_L10e`, `tab_L10f` (sekcja 21.10): część wariantów nie została policzona i ma puste wiersze.
4. Odtworzenie obliczeń w niezmienionej postaci wymaga dostępu do assetów Google Earth Engine z listy w `metadane/`.

## Źródła danych

Landsat Collection 2 i Landsat MSS (USGS), Sentinel-2 (ESA, Copernicus), Dynamic World (Google, World Resources Institute), World Settlement Footprint Evolution (DLR), CORINE Land Cover i Urban Atlas (Copernicus Land Monitoring Service), ortofotomapa i granice PRG (GUGiK), Bank Danych Lokalnych i siatki spisowe NSP 2011 i NSP 2021 (GUS), formy ochrony przyrody (GDOŚ), GHS-POP (JRC). Dane źródłowe podlegają licencjom dostawców i nie są redystrybuowane w tym repozytorium.

## Historia wersji

- 3.2 (2026-10-24): notatnik uporządkowany bez zmiany obliczeń; nazwa projektu GEE ze zmiennej środowiskowej `PROJEKT_GEE`; pamięć istniejących assetów (mniej zapytań do GEE); rok ortofotomapy (2023) w podpisach map; usunięte znaczniki redakcyjne z kodu, kart modeli i tabel metadanych.
- 3.1 (2026-10-12): wersja publiczna notatnika (opisy sekcji skrócone do tytułu i jednego zdania).

## Licencje

Kod: MIT (`LICENSE`). Tabele wynikowe, karty modeli, metadane i dane własne: CC BY 4.0 (`LICENSE_DANE.txt`).

## Cytowanie

Dane do cytowania są w `CITATION.cff` (na GitHubie przycisk „Cite this repository”). Prosimy o podanie wersji i DOI rekordu Zenodo.

---

## English summary

Code and result data for reconstructing built-up expansion of Toruń and Bydgoszcz (Poland), 1975–2025. A Random Forest classifier trained only on present-day Dynamic World 2025 labels is applied backwards to archival Landsat imagery (1985–2025) and, through a sensor bridge at the 1985 epoch, to Landsat MSS imagery (1975 and 1980). The resulting built-up series is used to compute urban sprawl indicators, landscape metrics and the SDG 11.3.1 indicator (LCRPGR), including on the 1 km census grid of the 2011 and 2021 Polish censuses. `kod/` holds the Google Colab notebook (24 chapters, 167 code cells, without stored outputs); `tabele/` holds the result tables; `metadane/` holds model cards, the classifier register and file lists. Reproduction requires a Google Earth Engine account and project (variable `PROJEKT_GEE`) and the input files listed in `metadane/pliki_wejsciowe.csv`. Code: MIT; result data: CC BY 4.0. The notebook and data descriptions are in Polish.
