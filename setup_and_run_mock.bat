@echo off

setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"



rem === venv paths ===

set "VENV_DIR=%~dp0\.venv"

set "VENV_PY=%VENV_DIR%\Scripts\python.exe"



rem === logs ===

if not exist "%~dp0logs" mkdir "%~dp0logs"

set "STAMP=%DATE:~-4%%DATE:~0,2%%DATE:~3,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"

set "STAMP=%STAMP: =0%"

set "LOG=%~dp0logs\launcher_%STAMP%.log"



echo [INFO] Log file: "%LOG%"

echo [INFO] Working dir: "%cd%" >> "%LOG%" 2>&1

echo [INFO] Using venv at "%VENV_DIR%" >> "%LOG%" 2>&1



if not exist "%VENV_PY%" (

  echo [INFO] Creating virtual environment... | tee -a "%LOG%"

  where py >nul 2>&1

  if not errorlevel 1 (

    py -3.11 -m venv "%VENV_DIR%" >> "%LOG%" 2>&1 || py -3.10 -m venv "%VENV_DIR%" >> "%LOG%" 2>&1 || py -m venv "%VENV_DIR%" >> "%LOG%" 2>&1

  ) else (

    python -m venv "%VENV_DIR%" >> "%LOG%" 2>&1

  )

)

if not exist "%VENV_PY%" (

  echo [ERROR] Failed to create venv at "%VENV_DIR%". See "%LOG%".

  type "%LOG%" | more

  pause

  exit /b 1

)



"%VENV_PY%" --version | tee -a "%LOG%"

for /f "usebackq tokens=1,2 delims= " %%A in (`"%VENV_PY%" --version`) do set VER=%%B

for /f "usebackq tokens=1,2 delims=." %%M in (`"%VENV_PY%" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"`) do set MAJOR=%%M& set MINOR=%%N

if "%MAJOR%"=="3" (

  if %MINOR% LSS 10 (

    echo [ERROR] Venv Python is 3.%MINOR%. Install Python 3.10/3.11 and recreate .venv. | tee -a "%LOG%"

    type "%LOG%" | more

    pause

    exit /b 1

  )

) else (

  echo [ERROR] Unexpected Python version in venv: %VER% | tee -a "%LOG%"

  type "%LOG%" | more

  pause

  exit /b 1

)

echo [INFO] Detected Python version: %VER% | tee -a "%LOG%"



if exist requirements.txt (

  echo [INFO] Installing requirements... | tee -a "%LOG%"

  "%VENV_PY%" -m pip install --upgrade pip >> "%LOG%" 2>&1 || goto :fail

  "%VENV_PY%" -m pip install -r requirements.txt >> "%LOG%" 2>&1 || goto :fail

)



if not exist .env (

  echo [INFO] Creating default .env template. | tee -a "%LOG%"

  (

    echo RUN_MODE=mock

    echo KIS_APP_KEY=

    echo KIS_APP_SECRET=

    echo KIS_ACC_NO=12345678-01

    echo TELEGRAM_BOT_TOKEN=

    echo TELEGRAM_CHAT_ID=

  ) > .env

)



powershell -NoProfile -Command "(Get-Content '.env') -replace '^RUN_MODE=.*','RUN_MODE=mock' | Set-Content '.env' -Encoding ASCII"



set "ENTRY=main.py"

if not exist "%ENTRY%" if exist "v5_trader\main.py" set "ENTRY=v5_trader\main.py"

if not exist "%ENTRY%" if exist "src\main.py" set "ENTRY=src\main.py"

if not exist "%ENTRY%" if exist "app\main.py" set "ENTRY=app\main.py"

if not exist "%ENTRY%" (

  echo [ERROR] Could not find main.py. Tried .\main.py, .5_trader\main.py, .\src\main.py, .pp\main.py | tee -a "%LOG%"

  goto :fail

)

echo [INFO] Launching Streamlit with "%ENTRY%" | tee -a "%LOG%"

echo [INFO] Launching Streamlit... | tee -a "%LOG%"

start "" http://localhost:8501

"%VENV_PY%" -m streamlit run "%ENTRY%" >> "%LOG%" 2>&1 || goto :fail

echo [INFO] Streamlit session ended. | tee -a "%LOG%"

pause

goto :eof



:fail

echo.

echo [ERROR] Launcher failed. Last 80 log lines from: "%LOG%"

powershell -NoProfile -Command "Get-Content -Path '%LOG%' -Tail 80"

echo.

echo [HINT] Scroll up in this window or open the full log:

echo        %LOG%

pause

exit /b 1

