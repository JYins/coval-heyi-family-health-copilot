param(
    [int]$MaxRows = 5000,
    [switch]$RunDownloadOnLoginNode,
    [switch]$SkipDataPrepSubmit,
    [switch]$LivePrompts
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    python -m venv (Join-Path $repoRoot ".venv")
}

& $venvPython -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('paramiko') else 1)"
if ($LASTEXITCODE -ne 0) {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install paramiko
}

$argsList = @(
    (Join-Path $repoRoot "scripts\narval_paramiko_setup.py"),
    "--max-rows", "$MaxRows"
)

if ($RunDownloadOnLoginNode) {
    $argsList += "--run-download-on-login-node"
}
if ($SkipDataPrepSubmit) {
    $argsList += "--skip-data-prep-submit"
}
if ($LivePrompts) {
    $argsList += "--live-prompts"
}

& $venvPython @argsList
