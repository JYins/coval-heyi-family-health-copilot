param(
    [string]$HostAlias = "narval",
    [string]$HostName = "",
    [string]$UserName = "",
    [string]$RemoteRoot = "/home/syin94/scratch/lora_health",
    [int]$MaxRows = 5000,
    [switch]$RunDownloadOnLoginNode,
    [switch]$SkipDataPrepSubmit,
    [switch]$EnableMux,
    [switch]$SkipUpload
)

$ErrorActionPreference = "Stop"

$target = $HostAlias
if ($HostName -and $UserName) {
    $target = "${UserName}@${HostName}"
}
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..")
$logDir = Join-Path $repoRoot "results\remote_setup"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDir "narval_setup_$stamp.log"
$controlPath = Join-Path $env:TEMP "lh_narval_mux"
$sshOptions = @("-tt")
$scpOptions = @("-O")

if ($EnableMux) {
    $sshOptions = @(
        "-tt",
        "-o", "ControlMaster=auto",
        "-o", "ControlPersist=30m",
        "-o", "ControlPath=$controlPath"
    ) + $sshOptions
    $scpOptions = @(
        "-o", "ControlMaster=auto",
        "-o", "ControlPersist=30m",
        "-o", "ControlPath=$controlPath"
    ) + $scpOptions
}

function Run-Step {
    param(
        [string]$Name,
        [scriptblock]$Body
    )
    Write-Host ""
    Write-Host "== $Name =="
    Add-Content -LiteralPath $logPath -Value "== $Name =="
    & $Body
    $exitCode = $LASTEXITCODE
    Add-Content -LiteralPath $logPath -Value "exit=$exitCode"
    if ($exitCode -ne 0) {
        throw "Step failed: $Name"
    }
}

Write-Host "Narval one-shot setup for lora_health"
Write-Host "Native OpenSSH will prompt for key passphrase, Narval password, and MFA if needed."
Write-Host "If asked for local key passphrase and the key has no passphrase, press Enter."
Write-Host "Secrets stay in the SSH prompt, not in files."
if ($EnableMux) {
    Write-Host "SSH connection reuse enabled."
} else {
    Write-Host "Using plain ssh/scp with no auth options for Narval compatibility; you may be prompted more than once."
}
Write-Host "Local log: $logPath"

Run-Step "Establish SSH control connection" {
    ssh @sshOptions $target "mkdir -p '${RemoteRoot}/tmp' '${RemoteRoot}/code' '${RemoteRoot}/slurm_logs' && printf 'connected_to=' && hostname && whoami && pwd"
}

if (-not $SkipUpload) {
    Run-Step "Upload repo safe subset" {
        & (Join-Path $scriptRoot "narval_upload_repo.ps1") `
            -HostName $HostName `
            -UserName $UserName `
            -HostAlias $HostAlias `
            -RemoteRoot $RemoteRoot `
            -SshOptions $sshOptions `
            -ScpOptions $scpOptions
    }
} else {
    Add-Content -LiteralPath $logPath -Value "== Upload repo safe subset =="
    Add-Content -LiteralPath $logPath -Value "skipped_by_user=true"
}

Run-Step "Remote bootstrap" {
    ssh @sshOptions $target "tar -xzf '${RemoteRoot}/tmp/code_upload.tgz' -C '${RemoteRoot}/code' && cd '${RemoteRoot}/code' && bash scripts/narval_bootstrap.sh"
}

if ($RunDownloadOnLoginNode) {
    Run-Step "Download public datasets on login node" {
        ssh @sshOptions $target "cd '${RemoteRoot}/code' && MAX_ROWS=${MaxRows} bash scripts/narval_pull_data.sh"
    }
}
elseif (-not $SkipDataPrepSubmit) {
    Run-Step "Submit CPU data-prep Slurm job" {
        ssh @sshOptions $target "cd '${RemoteRoot}' && MAX_ROWS=${MaxRows} sbatch code/scripts/submit_narval_data_prep.sh"
    }
}

Run-Step "Remote status" {
    ssh @sshOptions $target "cd '${RemoteRoot}' && bash code/scripts/narval_status.sh"
}

Write-Host ""
Write-Host "Done. Status log: $logPath"

try {
    if ($EnableMux) {
        ssh @sshOptions -O exit $target 2>$null | Out-Null
    }
} catch {
    Write-Host "SSH control connection cleanup skipped."
}
