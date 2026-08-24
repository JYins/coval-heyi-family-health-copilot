$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root
$pycachePath = Join-Path $env:TEMP "coval-health-workflow-pycache"

function Run-Command {
    param(
        [string]$Name,
        [scriptblock]$Body
    )
    Write-Host "== $Name =="
    & $Body
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Name"
    }
}

Run-Command "workflow policy check" {
    python scripts\check_workflow.py
}

Run-Command "local provider audit compile" {
    python -X "pycache_prefix=$pycachePath" -m py_compile scripts\benchmark_local_provider.py scripts\compare_local_inference.py scripts\compare_phase2b_safety_intent.py scripts\verify_adapter_effect.py eval\run_safety_intent_eval.py src\inference\providers.py
}

Run-Command "python compile" {
    python -X "pycache_prefix=$pycachePath" -m py_compile scripts\benchmark_local_provider.py scripts\compare_medication_contrast.py scripts\compare_sft_smoke_eval.py scripts\compare_sft_v1_eval.py scripts\compare_sft_v1_constrained.py scripts\compare_sft_v2_eval.py scripts\compare_sft_v2_template_patch.py scripts\compare_sft_v3_eval.py scripts\download_public_datasets.py scripts\prefetch_hf_assets.py scripts\heartbeat_report.py scripts\check_workflow.py scripts\go_no_go_report.py scripts\narval_paramiko_setup.py scripts\project_gap_report.py scripts\recover_predictions_from_raw_outputs.py scripts\run_rag_retrieval_eval.py scripts\summarize_baseline.py scripts\summarize_v1_1_gaps.py scripts\summarize_sft_v2_template_patch_gaps.py scripts\validate_predictions.py scripts\validate_sft_smoke_dataset.py scripts\normalize_predictions.py scripts\normalize_report_types.py scripts\template_doctor_summary.py eval\metrics_crisis.py eval\metrics_extract.py eval\metrics_risk.py eval\metrics_safety.py eval\metrics_summary.py eval\run_eval.py src\prediction_normalization.py src\product_spine.py src\health_memory\database.py src\health_memory\store.py src\inference\providers.py src\serve\api_schemas.py src\serve\demo_structuring.py src\serve\evidence.py src\serve\memory_api.py src\serve\coval_health_api.py train\build_sft_smoke_dataset.py train\build_sft_v1_dataset.py train\build_sft_v2_dataset.py train\build_sft_v3_dataset.py train\run_baseline.py train\train_sft.py
}

Run-Command "durable health memory tests" {
    .\.venv\Scripts\python.exe -m unittest discover -s tests -v
}

$gitBash = "C:\Program Files\Git\bin\bash.exe"
if (Test-Path -LiteralPath $gitBash) {
    Run-Command "bash syntax" {
        & $gitBash -n scripts/narval_bootstrap.sh
        & $gitBash -n scripts/narval_pull_data.sh
        & $gitBash -n scripts/narval_check_hf_cache.sh
        & $gitBash -n scripts/narval_prefetch_model.sh
        & $gitBash -n scripts/narval_status.sh
        & $gitBash -n scripts/submit_narval.sh
        & $gitBash -n scripts/submit_narval_data_prep.sh
        & $gitBash -n scripts/submit_narval_baseline.sh
        & $gitBash -n scripts/submit_narval_baseline_schema_v2.sh
        & $gitBash -n scripts/submit_narval_baseline_schema_v3.sh
        & $gitBash -n scripts/submit_narval_medication_contrast_schema_v3.sh
        & $gitBash -n scripts/submit_narval_medication_contrast_schema_v4.sh
        & $gitBash -n scripts/submit_narval_sft_smoke.sh
        & $gitBash -n scripts/submit_narval_sft_smoke_eval.sh
        & $gitBash -n scripts/submit_narval_sft_v1.sh
        & $gitBash -n scripts/submit_narval_sft_v1_eval.sh
        & $gitBash -n scripts/submit_narval_sft_v1_eval_v1_1.sh
        & $gitBash -n scripts/submit_narval_sft_v2.sh
        & $gitBash -n scripts/submit_narval_sft_v2_eval.sh
        & $gitBash -n scripts/submit_narval_sft_v3.sh
        & $gitBash -n scripts/submit_narval_sft_v3_eval.sh
        & $gitBash -n scripts/prepare_hf_adapter_upload.sh
    }
} else {
    Write-Host "Git Bash missing; skipping bash -n checks."
}

