$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$gitDir = Join-Path $root ".git"
if (-not (Test-Path -LiteralPath $gitDir)) {
    throw "No .git directory found under $root"
}

$hooksDir = Join-Path $gitDir "hooks"
New-Item -ItemType Directory -Force -Path $hooksDir | Out-Null
Copy-Item -LiteralPath (Join-Path $root "scripts\hooks\pre-commit") -Destination (Join-Path $hooksDir "pre-commit") -Force

Write-Host "Installed pre-commit hook."

