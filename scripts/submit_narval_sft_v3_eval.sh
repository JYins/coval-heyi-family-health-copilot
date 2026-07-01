#!/usr/bin/env bash
#SBATCH --job-name=lora_health_sft_v3_eval
#SBATCH --account=def-falmaham
#SBATCH --nodes=1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=/home/syin94/scratch/lora_health/slurm_logs/%x_%j.out
#SBATCH --error=/home/syin94/scratch/lora_health/slurm_logs/%x_%j.err
#SBATCH --chdir=/home/syin94/scratch/lora_health

set -euo pipefail

export LORA_HEALTH_EVAL_ADAPTER_DIR="/home/syin94/scratch/lora_health/runs/qwen7b_lora_sft_v3"
export LORA_HEALTH_EVAL_OUT_ROOT="/home/syin94/scratch/lora_health/results/sft_v3_eval"

bash /home/syin94/scratch/lora_health/code/scripts/submit_narval_sft_v2_eval.sh