Run-Command "PowerShell parse narval_upload_repo" {
    powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw -LiteralPath 'scripts\narval_upload_repo.ps1')) | Out-Null"
}

Run-Command "PowerShell parse narval_one_shot_setup" {
    powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw -LiteralPath 'scripts\narval_one_shot_setup.ps1')) | Out-Null"
}

Run-Command "PowerShell parse narval_auto_setup" {
    powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw -LiteralPath 'scripts\narval_auto_setup.ps1')) | Out-Null"
}

Run-Command "PowerShell parse narval_interactive_login" {
    powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw -LiteralPath 'scripts\narval_interactive_login.ps1')) | Out-Null"
}

Run-Command "PowerShell parse prepare_narval_paste_upload" {
    powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw -LiteralPath 'scripts\prepare_narval_paste_upload.ps1')) | Out-Null"
}

Run-Command "PowerShell parse narval_wsl_setup" {
    powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw -LiteralPath 'scripts\narval_wsl_setup.ps1')) | Out-Null"
}

Run-Command "PowerShell parse narval_job_status" {
    powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw -LiteralPath 'scripts\narval_job_status.ps1')) | Out-Null"
}

Run-Command "PowerShell parse hf_local_login" {
    powershell -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw -LiteralPath 'scripts\hf_local_login.ps1')) | Out-Null"
}

Run-Command "eval fixture smoke" {
    python eval\run_eval.py --gold eval\gold\synthetic_v0.jsonl --pred eval\gold\fixture_predictions_v0.jsonl --out results\eval_fixture_metrics.json
}

Run-Command "medication contrast fixture smoke" {
    python eval\run_eval.py --gold eval\gold\medication_contrast_v0.jsonl --pred eval\gold\fixture_predictions_medication_contrast_v0.jsonl --out results\eval_medication_contrast_metrics.json --details-out results\eval_medication_contrast_details.json
}

Run-Command "schema edge constrained fixture smoke" {
    python scripts\normalize_predictions.py --pred eval\gold\fixture_predictions_schema_edge_cases_raw_v0.jsonl --out results\schema_edge_cases_v0\predictions_normalized.jsonl --report results\schema_edge_cases_v0\normalization_report.json
    python scripts\normalize_report_types.py --pred results\schema_edge_cases_v0\predictions_normalized.jsonl --out results\schema_edge_cases_v0\predictions_report_type_normalized.jsonl --report results\schema_edge_cases_v0\report_type_normalization_report.json
    python eval\run_eval.py --gold eval\gold\schema_edge_cases_v0.jsonl --pred results\schema_edge_cases_v0\predictions_report_type_normalized.jsonl --out results\schema_edge_cases_v0\metrics.json --details-out results\schema_edge_cases_v0\example_details.json
}

Run-Command "safety onset edge v1.1 fixture smoke" {
    python scripts\normalize_predictions.py --pred eval\gold\fixture_predictions_safety_onset_edge_v1_1_raw.jsonl --out results\safety_onset_edge_v1_1\predictions_normalized.jsonl --report results\safety_onset_edge_v1_1\normalization_report.json
    python scripts\normalize_report_types.py --pred results\safety_onset_edge_v1_1\predictions_normalized.jsonl --out results\safety_onset_edge_v1_1\predictions_report_type_normalized.jsonl --report results\safety_onset_edge_v1_1\report_type_normalization_report.json
    python eval\run_eval.py --gold eval\gold\safety_onset_edge_v1_1.jsonl --pred results\safety_onset_edge_v1_1\predictions_report_type_normalized.jsonl --out results\safety_onset_edge_v1_1\metrics.json --details-out results\safety_onset_edge_v1_1\example_details.json
}

