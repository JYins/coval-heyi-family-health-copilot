# Training

Training must wait until the Phase 1-3 Go/No-Go gate passes.

Baseline evaluation can run before training. The first Narval GPU job should produce base-model predictions and metrics:

```bash
sbatch code/scripts/submit_narval_baseline.sh
```

Current LoRA training line:

- `sft_v2` completed on Narval and is the current trained adapter.
- `sft_v3` is prepared as a small extraction/onset patch. It keeps all data synthetic/public, mixes failure-driven v2/v3 examples into train, and holds out a few analog examples for validation.
- Submit v3 only when the user has approved a new Narval run:

```bash
LORA_HEALTH_APPROVED_SFT_V3=1 sbatch code/scripts/submit_narval_sft_v3.sh
```

After v3 training completes:

```bash
sbatch code/scripts/submit_narval_sft_v3_eval.sh
```

Rules:

- Train only on public or synthetic data.
- Record exact dataset manifest, config, Git commit, and output path.
- Use Narval root `/home/syin94/scratch/lora_health` only.
- Never reference `/home/syin94/scratch/MEng_Project` from training scripts.
