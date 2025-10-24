@echo off
setlocal enabledelayedexpansion
title v5_trader - Setup & Run (Mock)

REM === 0) Move to repo root ===
cd /d %~dp0

REM === 1) Check Python ===
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Install from https://www.python.org/ and rerun.
  pause
  exit /b 1
)

REM === 2) Create venv if missing ===
if not exist .venv (
  echo [INFO] Creating virtual environment...
  set "VENV_CMD="
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.10 -V >nul 2>nul
    if not errorlevel 1 (
      set "VENV_CMD=py -3.10"
    )
  )
  if not defined VENV_CMD set "VENV_CMD=python"
  %VENV_CMD% -m venv .venv
)

REM === 3) Activate venv ===
call .\.venv\Scripts\activate

REM === 4) Inspect Python version ===
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_FULL=%%v"
if not defined PY_FULL set "PY_FULL=unknown"
echo [INFO] Detected Python version: !PY_FULL!
for /f "tokens=1,2 delims=." %%a in ("!PY_FULL!") do (
  set "PY_MAJOR=%%a"
  set "PY_MINOR=%%b"
)
if defined PY_MAJOR (
  if !PY_MAJOR! LSS 3 (
    echo [WARN] Python 3.10 or newer is required. Detected: !PY_FULL!
  ) else (
    if !PY_MINOR! LSS 10 (
      echo [WARN] Python 3.10 or newer is required. Detected: !PY_FULL!
    )
  )
)

REM === 5) Install requirements ===
if exist requirements.txt (
  echo [INFO] Installing requirements...
  pip install --upgrade pip
  pip install -r requirements.txt
) else (
  echo [WARN] requirements.txt not found. Skipping this step.
)

REM === 6) Prepare .env (create if missing) ===
if not exist .env (
  echo [INFO] Creating default .env template.
  (
    echo RUN_MODE=mock
    echo KIS_APP_KEY=
    echo KIS_APP_SECRET=
    echo KIS_ACC_NO=12345678-01
    echo TELEGRAM_BOT_TOKEN=
    echo TELEGRAM_CHAT_ID=
  ) > .env
)

REM === 7) Force RUN_MODE=mock ===
powershell -NoProfile -Command "(Get-Content '.env') -replace '^RUN_MODE=.*','RUN_MODE=mock' | Set-Content '.env' -Encoding ASCII"

REM === 8) Run app ===
echo [INFO] Launching Streamlit (Mock)
REM === Entry file detection ===
set ENTRY=main.py
if not exist "%ENTRY%" if exist "v5_trader\main.py" set ENTRY=v5_trader\main.py
if not exist "%ENTRY%" if exist "src\main.py" set ENTRY=src\main.py
if not exist "%ENTRY%" if exist "app\main.py" set ENTRY=app\main.py
if not exist "%ENTRY%" (
  echo [ERROR] Could not find main.py. Check your repo structure.
  echo Tried: .\main.py, .\v5_trader\main.py, .\src\main.py, .\app\main.py
  pause
  exit /b 1
)
echo [INFO] Launching Streamlit with "%ENTRY%"
start "" http://localhost:8501
streamlit run "%ENTRY%"

REM === 9) Cleanup ===
deactivate
echo [DONE] Mock run finished.
pause
