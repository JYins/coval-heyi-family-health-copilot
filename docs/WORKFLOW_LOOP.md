# Workflow Loop

This project should move fast, but not by skipping privacy, eval, or remote isolation.

## Daily Agent Loop

1. Read the six required context files from `AGENTS.md`.
2. Run local workflow checks:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\run_workflow_checks.ps1
   ```

3. Inspect the latest heartbeat report under `results/heartbeat/`.
4. Continue the next safe project step:
   - expand gold data and metrics;
   - run baseline once model access is ready;
   - build the fake-data product spine;
   - only then prepare Narval fine-tuning.
5. Review `results/go_no_go/latest_go_no_go.md` before proposing any remote training.
6. Append real run results to `docs/experiment_log.md`; never invent missing metrics.

For a queued or running Narval eval, reuse the existing WSL master and run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\narval_job_status.ps1 -JobId 64203036
```

This prints only non-secret Slurm status, result files, and matching `lora_health_` logs under `/home/syin94/scratch/lora_health`.

## Remote Setup Loop

Use this when the WSL OpenSSH ControlMaster session is already open:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\narval_wsl_setup.ps1
```

This is the canonical path on this Windows workstation. It reuses the existing
MFA-authenticated WSL `narval` master connection, uploads the safe repo subset,
bootstraps the remote venv, submits `lora_health_data_prep`, and prints status.

Use this older native path only if WSL is unavailable:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\narval_one_shot_setup.ps1
```

This uses native OpenSSH prompts and ControlMaster reuse: authenticate once when possible, then upload, bootstrap, submit data prep, and print status.

By default the script uses plain `ssh`/`scp` with no auth options. If OpenSSH asks for the local key passphrase and the key has no passphrase, press Enter. Then enter Narval password and fresh MFA code in the SSH prompt only.

Paramiko fallback, only if native OpenSSH is unavailable:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\narval_auto_setup.ps1 -LivePrompts
```

Default behavior:

- uploads a safe subset of this repo to `/home/syin94/scratch/lora_health/code`;
- bootstraps `/home/syin94/scratch/lora_health`;
- creates or updates the remote venv;
- submits or prepares data prep depending on network availability;
- prints remote status.

Use login-node download only for a small smoke:

```powershell
powershell.exe -NoProfile -Command "wsl -d Ubuntu-22.04 -- ssh narval env MAX_ROWS=500 PROJECT_ROOT=/home/syin94/scratch/lora_health bash /home/syin94/scratch/lora_health/code/scripts/narval_pull_data.sh"
```

On 2026-06-19, compute-node data-prep could not reach Hugging Face, so first-time
public-data downloads should stay capped and run from the login node. Use Slurm
after data exists in `/home/syin94/scratch/lora_health/data/public` or HF cache.

## Hooks

The versioned pre-commit hook lives at `scripts/hooks/pre-commit`.

Install it locally with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_git_hooks.ps1
```

The hook checks for leaked secrets, verifies Slurm safety settings, and runs the eval fixture smoke test.
