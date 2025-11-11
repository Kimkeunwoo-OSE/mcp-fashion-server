param(
    [switch]$NoFrontend
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment (.venv)" -ForegroundColor Cyan
    py -3.11 -m venv .venv
}

$py = ".\.venv\Scripts\python.exe"
$pip = ".\.venv\Scripts\pip.exe"

& $py -m pip install --upgrade pip setuptools wheel
& $pip install -r requirements.txt

if (-not $NoFrontend) {
    if (-not (Test-Path "app_desktop/node_modules")) {
        Push-Location app_desktop
        npm install
        Pop-Location
    }
}

Start-Process -FilePath $py -ArgumentList '-m','uvicorn','api.main:app','--reload','--port','5173' -NoNewWindow

if (-not $NoFrontend) {
    Start-Process -FilePath 'npm' -ArgumentList 'run','tauri','dev' -NoNewWindow -WorkingDirectory 'app_desktop'
}

Write-Host "FastAPI dev server started on http://127.0.0.1:5173"
if (-not $NoFrontend) {
    Write-Host "Tauri dev console launched. Press Ctrl+C in each window to stop."
}
