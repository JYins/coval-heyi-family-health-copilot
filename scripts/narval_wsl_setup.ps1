param(
    [string]$WslDistro = "Ubuntu-22.04",
    [string]$HostAlias = "narval",
    [string]$RemoteRoot = "/home/syin94/scratch/lora_health",
    [int]$MaxRows = 5000,
    [switch]$SkipBootstrap,
    [switch]$SkipDataPrepSubmit,
    [switch]$SubmitSftV3,
    [switch]$SubmitSftV3Eval,
    [switch]$SkipStatus
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..")
$logDir = Join-Path $repoRoot "results\remote_setup"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$archive = Join-Path $logDir "lora_health_code_upload_$stamp.tgz"
$remoteArchive = "${RemoteRoot}/tmp/code_upload.tgz"

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

function Run-Step {
    param(
        [string]$Name,
        [scriptblock]$Body
    )
    Write-Host ""
    Write-Host "== $Name =="
    & $Body
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Name"
    }
}

function Invoke-Wsl {
    param(
        [string[]]$Arguments,
        [int]$Attempts = 3
    )
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        & wsl -d $WslDistro -- @Arguments
        if ($LASTEXITCODE -eq 0) {
            return
        }
        if ($attempt -lt $Attempts) {
            Write-Host "Command failed; retrying in 3s ($attempt/$Attempts)."
            Start-Sleep -Seconds 3
        }
    }
}

function Wsl-Path {
    param([string]$WindowsPath)
    $resolved = Resolve-Path -LiteralPath $WindowsPath
    $drive = $resolved.Path.Substring(0, 1).ToLowerInvariant()
    $rest = $resolved.Path.Substring(2).Replace("\", "/")
    return "/mnt/$drive$rest"
}

Write-Host "Narval WSL setup for lora_health"
Write-Host "Requires an existing WSL OpenSSH ControlMaster session."
Write-Host "No passwords, MFA codes, private keys, or private data are written by this script."

Run-Step "Check WSL SSH master" {
    Invoke-Wsl -Arguments @("ssh", "-O", "check", $HostAlias)
}

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

Run-Step "Pack safe repo subset" {
    if (Test-Path -LiteralPath $archive) {
        Remove-Item -LiteralPath $archive
    }
    $tarArgs = @("-czf", $archive, "-C", $repoRoot) + $existing
    & tar @tarArgs
}

$wslArchive = Wsl-Path -WindowsPath $archive

Run-Step "Upload archive through WSL scp" {
    Invoke-Wsl -Arguments @("scp", $wslArchive, "${HostAlias}:$remoteArchive")
}

Run-Step "Extract archive on Narval" {
    Invoke-Wsl -Arguments @("ssh", $HostAlias, "tar", "-xzf", $remoteArchive, "-C", "${RemoteRoot}/code")
}

if (-not $SkipBootstrap) {
    Run-Step "Remote bootstrap" {
        Invoke-Wsl -Arguments @("ssh", $HostAlias, "bash", "${RemoteRoot}/code/scripts/narval_bootstrap.sh")
    }
}

if (-not $SkipDataPrepSubmit) {
    Run-Step "Submit data-prep Slurm job" {
        Invoke-Wsl -Arguments @("ssh", $HostAlias, "sbatch", "--export=ALL,MAX_ROWS=$MaxRows", "${RemoteRoot}/code/scripts/submit_narval_data_prep.sh")
    }
}

if ($SubmitSftV3) {
    Run-Step "Submit SFT v3 Slurm job" {
        Invoke-Wsl -Arguments @("ssh", $HostAlias, "sbatch", "--export=ALL,LORA_HEALTH_APPROVED_SFT_V3=1", "${RemoteRoot}/code/scripts/submit_narval_sft_v3.sh")
    }
}

if ($SubmitSftV3Eval) {
    Run-Step "Submit SFT v3 eval Slurm job" {
        Invoke-Wsl -Arguments @("ssh", $HostAlias, "sbatch", "${RemoteRoot}/code/scripts/submit_narval_sft_v3_eval.sh")
    }
}

if (-not $SkipStatus) {
    Run-Step "Remote status" {
        Invoke-Wsl -Arguments @("ssh", $HostAlias, "bash", "${RemoteRoot}/code/scripts/narval_status.sh")
    }
}

Write-Host ""
Write-Host "Done. Uploaded archive: $archive"