Run-Command "product spine smoke" {
    python src\product_spine.py --gold eval\gold\synthetic_v0.jsonl --pred eval\gold\fixture_predictions_v0.jsonl --database results\product_spine\synthetic_v0.sqlite --out results\product_spine\synthetic_v0_report.json --markdown-out results\product_spine\synthetic_v0_doctor_summary.md
}

Run-Command "schema edge product spine smoke" {
    python src\product_spine.py --gold eval\gold\schema_edge_cases_v0.jsonl --pred eval\gold\fixture_predictions_schema_edge_cases_raw_v0.jsonl --database results\product_spine\schema_edge_cases_v0.sqlite --out results\schema_edge_cases_v0\product_spine_report.json --markdown-out results\schema_edge_cases_v0\product_spine_doctor_summary.md --limit 5
}

Run-Command "safety onset edge v1.1 product spine smoke" {
    python src\product_spine.py --gold eval\gold\safety_onset_edge_v1_1.jsonl --pred eval\gold\fixture_predictions_safety_onset_edge_v1_1_raw.jsonl --database results\product_spine\safety_onset_edge_v1_1.sqlite --out results\safety_onset_edge_v1_1\product_spine_report.json --markdown-out results\safety_onset_edge_v1_1\product_spine_doctor_summary.md --limit 6
}

Run-Command "rag v0 retrieval smoke" {
    python scripts\run_rag_retrieval_eval.py --corpus data\public\rag_v0\corpus.jsonl --gold eval\rag\gold_v0.jsonl --out results\rag_v0\metrics.json --details-out results\rag_v0\details.json
}

if (Test-Path -LiteralPath "results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_raw.jsonl") {
    Run-Command "sft v1 safety onset edge v1.1 completion" {
        python eval\run_eval.py --gold eval\gold\safety_onset_edge_v1_1.jsonl --pred results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_raw.jsonl --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\metrics_raw.json --details-out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\example_details_raw.json
        python scripts\normalize_predictions.py --pred results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_raw.jsonl --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_normalized.jsonl --report results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\normalization_report.json
        python scripts\normalize_report_types.py --pred results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_normalized.jsonl --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_report_type_normalized.jsonl --report results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\report_type_normalization_report.json
        python scripts\template_doctor_summary.py --gold eval\gold\safety_onset_edge_v1_1.jsonl --pred results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_report_type_normalized.jsonl --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_report_type_template_summary.jsonl
        python eval\run_eval.py --gold eval\gold\safety_onset_edge_v1_1.jsonl --pred results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_report_type_template_summary.jsonl --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\metrics_report_type_template_summary.json --details-out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\example_details_report_type_template_summary.json
        python scripts\validate_predictions.py --predictions results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_report_type_template_summary.jsonl --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\contract_validation_report_type_template_summary.json
        python src\product_spine.py --gold eval\gold\safety_onset_edge_v1_1.jsonl --pred results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_report_type_template_summary.jsonl --database results\product_spine\sft_v1_safety_onset_edge_v1_1.sqlite --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\product_spine_report.json --markdown-out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\product_spine_doctor_summary.md --limit 6

        python scripts\recover_predictions_from_raw_outputs.py --raw-outputs results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\raw_outputs.jsonl --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_recovered.jsonl --report results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\recovery_report.json
        python scripts\normalize_predictions.py --pred results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_recovered.jsonl --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_recovered_normalized.jsonl --report results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\recovered_normalization_report.json
        python scripts\normalize_report_types.py --pred results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_recovered_normalized.jsonl --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_recovered_report_type_normalized.jsonl --report results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\recovered_report_type_normalization_report.json
        python scripts\template_doctor_summary.py --gold eval\gold\safety_onset_edge_v1_1.jsonl --pred results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_recovered_report_type_normalized.jsonl --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_recovered_report_type_template_summary.jsonl
        python eval\run_eval.py --gold eval\gold\safety_onset_edge_v1_1.jsonl --pred results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_recovered_report_type_template_summary.jsonl --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\metrics_recovered_report_type_template_summary.json --details-out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\example_details_recovered_report_type_template_summary.json
        python scripts\validate_predictions.py --predictions results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_recovered_report_type_template_summary.jsonl --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\contract_validation_recovered_report_type_template_summary.json
        python src\product_spine.py --gold eval\gold\safety_onset_edge_v1_1.jsonl --pred results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\predictions_recovered_report_type_template_summary.jsonl --database results\product_spine\sft_v1_safety_onset_edge_v1_1_recovered.sqlite --out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\product_spine_recovered_report.json --markdown-out results\sft_v1_eval_v1_1\safety_onset_edge_v1_1\product_spine_recovered_doctor_summary.md --limit 6
    }
}

