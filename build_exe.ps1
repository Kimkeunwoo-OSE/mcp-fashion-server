param(
    [string]$Python = ".\.venv\Scripts\python.exe"
)

if (-not (Test-Path $Python)) {
    Write-Host "Python 가상환경을 찾을 수 없습니다. 먼저 .venv를 생성하세요." -ForegroundColor Yellow
    exit 1
}

$Pip = [System.IO.Path]::Combine((Split-Path $Python), "pip.exe")

& $Pip install --upgrade pip > $null
& $Pip install pyinstaller > $null

$pyinstaller = [System.IO.Path]::Combine((Split-Path $Python), "pyinstaller.exe")

& $pyinstaller `
    --name v5_trader `
    --onefile `
    --noconsole `
    --hidden-import=winotify `
    --collect-all streamlit `
    --collect-all plotly `
    --collect-all pywebview `
    --add-data "app;app" `
    --add-data "config;config" `
    -m app.__main__

Write-Host "빌드가 완료되었습니다. dist\v5_trader.exe 를 확인하세요." -ForegroundColor Green
