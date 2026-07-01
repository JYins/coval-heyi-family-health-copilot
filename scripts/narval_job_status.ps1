param(
    [string]$JobId = "",
    [string]$RemoteResultDir = "/home/syin94/scratch/lora_health/results/sft_v1_eval_v1_1/safety_onset_edge_v1_1",
    [string]$RemoteLogGlob = "/home/syin94/scratch/lora_health/slurm_logs/lora_health_*"
)

$ErrorActionPreference = "Stop"

$projectRoot = "/home/syin94/scratch/lora_health"
$thesisRoot = "/home/syin94/scratch/MEng_Project"

if ($JobId -and ($JobId -notmatch '^[0-9]+([_.][0-9]+)?$')) {
    throw "Refusing unsafe JobId: $JobId"
}

if (-not $RemoteResultDir.StartsWith($projectRoot)) {
    throw "Refusing result dir outside ${projectRoot}: $RemoteResultDir"
}

if (-not $RemoteLogGlob.StartsWith("${projectRoot}/slurm_logs/")) {
    throw "Refusing log glob outside ${projectRoot}/slurm_logs: $RemoteLogGlob"
}

$remoteLogName = Split-Path -Leaf $RemoteLogGlob
if (-not $remoteLogName.StartsWith("lora_health_")) {
    throw "Refusing non-lora_health log glob: $RemoteLogGlob"
}

Write-Host "Narval lora_health job status"
Write-Host "This script reuses the WSL OpenSSH ControlMaster only; it does not store credentials."

& wsl -d Ubuntu-22.04 -- ssh -O check narval
if ($LASTEXITCODE -ne 0) {
    throw "No active WSL ControlMaster for narval. Open one with: wsl -d Ubuntu-22.04 -- ssh -N narval"
}

$remoteLines = New-Object System.Collections.Generic.List[string]
$remoteLines.Add("set -euo pipefail")
$remoteLines.Add("PROJECT_ROOT='$projectRoot'")
$remoteLines.Add("THESIS_ROOT='$thesisRoot'")
$remoteLines.Add("RESULT_DIR='$RemoteResultDir'")
$remoteLines.Add("LOG_NAME='$remoteLogName'")
$remoteLines.Add("cd ""`$PROJECT_ROOT""")
$remoteLines.Add("PROJECT_REAL=`$(realpath -m ""`$PROJECT_ROOT"")")
$remoteLines.Add("PWD_REAL=`$(pwd -P)")
$remoteLines.Add("case ""`$PWD_REAL"" in ""`$PROJECT_REAL""*) ;; *) echo ""Refusing unsafe cwd: `$PWD_REAL"" >&2; exit 2 ;; esac")
$remoteLines.Add("echo '== identity =='")
$remoteLines.Add("hostname; whoami; pwd; date -u +%Y-%m-%dT%H:%M:%SZ")
$remoteLines.Add("echo")
$remoteLines.Add("echo '== lora_health queue =='")
$remoteLines.Add("squeue -u `$(whoami) -o '%i|%j|%T|%M|%R' | grep -E 'JOBID|lora_health' || true")

if ($JobId) {
    $remoteLines.Add("echo")
    $remoteLines.Add("echo '== squeue job $JobId =='")
    $remoteLines.Add("squeue -j '$JobId' -o '%i|%j|%T|%M|%R' --noheader || true")
    $remoteLines.Add("echo")
    $remoteLines.Add("echo '== sacct job $JobId =='")
    $remoteLines.Add("sacct -j '$JobId' -P --format=JobID,JobName%40,State,ExitCode,Elapsed,Start,End || true")
    $remoteLines.Add("echo")
    $remoteLines.Add("echo '== scontrol job $JobId =='")
    $remoteLines.Add("scontrol show job '$JobId' 2>/dev/null | sed -n '1,90p' || true")
}

$remoteLines.Add("echo")
$remoteLines.Add("echo '== result files =='")
$remoteLines.Add("if [ -d ""`$RESULT_DIR"" ]; then find ""`$RESULT_DIR"" -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM %f\n' | sort; else echo ""missing `$RESULT_DIR""; fi")
$remoteLines.Add("echo")
$remoteLines.Add("echo '== recent matching logs =='")
$remoteLines.Add("find /home/syin94/scratch/lora_health/slurm_logs -maxdepth 1 -type f -name ""`$LOG_NAME"" -printf '%TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null | sort | tail -30 || true")
$remoteLines.Add("echo")
$remoteLines.Add("echo '== thesis guard =='")
$remoteLines.Add('case "$RESULT_DIR" in /home/syin94/scratch/MEng_Project*) echo "Refusing thesis result path" >&2; exit 3 ;; *) echo ok ;; esac')

$remoteScript = $remoteLines -join "`n"
$encodedScript = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))

& wsl -d Ubuntu-22.04 -- ssh narval "printf '%s' '$encodedScript' | base64 -d | bash"
if ($LASTEXITCODE -ne 0) {
    throw "Remote status check failed"
}
