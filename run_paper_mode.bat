@echo off
setlocal
title v5_trader - Run (Paper/Mock)

cd /d %~dp0

if not exist .venv (
  echo [ERROR] Missing venv. Run setup_and_run_mock.bat first.
  pause
  exit /b 1
)

call .\.venv\Scripts\activate

if not exist .env (
  echo [ERROR] Missing .env. Run setup_and_run_mock.bat to generate it.
  pause
  exit /b 1
)

powershell -NoProfile -Command "(Get-Content '.env') -replace '^RUN_MODE=.*','RUN_MODE=paper' | Set-Content '.env' -Encoding ASCII"

echo [INFO] Running in PAPER mode.
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
