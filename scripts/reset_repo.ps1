param(
    [string]$Branch = "fix/rewrite-windows-toast"
)

Write-Host "[reset_repo] Checking out orphan branch: $Branch"
git checkout --orphan $Branch

Write-Host "[reset_repo] Removing tracked files"
git rm -r --cached . 2>$null

Write-Host "[reset_repo] Cleaning working tree"
git clean -fdx

Write-Host "[reset_repo] Removing residual files (except .git)"
Get-ChildItem -Force | Where-Object { $_.Name -ne ".git" } | Remove-Item -Recurse -Force

Write-Host "[reset_repo] Repository reset complete. Create new scaffold before committing."
