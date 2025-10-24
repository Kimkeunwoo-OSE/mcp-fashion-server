@echo off
setlocal
title v5_trader - Test Alerts

cd /d %~dp0
if not exist .venv (
  echo [ERROR] Missing venv. Run setup_and_run_mock.bat first.
  pause
  exit /b 1
)

call .\.venv\Scripts\activate

echo [INFO] Sending Telegram test message...
python - <<PY
try:
    from notify.telegram import send_msg  # Ensure module path matches your repo
    send_msg("v5_trader alert test: 🚀 Notification works.")
    print("[OK] Telegram message sent.")
except Exception as e:
    print("[ERROR] Telegram test failed:", e)
PY

REM If you have a desktop toast module, uncomment next line and adjust import:
REM python -c "from notify.toast import show_toast; show_toast('v5_trader', 'Alert test OK')"

deactivate
pause
