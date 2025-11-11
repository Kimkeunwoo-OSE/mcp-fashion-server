@echo off
REM v5 Trader desktop dev helper

if not exist .venv (
    echo Creating Python 3.11 virtual environment...
    py -3.11 -m venv .venv
)

call .venv\Scriptsctivate.bat
pip install -r requirements.txt

if not exist app_desktop
ode_modules (
    pushd app_desktop
    npm install
    popd
)

powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
