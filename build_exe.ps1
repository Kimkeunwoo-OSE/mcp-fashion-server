$ErrorActionPreference = "Stop"

if (-not (Test-Path '.venv')) {
  Write-Host 'Creating Python virtual environment (.venv)' -ForegroundColor Cyan
  py -3.11 -m venv .venv
}

$py = '.\.venv\Scripts\python.exe'
$pip = '.\.venv\Scripts\pip.exe'

& $py -m pip install --upgrade pip setuptools wheel
& $pip install -r requirements.txt

if (-not (Test-Path 'app_desktop/node_modules')) {
  Push-Location app_desktop
  npm install
  Pop-Location
}

powershell -ExecutionPolicy Bypass -File scripts\restore_icon.ps1

Push-Location app_desktop
npm run tauri build
Pop-Location

Write-Host 'Tauri build completed. Check app_desktop/src-tauri/target/release for binaries.'
