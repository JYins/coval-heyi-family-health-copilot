param(
    [switch]$WhoamiOnly
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$repoRoot = Split-Path -Parent $PSScriptRoot
$hfExe = Join-Path $repoRoot ".venv\Scripts\hf.exe"

if (-not (Test-Path -LiteralPath $hfExe)) {
    throw "HF CLI not found at $hfExe. Install it with: .\.venv\Scripts\python.exe -m pip install -U huggingface_hub[hf_xet]"
}

if ($WhoamiOnly) {
    & $hfExe auth whoami
    exit $LASTEXITCODE
}

Write-Host "Hugging Face local CLI login"
Write-Host "This stores auth through the Hugging Face CLI. Do not paste tokens into repo files or chat logs."
Write-Host "Connector login is separate from local CLI login."
Write-Host ""

if ($env:HF_TOKEN) {
    Write-Host "HF_TOKEN is set for this shell. Verifying account..."
    & $hfExe auth whoami
    exit $LASTEXITCODE
}

Write-Host "No HF_TOKEN is set in this shell. Starting interactive login."
Write-Host "Paste a Hugging Face token when the CLI prompts for it."
& $hfExe auth login
