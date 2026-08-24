param(
    [switch]$Install,
    [switch]$SkipBrowser
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$web = Join-Path $root "apps\coval-health-web"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
$npm = if ($IsWindows -or $env:OS -eq "Windows_NT") { "npm.cmd" } else { "npm" }
$npx = if ($IsWindows -or $env:OS -eq "Windows_NT") { "npx.cmd" } else { "npx" }

function Run-Step {
    param([string]$Name, [scriptblock]$Body)
    Write-Host "== $Name =="
    & $Body
    if ($LASTEXITCODE -ne 0) {
        throw "Quality step failed: $Name"
    }
}

Set-Location $root

if ($Install) {
    Run-Step "install backend dependencies" {
        & $python -m pip install -r requirements-dev.txt
    }
    Run-Step "install frontend dependencies" {
        Set-Location $web
        & $npm ci
        Set-Location $root
    }
    if (-not $SkipBrowser) {
        Run-Step "install Playwright Chromium" {
            Set-Location $web
            & $npx playwright install chromium
            Set-Location $root
        }
    }
}

Run-Step "workflow policy" {
    & $python scripts\check_workflow.py
}

Run-Step "backend unit, contract, and process-restart tests" {
    & $python -m unittest discover -s tests -v
}

Run-Step "frontend lint" {
    Set-Location $web
    & $npm run lint
    Set-Location $root
}

Run-Step "frontend typecheck" {
    Set-Location $web
    & $npm run typecheck
    Set-Location $root
}

Run-Step "frontend production build" {
    Set-Location $web
    try {
        & $npm run build
    } finally {
        Set-Location $root
    }
}

if (-not $SkipBrowser) {
    Run-Step "browser E2E" {
        Set-Location $web
        & $npm run test:e2e
        Set-Location $root
    }
    Run-Step "restore default Next generated types" {
        Set-Location $web
        & $npm run typegen
        Set-Location $root
    }
}

Write-Host "local quality checks ok"
