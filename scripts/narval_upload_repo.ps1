param(
    [string]$HostAlias = "narval",
    [string]$HostName = "",
    [string]$UserName = "",
    [string]$RemoteRoot = "/home/syin94/scratch/lora_health",
    [string[]]$SshOptions = @(),
    [string[]]$ScpOptions = @()
)

$ErrorActionPreference = "Stop"

$localRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$target = $HostAlias
if ($HostName -and $UserName) {
    $target = "${UserName}@${HostName}"
}
$remoteArchive = "${target}:${RemoteRoot}/tmp/code_upload.tgz"
$archive = Join-Path $env:TEMP "lora_health_code_upload.tgz"

Write-Host "Packing safe project files from $localRoot"
Write-Host "This script intentionally excludes .env, data/private, checkpoints, models, outputs, and graphify-out."

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

if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive
}

$existing = @()
foreach ($item in $items) {
    $path = Join-Path $localRoot $item
    if (Test-Path -LiteralPath $path) {
        $existing += $item
    }
}

if ($existing.Count -eq 0) {
    throw "No uploadable project files found under $localRoot"
}

$tarArgs = @("-czf", $archive, "-C", $localRoot) + $existing
& tar @tarArgs

scp @ScpOptions $archive $remoteArchive

Write-Host "Archive upload complete: ${RemoteRoot}/tmp/code_upload.tgz"
