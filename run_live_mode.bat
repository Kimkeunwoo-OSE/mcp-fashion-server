@echo off
setlocal enabledelayedexpansion
title v5_trader - Run (Live)

cd /d %~dp0

if not exist .venv (
  echo [ERROR] Missing venv. Run setup_and_run_mock.bat first.
  pause
  exit /b 1
)

call .\.venv\Scripts\activate

python --version
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_FULL=%%v"
if not defined PY_FULL set "PY_FULL=unknown"
echo [INFO] Detected Python version: !PY_FULL!
for /f "tokens=1,2 delims=." %%a in ("!PY_FULL!") do (
  set "PY_MAJOR=%%a"
  set "PY_MINOR=%%b"
)
set "PY_OK=1"
if not defined PY_MAJOR set "PY_OK=0"
if defined PY_MAJOR (
  if !PY_MAJOR! LSS 3 set "PY_OK=0"
  if !PY_MAJOR! EQU 3 if !PY_MINOR! LSS 10 set "PY_OK=0"
)
if "!PY_OK!"=="0" (
  echo [ERROR] Python version is below 3.10. You must install Python 3.10 or 3.11 and recreate the .venv.
  deactivate
  pause
  exit /b 1
)
set "PYTHON_EXE=%~dp0\.venv\Scripts\python.exe"

if not exist .env (
  echo [ERROR] Missing .env. Fill KIS keys/account before live run.
  deactivate
  pause
  exit /b 1
)

REM Basic sanity check for required keys
for %%V in (KIS_APP_KEY KIS_APP_SECRET KIS_ACC_NO) do (
  powershell -NoProfile -Command "if(-not (Select-String -Path '.env' -Pattern '^%%V=.+')){exit 1}" >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] %%V is empty in .env. Please set it and retry.
    deactivate
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
  deactivate
  pause
  exit /b 1
)
echo [INFO] Launching Streamlit with "%ENTRY%"
start "" http://localhost:8501
"%PYTHON_EXE%" -m streamlit run "%ENTRY%"

deactivate
pause
