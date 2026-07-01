param(
    [string]$RemoteRoot = "/home/syin94/scratch/lora_health",
    [int]$MaxRows = 5000,
    [switch]$SkipBaselineSubmit,
    [switch]$CopyToClipboard
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$outDir = Join-Path $repoRoot "results\remote_setup"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$archive = Join-Path $env:TEMP "lora_health_code_upload_$stamp.tgz"
$pasteScript = Join-Path $outDir "narval_paste_upload_$stamp.sh"

$items = @(
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    ".env.example",
    ".gitignore",
    "requirements-narval.txt",
    "configs",
    "data/dataset_manifest.json",
    "data/public",
    "docs",
    "eval",
    "scripts",
    "src",
    "train"
)

$existing = @()
foreach ($item in $items) {
    $path = Join-Path $repoRoot $item
    if (Test-Path -LiteralPath $path) {
        $existing += $item
    }
}

if ($existing.Count -eq 0) {
    throw "No uploadable project files found under $repoRoot"
}

if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive
}

$tarArgs = @("-czf", $archive, "-C", $repoRoot) + $existing
& tar @tarArgs
if ($LASTEXITCODE -ne 0) {
    throw "tar failed"
}

$bytes = [System.IO.File]::ReadAllBytes($archive)
$b64 = [Convert]::ToBase64String($bytes)
$lines = New-Object System.Collections.Generic.List[string]
for ($i = 0; $i -lt $b64.Length; $i += 76) {
    $len = [Math]::Min(76, $b64.Length - $i)
    $lines.Add($b64.Substring($i, $len))
}

$submitBaseline = if ($SkipBaselineSubmit) { "false" } else { "true" }
$body = @()
$body += "set -euo pipefail"
$body += "PROJECT_ROOT='$RemoteRoot'"
$body += "CODE_DIR=`"`$PROJECT_ROOT/code`""
$body += "mkdir -p `"`$PROJECT_ROOT/tmp`" `"`$PROJECT_ROOT/code`" `"`$PROJECT_ROOT/slurm_logs`""
$body += "cat > `"`$PROJECT_ROOT/tmp/code_upload.tgz.b64`" <<'LORA_HEALTH_ARCHIVE_B64'"
$body += $lines
$body += "LORA_HEALTH_ARCHIVE_B64"
$body += "base64 -d `"`$PROJECT_ROOT/tmp/code_upload.tgz.b64`" > `"`$PROJECT_ROOT/tmp/code_upload.tgz`""
$body += "tar -xzf `"`$PROJECT_ROOT/tmp/code_upload.tgz`" -C `"`$PROJECT_ROOT/code`""
$body += "cd `"`$PROJECT_ROOT/code`""
$body += "bash scripts/narval_bootstrap.sh"
$body += "cd `"`$PROJECT_ROOT`""
$body += "MAX_ROWS=$MaxRows sbatch code/scripts/submit_narval_data_prep.sh"
$body += "if [ `"$submitBaseline`" = true ]; then sbatch code/scripts/submit_narval_baseline.sh; fi"
$body += "bash code/scripts/narval_status.sh"

[System.IO.File]::WriteAllText($pasteScript, ($body -join "`n") + "`n", [System.Text.Encoding]::UTF8)

if ($CopyToClipboard) {
    Get-Content -LiteralPath $pasteScript -Raw | Set-Clipboard
    Write-Host "Paste script copied to clipboard."
}

Write-Host "Created paste upload script:"
Write-Host $pasteScript
Write-Host ""
Write-Host "Use:"
Write-Host "1. ssh narval"
Write-Host "2. cd /home/syin94/scratch/lora_health || true"
Write-Host "3. Paste the full script contents into the SSH session."
