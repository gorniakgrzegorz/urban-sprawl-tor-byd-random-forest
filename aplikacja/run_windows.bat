@echo off
chcp 65001 >nul
cd /d %~dp0
echo ============================================================
echo  Land Cover Rewind 1985-2025
echo  Nie zamykaj tego okna / Do not close this window.
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
  echo Nie znaleziono Pythona 3.11-3.13 / Python 3.11-3.13 not found.
  echo 1. https://www.python.org/downloads/windows/  (Python 3.12)
  echo 2. Zaznacz / tick "Add python.exe to PATH", "Install Now".
  echo 3. Uruchom ponownie / run this file again.
  pause & exit /b 1
)
echo Python: & %PY% --version
if not exist .venv (
  echo Tworzenie srodowiska / creating the environment...
  %PY% -m venv .venv || (echo Blad srodowiska / environment error. & pause & exit /b 1)
)
call .venv\Scripts\activate
python -c "import streamlit, odc.stac, sklearn, streamlit_folium" >nul 2>&1 || (
  echo.
  echo Pierwsze uruchomienie: instalacja pakietow (5-10 min).
  echo First run: installing packages (5-10 min)...
  python -m pip install --upgrade pip
  pip install -r requirements.txt || (echo Instalacja nieudana, sprawdz internet / installation failed, check the internet. & pause & exit /b 1)
)
echo.
echo Uruchamianie / starting: http://localhost:8501
streamlit run app.py
pause
