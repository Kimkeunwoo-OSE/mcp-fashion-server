@echo off
setlocal
title v5_trader - Build EXE

cd /d %~dp0

if not exist .venv (
  echo [ERROR] Missing venv. Run setup_and_run_mock.bat first.
  pause
  exit /b 1
)

call .\.venv\Scripts\activate

pip show pyinstaller >nul 2>&1 || pip install pyinstaller

set ICON_OPT=
if exist ui\assets\app.ico (
  set ICON_OPT=--icon=ui\assets\app.ico
)

echo [INFO] Building onefile EXE...
pyinstaller --noconfirm --onefile --name v5_trader %ICON_OPT% main.py

echo [INFO] Output: .\dist\v5_trader.exe
deactivate
pause
