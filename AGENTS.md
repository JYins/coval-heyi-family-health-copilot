# Agent Rules for Family Health Memory Copilot

This repository is the working repo for a private-first Chinese family health memory copilot and a rigorously evaluated LoRA/QLoRA medical-structuring project.

## First Files To Read

Read these before making claims, changing architecture, or submitting any remote job:

1. `docs/PROJECT_BRIEF.md` - full original handoff and product/research intent.
2. `docs/PLAN.md` - current execution chain, milestones, and Go/No-Go gates.
3. `docs/REMOTE_NARVAL.md` - Narval connection info, isolation rules, and safe Slurm conventions.
   Also read `docs/NARVAL_WSL_CONTROLMASTER.md` before any Narval SSH/SCP/Slurm action.
4. `docs/experiment_log.md` - completed runs and metrics; if a number is not here or in a cited result file, treat it as unknown.
5. `docs/error_analysis.md` - known failures, bad examples, and next fixes.
6. `docs/GRAPHIFY.md` - context-saving graphify workflow for this repo.

For coding style inspiration, read `D:\MyProjects\wiki\wiki\CLAUDE.md` and, when needed, `D:\MyProjects\wiki\wiki\me\coding-style.md` / `me\principles.md` if those files are available. For the future RAG/eval layer, consult `D:\简历故事和细节\THIS_WEEK\02-EVENUP-之后`, especially the RAG architecture and defense notes.

## Product And Research Posture

- This is one project with two faces: a real private product for family health organization and a publishable/portfolio-grade model evaluation project.
- The first research contribution is not a chatbot. It is an evaluation-first Chinese medical record structuring and safety system.
- Build the eval harness before training. Do not fine-tune until baseline evaluation and the local product spine can run on synthetic/public examples.
- Be conservative with all medical claims. The assistant organizes information, prepares doctor-facing summaries, and escalates crisis symptoms. It does not diagnose, prescribe, adjust medication, or reassure the user that care is unnecessary.

## Hard Privacy Boundary

- Public repo/Hugging Face artifacts may use only public or synthetic data.
- Real family medical data must never enter training data, Git, Hugging Face, logs, cloud services, or Narval jobs unless the user explicitly redesigns the privacy policy later.
- `data/private/`, `*.real.*`, `*.pii.*`, local databases, scans, reports, and raw family notes are never committed.
- If a task would touch real family data, stop and ask the user first.

## Secrets And Credentials

- Never write passwords, MFA codes, one-time codes, private keys, tokens, or secret URLs into files, commits, logs, or docs.
- The Narval password and any MFA code mentioned in chat are not to be reused or recorded. If a password was exposed in chat, recommend rotation.
- Store only non-secret connection metadata in docs: host, username, Slurm account, and project paths.
- Use SSH keys for Narval where possible. Runtime secrets belong in `.env`, which is ignored; keep only `.env.example` in the repo.

## Narval / Thesis Isolation

- The thesis project on Narval lives under `/home/syin94/scratch/MEng_Project`. Treat it as read-protected for this repo: do not read, write, reuse, move, or delete thesis data/code from this project.
- This project must use `/home/syin94/scratch/lora_health` on Narval with its own venv, data, runs, and Slurm logs.
- Slurm job names must start with `lora_health_`.
- Before any remote job, verify the script path, checkpoint path, output directory, `--chdir`, and scratch quota.
- Do not leave SSH sessions running at the end of a turn.

## Execution Chain

Follow this order unless the user explicitly changes the plan:

1. Build the first synthetic/public gold eval set.
2. Run the base instruct model through extraction, summary, safety, crisis, and hallucination checks.
3. Build a local end-to-end product spine with fake reports: OCR/ASR stub -> structure -> timeline DB -> doctor summary -> safety escalation.
4. Only after steps 1-3 pass the Go/No-Go gate, use Narval A100 for a product-first 7B LoRA/QLoRA SFT run that targets the biggest measured blocker and can plug back into the local product spine.
5. Add interpretable complexity only when failures justify it: structured JSON constrained decoding, failure-driven data augmentation, a small rank/data-size ablation, optional 14B QLoRA, or safety refusal DPO/ORPO after preference data exists.
6. Rerun evals, record before/after deltas, test the adapter inside the fake-data product pipeline, then run focused ablations only if they answer a real product or metric question.
7. Add RAG last, using the existing rageval-style structure: retrieval metrics first, generation second.

## Code Style

- Fail loud. Avoid silent `except: pass`; raise or log clear actionable errors.
- Skeleton first: make the pipeline run end-to-end on fake/synthetic data before filling heavy implementations.
- Keep code student-readable: simple names, short functions, minimal abstraction, explicit data contracts.
- Prefer structured parsers, schemas, and tests over ad hoc string manipulation.
- Record every experiment like a lab notebook entry in `docs/experiment_log.md`.
- Never invent metrics. If an experiment has not run, write `not run` or `missing`, not a guessed number.

## Git Discipline

- Keep secrets and private data out of Git.
- Commit source, configs, docs, synthetic/public gold samples, and small reproducibility manifests.
- Do not commit large checkpoints, generated model outputs, private data, or `graphify-out/`.
- Use clear commits that explain the intent, not only the file operation.

## Narval Connection Canon

For this Windows Codex workstation, the canonical Narval workflow is WSL OpenSSH ControlMaster:

```powershell
wsl -d Ubuntu-22.04 -- ssh -N narval
wsl -d Ubuntu-22.04 -- ssh -O check narval
wsl -d Ubuntu-22.04 -- ssh narval "cd /home/syin94/scratch/lora_health && hostname && pwd"
```

Complete MFA in the visible master SSH window and keep that window open while Codex runs remote commands. Do not use native Windows OpenSSH ControlMaster for repeated commands. Do not write credentials, MFA codes, private keys, tokens, real family medical data, or private patient data into files.

LoRA remote root: `/home/syin94/scratch/lora_health`.
Thesis/MEng remote root: `/home/syin94/scratch/MEng_Project`.
Keep these two projects isolated unless the user explicitly asks to work on the other project.

