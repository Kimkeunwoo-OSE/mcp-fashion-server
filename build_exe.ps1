$ErrorActionPreference = "Stop"

$py = ".\.venv\Scripts\python.exe"
$pip = ".\.venv\Scripts\pip.exe"
$pyi = ".\.venv\Scripts\pyinstaller.exe"

if (-not (Test-Path $py)) {
  Write-Error "Python 가상환경(.venv)을 찾을 수 없습니다."
}

& $pip install -U pip
& $pip install pyinstaller

powershell -ExecutionPolicy Bypass -File scripts\restore_icon.ps1

& $pyi `
  --name v5_trader `
  --onefile `
  --noconsole `
  --hidden-import=winotify `
  --collect-all streamlit `
  --collect-all plotly `
  --collect-all pywebview `
  --add-data "app;app" `
  --add-data "config;config" `
  --icon "assets/app.ico" `
  -m app.__main__

Write-Host "Build done: dist\\v5_trader.exe"
