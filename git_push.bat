@echo off
setlocal
title v5_trader - Git Commit & Push

cd /d %~dp0

where git >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Git not found. Install from https://git-scm.com
  pause
  exit /b 1
)

git add .
set /p MSG=[input] Commit message: 
if "%MSG%"=="" set MSG=chore: update

git commit -m "%MSG%"
git branch >nul 2>&1 || git branch -M main
git remote -v >nul 2>&1 || (
  echo [WARN] No remote configured. Set origin like:
  echo git remote add origin https://github.com/USER/v5-trader.git
  pause
  exit /b 0
)

git push -u origin main
echo [DONE] Git push completed.
pause
