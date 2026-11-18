@echo off
chcp 65001 >nul
cd /d %~dp0
echo ============================================================
echo  Land Cover Rewind 1985-2025: zabudowa z archiwum Landsat
echo  Nie zamykaj tego okna podczas pracy aplikacji.
echo ============================================================
set PY=
for %%V in (3.12 3.13 3.11) do (
  if not defined PY ( py -%%V --version >nul 2>&1 && set PY=py -%%V )
)
if not defined PY (
  python -c "import sys; sys.exit(0 if (3,11)<=sys.version_info[:2]<=(3,13) else 1)" >nul 2>&1 && set PY=python
)
if not defined PY (
  echo.
  echo Nie znaleziono Pythona w wersji 3.11, 3.12 lub 3.13.
  echo 1. Pobierz Python 3.12 ze strony https://www.python.org/downloads/windows/
  echo 2. W instalatorze zaznacz pole "Add python.exe to PATH" i kliknij "Install Now".
  echo 3. Uruchom ponownie ten plik.
  pause & exit /b 1
)
echo Uzywany Python: & %PY% --version
if not exist .venv (
  echo Tworzenie srodowiska aplikacji...
  %PY% -m venv .venv || (echo Nie udalo sie utworzyc srodowiska. & pause & exit /b 1)
)
call .venv\Scripts\activate
python -c "import streamlit, odc.stac, sklearn, streamlit_folium" >nul 2>&1 || (
  echo.
  echo Pierwsze uruchomienie: instalacja potrzebnych pakietow.
  echo Potrwa to okolo 5-10 minut, zalezy od lacza. Prosze czekac...
  python -m pip install --upgrade pip
  pip install -r requirements.txt || (echo Instalacja nie powiodla sie. Sprawdz internet i uruchom ponownie. & pause & exit /b 1)
)
echo.
echo Uruchamianie aplikacji. Za chwile otworzy sie przegladarka.
echo Jesli sie nie otworzy, wpisz w przegladarce adres: http://localhost:8501
streamlit run aplikacja.py
pause