Run-Command "sft smoke dataset build" {
    python train\build_sft_smoke_dataset.py --out-dir data\public\sft_smoke_v0
    python scripts\validate_sft_smoke_dataset.py --train-jsonl data\public\sft_smoke_v0\train.jsonl --val-jsonl data\public\sft_smoke_v0\val.jsonl --manifest data\public\sft_smoke_v0\manifest.json --report results\sft_smoke_validation.json
}

Run-Command "sft v1 dataset build" {
    python train\build_sft_v1_dataset.py --out-dir data\public\sft_v1
    python scripts\validate_sft_smoke_dataset.py --train-jsonl data\public\sft_v1\train.jsonl --val-jsonl data\public\sft_v1\val.jsonl --manifest data\public\sft_v1\manifest.json --report results\sft_v1_validation.json
}

Run-Command "sft v2 dataset build" {
    python train\build_sft_v2_dataset.py --out-dir data\public\sft_v2
    python scripts\validate_sft_smoke_dataset.py --train-jsonl data\public\sft_v2\train.jsonl --val-jsonl data\public\sft_v2\val.jsonl --manifest data\public\sft_v2\manifest.json --gold eval\gold\synthetic_v0.jsonl eval\gold\medication_contrast_v0.jsonl eval\gold\safety_onset_edge_v1_1.jsonl --report results\sft_v2_validation.json
}

Run-Command "sft v3 dataset build" {
    python train\build_sft_v3_dataset.py --out-dir data\public\sft_v3
    python scripts\validate_sft_smoke_dataset.py --train-jsonl data\public\sft_v3\train.jsonl --val-jsonl data\public\sft_v3\val.jsonl --manifest data\public\sft_v3\manifest.json --gold eval\gold\synthetic_v0.jsonl eval\gold\medication_contrast_v0.jsonl eval\gold\safety_onset_edge_v1_1.jsonl --report results\sft_v3_validation.json
}

if (Test-Path -LiteralPath "results\medication_contrast_schema_v3\predictions_normalized.jsonl") {
    Run-Command "medication contrast template summary smoke" {
        python scripts\template_doctor_summary.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v3\predictions_normalized.jsonl --out results\medication_contrast_schema_v3\predictions_template_summary.jsonl
        python eval\run_eval.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v3\predictions_template_summary.jsonl --out results\medication_contrast_schema_v3\metrics_template_summary.json --details-out results\medication_contrast_schema_v3\example_details_template_summary.json
        python scripts\normalize_report_types.py --pred results\medication_contrast_schema_v3\predictions_normalized.jsonl --out results\medication_contrast_schema_v3\predictions_report_type_normalized.jsonl --report results\medication_contrast_schema_v3\report_type_normalization_report.json
        python scripts\template_doctor_summary.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v3\predictions_report_type_normalized.jsonl --out results\medication_contrast_schema_v3\predictions_report_type_template_summary.jsonl
        python eval\run_eval.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v3\predictions_report_type_template_summary.jsonl --out results\medication_contrast_schema_v3\metrics_report_type_template_summary.json --details-out results\medication_contrast_schema_v3\example_details_report_type_template_summary.json
        python src\product_spine.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v3\predictions_report_type_template_summary.jsonl --database results\product_spine\medication_contrast_schema_v3_report_type_template_63925409.sqlite --out results\product_spine\medication_contrast_schema_v3_report_type_template_63925409_report.json --markdown-out results\product_spine\medication_contrast_schema_v3_report_type_template_63925409_doctor_summary.md --limit 4
    }
}

