@echo off

setlocal enabledelayedexpansion

title v5_trader - Run (Live)

cd /d %~dp0

set "VENV_DIR=%~dp0\.venv"

set "VENV_PY=%VENV_DIR%\Scripts\python.exe"



if not exist "%VENV_PY%" (

  where py >nul 2>nul

  if not errorlevel 1 (

    py -3.11 -m venv "%VENV_DIR%" 2>nul || py -3.10 -m venv "%VENV_DIR%" 2>nul || py -m venv "%VENV_DIR%"

  ) else (

    python -m venv "%VENV_DIR%"

  )

)

if not exist "%VENV_PY%" (

  echo [ERROR] Failed to create venv at "%VENV_DIR%".

  echo Please install Python 3.10 or 3.11 and re-run.

  pause & exit /b 1

)



"%VENV_PY%" --version

for /f "tokens=1,2 delims= " %%A in ('"%VENV_PY%" --version') do set VER=%%B

for /f "usebackq tokens=1,2 delims=." %%M in (`"%VENV_PY%" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"`) do set MAJOR=%%M& set MINOR=%%N

if "%MAJOR%"=="3" (

  if %MINOR% LSS 10 (

    echo [ERROR] Venv Python is 3.%MINOR%. Install Python 3.10/3.11 and recreate .venv.

    pause & exit /b 1

  )

) else (

  echo [ERROR] Unexpected Python version in venv: %VER%

  pause & exit /b 1

)

echo [INFO] Detected Python version: %VER%



if exist requirements.txt (

  "%VENV_PY%" -m pip install --upgrade pip

  "%VENV_PY%" -m pip install -r requirements.txt

) else (

  echo [WARN] requirements.txt not found. Skipping this step.

)



if not exist .env (

  echo [ERROR] Missing .env. Fill KIS keys/account before live run.

  pause & exit /b 1

)



for %%V in (KIS_APP_KEY KIS_APP_SECRET KIS_ACC_NO) do (

  powershell -NoProfile -Command "if(-not (Select-String -Path '.env' -Pattern '^%%V=.+')){exit 1}" >nul 2>&1

  if errorlevel 1 (

    echo [ERROR] %%V is empty in .env. Please set it and retry.

    pause & exit /b 1

  )

)



powershell -NoProfile -Command "(Get-Content '.env') -replace '^RUN_MODE=.*','RUN_MODE=live'  | Set-Content '.env' -Encoding ASCII"



echo [INFO] Running in LIVE mode. Trade carefully!

set "ENTRY=main.py"

if not exist "%ENTRY%" if exist "v5_trader\main.py" set "ENTRY=v5_trader\main.py"

if not exist "%ENTRY%" if exist "src\main.py" set "ENTRY=src\main.py"

if not exist "%ENTRY%" if exist "app\main.py" set "ENTRY=app\main.py"

if not exist "%ENTRY%" (

  echo [ERROR] Could not find main.py. Tried .\main.py, .\v5_trader\main.py, .\src\main.py, .\app\main.py

  pause & exit /b 1

)

echo [INFO] Launching Streamlit with "%ENTRY%"

start "" http://localhost:8501

"%VENV_PY%" -m streamlit run "%ENTRY%"

echo [DONE] Live run finished.

pause

