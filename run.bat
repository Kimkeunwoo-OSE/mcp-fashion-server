@echo off
REM v5 Trader (Rewrite, Windows Toast Edition) launcher

if not exist .venv (
    echo Creating Python 3.11 virtual environment...
    py -3.11 -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -r requirements.txt
python -m app %*