if (Test-Path -LiteralPath "results\medication_contrast_schema_v4\predictions_normalized.jsonl") {
    Run-Command "medication contrast schema_v4 template summary smoke" {
        python scripts\template_doctor_summary.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v4\predictions_normalized.jsonl --out results\medication_contrast_schema_v4\predictions_template_summary.jsonl
        python eval\run_eval.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v4\predictions_template_summary.jsonl --out results\medication_contrast_schema_v4\metrics_template_summary.json --details-out results\medication_contrast_schema_v4\example_details_template_summary.json
        python scripts\normalize_report_types.py --pred results\medication_contrast_schema_v4\predictions_normalized.jsonl --out results\medication_contrast_schema_v4\predictions_report_type_normalized.jsonl --report results\medication_contrast_schema_v4\report_type_normalization_report.json
        python scripts\template_doctor_summary.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v4\predictions_report_type_normalized.jsonl --out results\medication_contrast_schema_v4\predictions_report_type_template_summary.jsonl
        python eval\run_eval.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v4\predictions_report_type_template_summary.jsonl --out results\medication_contrast_schema_v4\metrics_report_type_template_summary.json --details-out results\medication_contrast_schema_v4\example_details_report_type_template_summary.json
        python src\product_spine.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v4\predictions_normalized.jsonl --database results\product_spine\medication_contrast_schema_v4_63970602.sqlite --out results\product_spine\medication_contrast_schema_v4_63970602_report.json --markdown-out results\product_spine\medication_contrast_schema_v4_63970602_doctor_summary.md --limit 4
        python scripts\compare_medication_contrast.py
    }
}

if (Test-Path -LiteralPath "results\baseline_schema_v3\predictions_normalized.jsonl") {
    Run-Command "synthetic_v0 schema_v3 postprocess comparison" {
        python scripts\normalize_report_types.py --pred results\baseline_schema_v3\predictions_normalized.jsonl --out results\baseline_schema_v3\predictions_report_type_normalized.jsonl --report results\baseline_schema_v3\report_type_normalization_report.json
        python eval\run_eval.py --gold eval\gold\synthetic_v0.jsonl --pred results\baseline_schema_v3\predictions_report_type_normalized.jsonl --out results\baseline_schema_v3\metrics_report_type_normalized.json --details-out results\baseline_schema_v3\example_details_report_type_normalized.json
        python scripts\template_doctor_summary.py --gold eval\gold\synthetic_v0.jsonl --pred results\baseline_schema_v3\predictions_report_type_normalized.jsonl --out results\baseline_schema_v3\predictions_report_type_template_summary.jsonl
        python eval\run_eval.py --gold eval\gold\synthetic_v0.jsonl --pred results\baseline_schema_v3\predictions_report_type_template_summary.jsonl --out results\baseline_schema_v3\metrics_report_type_template_summary.json --details-out results\baseline_schema_v3\example_details_report_type_template_summary.json
        python src\product_spine.py --gold eval\gold\synthetic_v0.jsonl --pred results\baseline_schema_v3\predictions_report_type_template_summary.jsonl --database results\product_spine\baseline_schema_v3_report_type_template_63839439.sqlite --out results\product_spine\baseline_schema_v3_report_type_template_63839439_report.json --markdown-out results\product_spine\baseline_schema_v3_report_type_template_63839439_doctor_summary.md --limit 10
    }
}

if ((Test-Path -LiteralPath "results\sft_smoke_eval_64164883\synthetic_v0\metrics_report_type_template_summary.json") -and (Test-Path -LiteralPath "results\sft_smoke_eval_64164883\medication_contrast_v0\metrics_report_type_template_summary.json")) {
    Run-Command "sft smoke eval comparison" {
        python scripts\compare_sft_smoke_eval.py
    }
}

if ((Test-Path -LiteralPath "results\sft_v1_eval\synthetic_v0\metrics_report_type_template_summary.json") -and (Test-Path -LiteralPath "results\sft_v1_eval\medication_contrast_v0\metrics_report_type_template_summary.json") -and (Test-Path -LiteralPath "results\sft_v1\trainer_state.json")) {
    Run-Command "sft v1 eval comparison" {
        python scripts\compare_sft_v1_eval.py
    }
}

