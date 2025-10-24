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
  python -m venv .venv
)

REM === 3) Activate venv ===
call .\.venv\Scripts\activate

REM === 4) Install requirements ===
if exist requirements.txt (
  echo [INFO] Installing requirements...
  pip install --upgrade pip
  pip install -r requirements.txt
) else (
  echo [WARN] requirements.txt not found. Skipping this step.
)

REM === 5) Prepare .env (create if missing) ===
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

REM === 6) Force RUN_MODE=mock ===
powershell -Command "(Get-Content .env) -replace '^RUN_MODE=.*','RUN_MODE=mock' ^| Set-Content .env"

REM === 7) Run app ===
echo [INFO] Launching Streamlit (Mock)
start "" http://localhost:8501
streamlit run main.py

REM === 8) Cleanup ===
deactivate
echo [DONE] Mock run finished.
pause
