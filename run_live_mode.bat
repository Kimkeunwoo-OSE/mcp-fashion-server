@echo off
setlocal
title v5_trader - Run (Live)

cd /d %~dp0

if not exist .venv (
  echo [ERROR] Missing venv. Run setup_and_run_mock.bat first.
  pause
  exit /b 1
)

call .\.venv\Scripts\activate

if not exist .env (
  echo [ERROR] Missing .env. Fill KIS keys/account before live run.
  pause
  exit /b 1
)

REM Basic sanity check for required keys
for %%V in (KIS_APP_KEY KIS_APP_SECRET KIS_ACC_NO) do (
  powershell -NoProfile -Command "if(-not (Select-String -Path '.env' -Pattern '^%%V=.+')){exit 1}" >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] %%V is empty in .env. Please set it and retry.
    pause
    exit /b 1
  )
)

powershell -NoProfile -Command "(Get-Content '.env') -replace '^RUN_MODE=.*','RUN_MODE=live'  | Set-Content '.env' -Encoding ASCII"

echo [INFO] Running in LIVE mode. Trade carefully!
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

deactivate
pause