if ((Test-Path -LiteralPath "results\sft_v1_eval\synthetic_v0\predictions_raw.jsonl") -and (Test-Path -LiteralPath "results\sft_v1_eval\medication_contrast_v0\predictions_raw.jsonl")) {
    Run-Command "sft v1 constrained postprocess comparison" {
        python scripts\normalize_predictions.py --pred results\sft_v1_eval\synthetic_v0\predictions_raw.jsonl --out results\sft_v1_eval_constrained\synthetic_v0\predictions_normalized.jsonl --report results\sft_v1_eval_constrained\synthetic_v0\normalization_report.json
        python scripts\normalize_report_types.py --pred results\sft_v1_eval_constrained\synthetic_v0\predictions_normalized.jsonl --out results\sft_v1_eval_constrained\synthetic_v0\predictions_report_type_normalized.jsonl --report results\sft_v1_eval_constrained\synthetic_v0\report_type_normalization_report.json
        python scripts\template_doctor_summary.py --gold eval\gold\synthetic_v0.jsonl --pred results\sft_v1_eval_constrained\synthetic_v0\predictions_report_type_normalized.jsonl --out results\sft_v1_eval_constrained\synthetic_v0\predictions_report_type_template_summary.jsonl
        python eval\run_eval.py --gold eval\gold\synthetic_v0.jsonl --pred results\sft_v1_eval_constrained\synthetic_v0\predictions_report_type_template_summary.jsonl --out results\sft_v1_eval_constrained\synthetic_v0\metrics_report_type_template_summary.json --details-out results\sft_v1_eval_constrained\synthetic_v0\example_details_report_type_template_summary.json
        python src\product_spine.py --gold eval\gold\synthetic_v0.jsonl --pred results\sft_v1_eval_constrained\synthetic_v0\predictions_report_type_template_summary.jsonl --database results\product_spine\sft_v1_constrained_synthetic_v0.sqlite --out results\sft_v1_eval_constrained\synthetic_v0\product_spine_report.json --markdown-out results\sft_v1_eval_constrained\synthetic_v0\product_spine_doctor_summary.md --limit 10

        python scripts\normalize_predictions.py --pred results\sft_v1_eval\medication_contrast_v0\predictions_raw.jsonl --out results\sft_v1_eval_constrained\medication_contrast_v0\predictions_normalized.jsonl --report results\sft_v1_eval_constrained\medication_contrast_v0\normalization_report.json
        python scripts\normalize_report_types.py --pred results\sft_v1_eval_constrained\medication_contrast_v0\predictions_normalized.jsonl --out results\sft_v1_eval_constrained\medication_contrast_v0\predictions_report_type_normalized.jsonl --report results\sft_v1_eval_constrained\medication_contrast_v0\report_type_normalization_report.json
        python scripts\template_doctor_summary.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\sft_v1_eval_constrained\medication_contrast_v0\predictions_report_type_normalized.jsonl --out results\sft_v1_eval_constrained\medication_contrast_v0\predictions_report_type_template_summary.jsonl
        python eval\run_eval.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\sft_v1_eval_constrained\medication_contrast_v0\predictions_report_type_template_summary.jsonl --out results\sft_v1_eval_constrained\medication_contrast_v0\metrics_report_type_template_summary.json --details-out results\sft_v1_eval_constrained\medication_contrast_v0\example_details_report_type_template_summary.json
        python src\product_spine.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\sft_v1_eval_constrained\medication_contrast_v0\predictions_report_type_template_summary.jsonl --database results\product_spine\sft_v1_constrained_medication_contrast_v0.sqlite --out results\sft_v1_eval_constrained\medication_contrast_v0\product_spine_report.json --markdown-out results\sft_v1_eval_constrained\medication_contrast_v0\product_spine_doctor_summary.md --limit 4

        python scripts\compare_sft_v1_constrained.py
    }
}

Run-Command "go/no-go report" {
    python scripts\go_no_go_report.py
}

Run-Command "project gap report" {
    python scripts\project_gap_report.py
}

Run-Command "sft v1.1 gap summary" {
    python scripts\summarize_v1_1_gaps.py
}

Run-Command "heartbeat report" {
    python scripts\heartbeat_report.py
}

Write-Host "workflow checks ok"
