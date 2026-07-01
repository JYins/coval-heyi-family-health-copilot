# Narval Access via WSL ControlMaster

Last verified: 2026-06-12, after Narval/Duo account unlock.

This is the canonical connection method for this LoRA project on the Windows Codex workstation.

## Golden Rule

Use WSL OpenSSH ControlMaster for Narval.

Do not use native Windows OpenSSH ControlMaster for repeated Codex SSH commands. Alliance MFA documentation notes that ControlMaster does not work correctly with native Windows SSH. WSL is the reliable path.

Do not write passwords, MFA passcodes, private keys, Duo backup codes, or tokens into this repo, logs, scripts, Slurm files, or chat summaries.

## One-Time WSL SSH Config

The expected WSL distribution is:

```bash
Ubuntu-22.04
```

The WSL SSH config should contain a `narval` host similar to this:

```sshconfig
Host narval
    HostName narval.alliancecan.ca
    User syin94
    IdentityFile ~/.ssh/id_ed25519_alliance
    IdentitiesOnly yes
    ControlMaster auto
    ControlPath ~/.ssh/cm-%r@%h:%p
    ControlPersist 10m
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

The private key must live only in WSL `~/.ssh/` with restricted permissions. Do not copy private keys into this repository.

## Standard Connection Flow

1. Start a master SSH connection in a visible PowerShell window:

```powershell
wsl -d Ubuntu-22.04 -- ssh -N narval
```

2. Complete the normal SSH prompts:

- SSH key passphrase if requested.
- Alliance/Duo MFA prompt. Use Duo Push or a current one-time code.

3. Keep that PowerShell window open. It is the master connection.

4. In Codex or another terminal, verify that the master is active:

```powershell
wsl -d Ubuntu-22.04 -- ssh -O check narval
```

Expected good output:

```text
Master running (pid=...)
```

5. Reuse the existing MFA-authenticated connection for commands:

```powershell
wsl -d Ubuntu-22.04 -- ssh narval "hostname && pwd"
```

This should not ask for MFA again while the master connection is alive.

## LoRA Project Remote Root

This project uses:

```text
/home/syin94/scratch/lora_health
```

Keep it isolated from the thesis/MEng project root:

```text
/home/syin94/scratch/MEng_Project
```

Do not read, modify, copy into, or submit jobs from the thesis root when working on this LoRA project unless the user explicitly asks for that separate project.

## Common Commands

Check remote root:

```powershell
wsl -d Ubuntu-22.04 -- ssh narval "cd /home/syin94/scratch/lora_health && pwd && ls"
```

Check Slurm queue for this project:

```powershell
wsl -d Ubuntu-22.04 -- ssh narval "squeue -u syin94 -o '%.18i %.30j %.10T %.12M %.12L %.20R' | grep -E 'JOBID|lora_health'"
```

Submit a job from the LoRA root:

```powershell
wsl -d Ubuntu-22.04 -- ssh narval "cd /home/syin94/scratch/lora_health && sbatch scripts/<job>.sh"
```

Upload a local file to the LoRA remote root:

```powershell
wsl -d Ubuntu-22.04 -- scp /mnt/d/lora/scripts/<file>.sh narval:/home/syin94/scratch/lora_health/scripts/<file>.sh
```

Download a result:

```powershell
wsl -d Ubuntu-22.04 -- scp narval:/home/syin94/scratch/lora_health/results/<file> /mnt/d/lora/results/<file>
```

## What Went Wrong Before

Repeated native Windows SSH attempts can fail or burn MFA attempts because each command may start a fresh login instead of reusing a multiplexed session. Symptoms included:

```text
Your account is disabled and cannot access this application.
Permission denied (keyboard-interactive,hostbased).
```

That was an account/application lockout state, not evidence that the project keys were wrong. After support unlocked the account, the WSL ControlMaster method worked.

## If It Fails Again

If Duo/Narval says the account is disabled, stop retrying. Do not keep sending SSH attempts. Ask the user to contact Alliance support and mention the exact message.

If `ssh -O check narval` says no master is running, reopen the visible master connection:

```powershell
wsl -d Ubuntu-22.04 -- ssh -N narval
```

If commands still ask for MFA every time, check that the command is using WSL and the `narval` alias, not native Windows SSH.

## Logging Discipline

For this LoRA project:

- Slurm job names should start with `lora_health_`.
- Record submitted job IDs in `docs/experiment_log.md`.
- Record exact metrics and paths when jobs finish.
- Never record secrets, MFA codes, passwords, private keys, real family medical data, or private patient data.
