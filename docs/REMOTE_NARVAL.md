# Narval Remote Notes

> 2026-06-12 connection update: use WSL OpenSSH ControlMaster as the canonical Narval path. Read `docs/NARVAL_WSL_CONTROLMASTER.md` before any SSH, SCP, or Slurm action. Native Windows SSH may still log in once, but it must not be used for repeated Codex commands because Alliance MFA + ControlMaster is reliable through WSL, not native Windows.

Quick path:

```powershell
wsl -d Ubuntu-22.04 -- ssh -N narval
wsl -d Ubuntu-22.04 -- ssh -O check narval
wsl -d Ubuntu-22.04 -- ssh narval "cd /home/syin94/scratch/lora_health && hostname && pwd"
```

Keep the first command's PowerShell window open after completing MFA. Do not store MFA codes, passwords, private keys, tokens, or real family medical data in this repo.

This file records non-secret connection and safety information only.

Do not write passwords, MFA codes, one-time login codes, private keys, tokens, or secret URLs here or anywhere else in the repo.

## Cluster Identity

- Cluster: Narval / Digital Research Alliance of Canada.
- SSH alias: `narval` from the local OpenSSH config.
- Current SSH host behind the alias: `narval.alliancecan.ca`.
- User: `syin94`.
- Slurm account: `def-falmaham`.
- Typical GPU request: `--gres=gpu:a100:1`.
- Typical training job shape: 1 node, 1 A100, 8-16 CPU, 48-64G RAM.

## Project Isolation

This project must be isolated from the MEng thesis project.

- Lora project remote root: `/home/syin94/scratch/lora_health`.
- Thesis project remote root: `/home/syin94/scratch/MEng_Project`.
- Do not read, write, reuse, copy, move, or delete anything under the thesis root from this project.
- Use a separate venv, data folder, run folder, and Slurm log folder under `lora_health`.
- Slurm job names must start with `lora_health_`.

## Authentication

Preferred flow:

```powershell
ssh narval
```

Expected authentication may include password plus MFA. Ask the user for a fresh code only at login time. Do not store it.

Recommended improvement: keep SSH key authentication configured outside this repo.
The current local config is expected to use `IdentityFile ~/.ssh/id_ed25519_alliance`
for host alias `narval`. Do not copy the key into this repository.

Known plain-SSH flow:

```powershell
ssh narval
```

If OpenSSH asks for the local key passphrase:

```text
Enter passphrase for key 'C:\Users\shi/.ssh/id_ed25519':
```

Press Enter if the key has no passphrase. Then enter the Narval password and fresh Duo/MFA code when prompted. Do not write either value to a file, script, command line, or repo.

## Read-Only Connectivity Check

A safe check should not touch the thesis directory. Example after login:

```bash
hostname
whoami
pwd
squeue -u syin94
```

Before any Slurm submission for this project:

```bash
mkdir -p /home/syin94/scratch/lora_health/{code,data,runs,slurm_logs}
cd /home/syin94/scratch/lora_health
diskusage_report
```

## Prepared Remote Bootstrap

The repo includes scripts to set up the remote project spine without storing credentials:

- `scripts/narval_wsl_setup.ps1` is the canonical Windows workstation setup path. It reuses the active WSL OpenSSH ControlMaster session, uploads the safe repo subset, bootstraps the remote venv, submits data prep, and prints status.
- `scripts/narval_upload_repo.ps1` packs safe local project files and uploads them to `/home/syin94/scratch/lora_health/code`.
- `scripts/narval_bootstrap.sh` creates the isolated remote directory tree and Python venv.
- `scripts/narval_pull_data.sh` downloads public candidate datasets into `/home/syin94/scratch/lora_health/data/public`.
- `scripts/download_public_datasets.py` writes a remote download manifest.
- `scripts/submit_narval_data_prep.sh` is a CPU Slurm template for dataset prep after the remote venv is ready.

Suggested flow after the WSL master SSH session is open:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\narval_wsl_setup.ps1
```

Older native fallback from local PowerShell after logging in with fresh MFA when prompted:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\narval_one_shot_setup.ps1
```

The native fallback uses plain OpenSSH prompts by default to run the full setup without writing secrets. It intentionally targets `/home/syin94/scratch/lora_health`, not the thesis directory.

Paramiko fallback, only if native OpenSSH is unavailable:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\narval_auto_setup.ps1 -LivePrompts
```

The one-shot script uses SSH connection sharing when available, uploads the safe repo subset, bootstraps the remote venv, submits the CPU data-prep job, and prints remote status.

Do not use `/home/syin94/scratch/MEng_Project` for this repository. That path is the thesis project boundary from the project rules; it is useful as a login reference only, not as this LoRA project root.

Manual equivalent:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\narval_upload_repo.ps1
ssh narval "cd /home/syin94/scratch/lora_health/code && bash scripts/narval_bootstrap.sh"
ssh narval "cd /home/syin94/scratch/lora_health/code && MAX_ROWS=5000 bash scripts/narval_pull_data.sh"
```

Use `MAX_ROWS=0` only after quota is checked and the dataset licenses/schema are reviewed.

Current network note:

- Compute-node Slurm jobs cannot be assumed to reach Hugging Face directly. On 2026-06-19, `lora_health_data_prep` failed on a compute node with `Network is unreachable` while requesting Hugging Face metadata.
- For small public-data smoke downloads, run `narval_pull_data.sh` from the login node with a capped `MAX_ROWS` after the WSL ControlMaster session is open:

```powershell
powershell.exe -NoProfile -Command "wsl -d Ubuntu-22.04 -- ssh narval env MAX_ROWS=500 PROJECT_ROOT=/home/syin94/scratch/lora_health bash /home/syin94/scratch/lora_health/code/scripts/narval_pull_data.sh"
```

- Use Slurm for cached/offline processing and training, not for first-time internet downloads, unless Alliance network policy for the job environment has been verified.

If login-node downloads are too slow, submit the data-prep job after bootstrap:

```bash
cd /home/syin94/scratch/lora_health
sbatch code/scripts/submit_narval_data_prep.sh
```

Current public dataset candidates:

- `FreedomIntelligence/medical-o1-reasoning-SFT`, `zh` and `zh_mix`, Apache-2.0 on Hugging Face, candidate SFT source after filtering.
- `openlifescienceai/medmcqa`, validation/test, Apache-2.0 on Hugging Face, external sanity benchmark.
- `bigbio/pubmed_qa`, snapshot only, license and loader need review before use.

## Slurm Safety Checklist

Before submitting a job, verify:

- `--chdir=/home/syin94/scratch/lora_health` or equivalent is set.
- Output paths are under `/home/syin94/scratch/lora_health/runs` or `slurm_logs`.
- No input path points to `/home/syin94/scratch/MEng_Project`.
- No real family medical data is uploaded or referenced.
- The job name begins with `lora_health_`.
- The exact Slurm job ID is recorded in `docs/experiment_log.md` after submission.

## Current Connectivity Note

A non-interactive `BatchMode=yes` SSH check was attempted and did not enter the account because Narval requires MFA/keyboard-interactive authentication. No password or MFA code was used, no remote command was executed, and no thesis data was accessed.

