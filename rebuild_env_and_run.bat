@echo off

setlocal enabledelayedexpansion

title v5_trader - Rebuild venv & Run (Mock)

REM === Move to repo root ===
cd /d %~dp0

REM === Remove existing venv ===
if exist .venv (
  echo [INFO] Removing existing virtual environment...
  rmdir /s /q .venv
)

REM === Create new venv (prefer Python 3.10) ===
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
if errorlevel 1 (
  echo [ERROR] Failed to create virtual environment.
  pause
  exit /b 1
)

REM === Activate venv ===
call .\.venv\Scripts\activate

REM === Check Python version ===
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

REM === Install dependencies ===
if exist requirements.txt (
  echo [INFO] Upgrading pip and installing requirements...
  pip install --upgrade pip
  pip install -r requirements.txt
) else (
  echo [WARN] requirements.txt not found. Skipping installation.
)

REM === Prepare .env ===
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

REM === Force RUN_MODE=mock ===
powershell -NoProfile -Command "(Get-Content '.env') -replace '^RUN_MODE=.*','RUN_MODE=mock' | Set-Content '.env' -Encoding ASCII"

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
