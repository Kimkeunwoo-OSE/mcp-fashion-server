param(
  [string]$InFile = "assets/app.ico.b64.txt",
  [string]$OutFile = "assets/app.ico"
)

if (!(Test-Path $InFile)) {
  Write-Error "Input base64 file not found: $InFile"
  exit 1
}

$b64 = Get-Content -Raw -Path $InFile
$bytes = [System.Convert]::FromBase64String($b64)
[IO.File]::WriteAllBytes($OutFile, $bytes)
Write-Host "Restored icon -> $OutFile"
