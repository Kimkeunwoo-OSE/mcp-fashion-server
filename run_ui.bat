@echo off
REM venv 활성화(있다면)
IF EXIST .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
)
python -m app --ui
