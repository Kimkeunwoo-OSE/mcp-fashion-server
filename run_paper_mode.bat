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

powershell -Command "(Get-Content .env) -replace '^RUN_MODE=.*','RUN_MODE=paper' ^| Set-Content .env"

echo [INFO] Running in PAPER mode.
start "" http://localhost:8501
streamlit run main.py

deactivate
pause
