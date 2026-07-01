from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    now = datetime.now()
    out_dir = ROOT / "results" / "heartbeat"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"heartbeat_{now:%Y%m%d_%H%M%S}.md"

    metrics = read_json(ROOT / "results" / "eval_fixture_metrics.json")
    medication_contrast = read_json(ROOT / "results" / "eval_medication_contrast_metrics.json")
    schema_edge = read_json(ROOT / "results" / "schema_edge_cases_v0" / "metrics.json")
    schema_edge_product_report = read_json(ROOT / "results" / "schema_edge_cases_v0" / "product_spine_report.json")
    safety_onset_edge = read_json(ROOT / "results" / "safety_onset_edge_v1_1" / "metrics.json")
    safety_onset_product_report = read_json(
        ROOT / "results" / "safety_onset_edge_v1_1" / "product_spine_report.json"
    )
    product_report = read_json(ROOT / "results" / "product_spine" / "synthetic_v0_report.json")
    baseline_v1 = read_json(ROOT / "results" / "baseline" / "metrics_qwen7b_63312758.json")
    baseline_schema_v2 = read_json(ROOT / "results" / "baseline_schema_v2" / "metrics.json")
    baseline_schema_v3 = read_json(ROOT / "results" / "baseline_schema_v3" / "metrics.json")
    baseline_schema_v3_normalized = read_json(ROOT / "results" / "baseline_schema_v3" / "metrics_normalized.json")
    med_schema_v3 = read_json(ROOT / "results" / "medication_contrast_schema_v3" / "metrics.json")
    med_schema_v3_template = read_json(
        ROOT / "results" / "medication_contrast_schema_v3" / "metrics_template_summary.json"
    )
    med_schema_v4 = read_json(ROOT / "results" / "medication_contrast_schema_v4" / "metrics.json")
    sft_synthetic = read_json(
        ROOT
        / "results"
        / "sft_smoke_eval_64164883"
        / "synthetic_v0"
        / "metrics_report_type_template_summary.json"
    )
    sft_medication = read_json(
        ROOT
        / "results"
        / "sft_smoke_eval_64164883"
        / "medication_contrast_v0"
        / "metrics_report_type_template_summary.json"
    )
    sft_comparison = ROOT / "results" / "sft_smoke_eval_64164883" / "comparison.md"
    sft_v1_synthetic = read_json(
        ROOT
        / "results"
        / "sft_v1_eval"
        / "synthetic_v0"
        / "metrics_report_type_template_summary.json"
    )
    sft_v1_medication = read_json(
        ROOT
        / "results"
        / "sft_v1_eval"
        / "medication_contrast_v0"
        / "metrics_report_type_template_summary.json"
    )
    sft_v1_comparison = ROOT / "results" / "sft_v1_eval" / "comparison.md"
    sft_v1_constrained_synthetic = read_json(
        ROOT
        / "results"
        / "sft_v1_eval_constrained"
        / "synthetic_v0"
        / "metrics_report_type_template_summary.json"
    )
    sft_v1_constrained_medication = read_json(
        ROOT
        / "results"
        / "sft_v1_eval_constrained"
        / "medication_contrast_v0"
        / "metrics_report_type_template_summary.json"
    )
    sft_v1_constrained_comparison = ROOT / "results" / "sft_v1_eval_constrained" / "comparison.md"
    sft_v1_v1_1 = read_json(
        ROOT
        / "results"
        / "sft_v1_eval_v1_1"
        / "safety_onset_edge_v1_1"
        / "metrics_report_type_template_summary.json"
    )
    sft_v1_v1_1_product = read_json(
        ROOT
        / "results"
        / "sft_v1_eval_v1_1"
        / "safety_onset_edge_v1_1"
        / "product_spine_report.json"
    )
    sft_v1_v1_1_recovered = read_json(
        ROOT
        / "results"
        / "sft_v1_eval_v1_1"
        / "safety_onset_edge_v1_1"
        / "metrics_recovered_report_type_template_summary.json"
    )
    sft_v1_v1_1_recovery_report = read_json(
        ROOT / "results" / "sft_v1_eval_v1_1" / "safety_onset_edge_v1_1" / "recovery_report.json"
    )
    sft_v1_v1_1_recovered_product = read_json(
        ROOT
        / "results"
        / "sft_v1_eval_v1_1"
        / "safety_onset_edge_v1_1"
        / "product_spine_recovered_report.json"
    )
    schema_v2_contract = read_json(ROOT / "results" / "baseline_schema_v2" / "contract_validation.json")
    schema_v3_contract = read_json(ROOT / "results" / "baseline_schema_v3" / "contract_validation_local.json")
    schema_v3_normalized_contract = read_json(ROOT / "results" / "baseline_schema_v3" / "contract_validation_normalized.json")
    status = run(["git", "status", "--short"])
    remote_log = latest_file(ROOT / "results" / "remote_setup", "*.log")
    go_no_go = ROOT / "results" / "go_no_go" / "latest_go_no_go.md"
    project_gap = ROOT / "results" / "progress" / "latest_project_gap_report.md"
    sft_v1_1_gap = ROOT / "results" / "progress" / "latest_sft_v1_1_gap_summary.md"
    med_comparison = ROOT / "results" / "medication_contrast_comparison.md"
    sft_validation = read_json(ROOT / "results" / "sft_smoke_validation.json")

    body = [
        f"# Lora Health Heartbeat {now:%Y-%m-%d %H:%M:%S}",
        "",
        "## Phase",
        "",
        phase_line(
            baseline_v1,
            baseline_schema_v2,
            baseline_schema_v3,
            sft_synthetic,
            sft_v1_synthetic,
            sft_v1_constrained_synthetic,
        ),
        "- Do not run a broad rank/data-size sweep. The current win comes from constrained product-layer normalization.",
        "- Narval access must keep using interactive MFA or an already authenticated session; no secrets are stored.",
        "",
        "## Local Eval Fixture",
        "",
        metric_line(metrics, "dataset_version"),
        metric_line(metrics, "example_count"),
        metric_line(metrics, "extraction_field_f1"),
        metric_line(metrics, "summary_point_coverage"),
        metric_line(metrics, "summary_point_relaxed_coverage"),
        metric_line(metrics, "unsupported_claim_rate"),
        metric_line(metrics, "hallucination_rate"),
        metric_line(metrics, "overdiagnosis_rate"),
        metric_line(metrics, "safety_refusal_rate"),
        metric_line(metrics, "crisis_escalation_recall"),
        "",
        "## Medication Contrast Fixture",
        "",
        metric_line(medication_contrast, "dataset_version"),
        metric_line(medication_contrast, "example_count"),
        metric_line(medication_contrast, "extraction_field_f1"),
        metric_line(medication_contrast, "summary_point_coverage"),
        metric_line(medication_contrast, "summary_point_relaxed_coverage"),
        metric_line(medication_contrast, "safety_refusal_rate"),
        metric_line(medication_contrast, "safety_false_refusal_rate"),
        "",
        "## Schema Edge Constrained Fixture",
        "",
        metric_line(schema_edge, "dataset_version"),
        metric_line(schema_edge, "example_count"),
        metric_line(schema_edge, "extraction_field_f1"),
        metric_line(schema_edge, "summary_point_coverage"),
        metric_line(schema_edge, "summary_point_relaxed_coverage"),
        metric_line(schema_edge, "unsupported_claim_rate"),
        metric_line(schema_edge, "safety_false_refusal_rate"),
        product_normalization_line(schema_edge_product_report),
        "",
        "## Safety/Onset Edge v1.1 Fixture",
        "",
        metric_line(safety_onset_edge, "dataset_version"),
        metric_line(safety_onset_edge, "example_count"),
        metric_line(safety_onset_edge, "extraction_field_f1"),
        metric_line(safety_onset_edge, "summary_point_coverage"),
        metric_line(safety_onset_edge, "summary_point_relaxed_coverage"),
        metric_line(safety_onset_edge, "unsupported_claim_rate"),
        metric_line(safety_onset_edge, "safety_refusal_rate"),
        metric_line(safety_onset_edge, "safety_false_refusal_rate"),
        metric_line(safety_onset_edge, "crisis_escalation_recall"),
        metric_line(safety_onset_edge, "crisis_false_escalation_rate"),
        product_safety_line(safety_onset_product_report),
        "",
        "## Local Product Spine",
        "",
        product_line(product_report, "timeline", "timeline_rows"),
        product_line(product_report.get("doctor_summary", {}), "lab_items", "lab_items"),
        product_line(product_report.get("doctor_summary", {}), "symptoms", "symptoms"),
        product_line(product_report, "safety_escalations", "safety_escalations"),
        product_line(product_report, "safety_refusals", "safety_refusals"),
        "",
        "## Baseline Results",
        "",
        baseline_block("qwen7b_v1_63312758", baseline_v1),
        "",
        baseline_block("qwen7b_schema_v2_63344883", baseline_schema_v2),
        "",
        baseline_block("qwen7b_schema_v3_63839439", baseline_schema_v3),
        "",
        baseline_block("qwen7b_schema_v3_normalized_63839439", baseline_schema_v3_normalized),
        "",
        "## Medication Contrast Model Checks",
        "",
        baseline_block("qwen7b_med_schema_v3_63925409", med_schema_v3),
        "",
        baseline_block("qwen7b_med_schema_v3_template_summary", med_schema_v3_template),
        "",
        baseline_block("qwen7b_med_schema_v4_63970602", med_schema_v4),
        "",
        "## SFT Smoke Eval",
        "",
        baseline_block("qwen7b_lora_sft_smoke_v0_synthetic", sft_synthetic),
        "",
        baseline_block("qwen7b_lora_sft_smoke_v0_medication_contrast", sft_medication),
        "",
        f"- Comparison report: `{sft_comparison.relative_to(ROOT)}`"
        if sft_comparison.exists()
        else "- Comparison report: missing",
        "",
        "## SFT v1 Eval",
        "",
        baseline_block("qwen7b_lora_sft_v1_synthetic", sft_v1_synthetic),
        "",
        baseline_block("qwen7b_lora_sft_v1_medication_contrast", sft_v1_medication),
        "",
        f"- Comparison report: `{sft_v1_comparison.relative_to(ROOT)}`"
        if sft_v1_comparison.exists()
        else "- Comparison report: missing",
        "",
        "## SFT v1 Constrained Eval",
        "",
        baseline_block("qwen7b_lora_sft_v1_constrained_synthetic", sft_v1_constrained_synthetic),
        "",
        baseline_block(
            "qwen7b_lora_sft_v1_constrained_medication_contrast",
            sft_v1_constrained_medication,
        ),
        "",
        f"- Comparison report: `{sft_v1_constrained_comparison.relative_to(ROOT)}`"
        if sft_v1_constrained_comparison.exists()
        else "- Comparison report: missing",
        "",
        "## SFT v1 Safety/Onset Edge v1.1 Eval",
        "",
        baseline_block("qwen7b_lora_sft_v1_safety_onset_edge_v1_1", sft_v1_v1_1),
        "",
        product_safety_line(sft_v1_v1_1_product),
        "",
        recovery_line(sft_v1_v1_1_recovery_report),
        "",
        baseline_block("qwen7b_lora_sft_v1_safety_onset_edge_v1_1_recovered", sft_v1_v1_1_recovered),
        "",
        product_safety_line(sft_v1_v1_1_recovered_product),
        "",
        "## Contract Checks",
        "",
        contract_block("qwen7b_schema_v2_63344883", schema_v2_contract),
        "",
        contract_block("qwen7b_schema_v3_63839439", schema_v3_contract),
        "",
        contract_block("qwen7b_schema_v3_normalized_63839439", schema_v3_normalized_contract),
        "",
        "## Git Status",
        "",
        "```text",
        status.strip() or "clean or unavailable",
        "```",
        "",
        "## Remote Setup",
        "",
        f"- Latest local remote setup log: `{remote_log.relative_to(ROOT)}`" if remote_log else "- No remote setup log found.",
        "",
        "## Go/No-Go",
        "",
        f"- Latest report: `{go_no_go.relative_to(ROOT)}`" if go_no_go.exists() else "- Latest report: missing",
        f"- Medication contrast comparison: `{med_comparison.relative_to(ROOT)}`"
        if med_comparison.exists()
        else "- Medication contrast comparison: missing",
        f"- Project gap report: `{project_gap.relative_to(ROOT)}`"
        if project_gap.exists()
        else "- Project gap report: missing",
        f"- SFT v1.1 gap summary: `{sft_v1_1_gap.relative_to(ROOT)}`"
        if sft_v1_1_gap.exists()
        else "- SFT v1.1 gap summary: missing",
        "",
        "## SFT Smoke Readiness",
        "",
        sft_validation_line(sft_validation),
        "",
        "## Next Safe Step",
        "",
        next_step_line(
            baseline_v1,
            baseline_schema_v2,
            baseline_schema_v3,
            baseline_schema_v3_normalized,
            sft_synthetic,
            sft_medication,
            sft_v1_synthetic,
            sft_v1_medication,
            sft_v1_constrained_synthetic,
            sft_v1_constrained_medication,
            sft_v1_v1_1_recovered,
        ),
        "",
    ]

    out_path.write_text("\n".join(body), encoding="utf-8")
    print(out_path)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def metric_line(metrics: dict, key: str) -> str:
    value = metrics.get(key, "missing")
    return f"- {key}: {value}"


def product_line(report: dict, key: str, label: str) -> str:
    value = report.get(key)
    if isinstance(value, list):
        return f"- {label}: {len(value)}"
    return f"- {label}: missing"


def product_normalization_line(report: dict) -> str:
    normalization = report.get("normalization") or {}
    if not normalization:
        return "- product_spine_normalization_changed_predictions: missing"
    return (
        "- product_spine_normalization_changed_predictions: "
        f"{normalization.get('changed_prediction_count', 'missing')}"
    )


def product_safety_line(report: dict) -> str:
    if not report:
        return "- product_spine_safety_events: missing"
    return (
        "- product_spine_safety_events: "
        f"refusals={len(report.get('safety_refusals') or [])}, "
        f"escalations={len(report.get('safety_escalations') or [])}"
    )


def recovery_line(report: dict) -> str:
    if not report:
        return "- recovery: missing"
    return (
        "- recovery: "
        f"parse_errors={report.get('parse_error_count', 'missing')}, "
        f"json_unit_repairs={report.get('json_repair_applied_count', 'missing')}"
    )


def phase_line(
    baseline_v1: dict,
    baseline_schema_v2: dict,
    baseline_schema_v3: dict,
    sft_synthetic: dict,
    sft_v1_synthetic: dict,
    sft_v1_constrained_synthetic: dict,
) -> str:
    if sft_v1_constrained_synthetic:
        return "- Current safe phase: Phase 4 constrained v1 product-layer integration plus eval-slice expansion."
    if sft_v1_synthetic:
        return "- Current safe phase: Phase 4 v1 adapter evaluation plus failure-analysis planning."
    if sft_synthetic:
        return "- Current safe phase: Phase 4 smoke adapter evaluation plus failure-driven v1 data planning."
    if baseline_schema_v3:
        return "- Current safe phase: Phase 2 prompt/schema baseline analysis plus Phase 3 product-spine validation."
    if baseline_schema_v2:
        return "- Current safe phase: Phase 2 prompt/schema baseline analysis plus Phase 3 product-spine validation."
    if baseline_v1:
        return "- Current safe phase: Phase 2 baseline analysis plus Phase 3 product-spine validation."
    return "- Current safe phase: Phase 3 local product spine, with Phase 2 baseline still pending model access."


def baseline_block(label: str, metrics: dict) -> str:
    if not metrics:
        return f"- {label}: missing or not pulled yet"
    keys = [
        "example_count",
        "extraction_field_f1",
        "summary_point_coverage",
        "summary_point_relaxed_coverage",
        "safety_refusal_rate",
        "crisis_escalation_recall",
        "hallucination_rate",
        "overdiagnosis_rate",
    ]
    values = ", ".join(f"{key}={metrics.get(key, 'missing')}" for key in keys)
    return f"- {label}: {values}"


def contract_block(label: str, report: dict) -> str:
    if not report:
        return f"- {label}: contract validation missing"
    return (
        f"- {label}: valid_contract={report.get('valid_contract_count', 'missing')}/"
        f"{report.get('prediction_count', 'missing')}, "
        f"product_spine_ready={report.get('product_spine_ready_count', 'missing')}/"
        f"{report.get('prediction_count', 'missing')}, "
        f"evaluable={report.get('evaluable_count', 'missing')}/"
        f"{report.get('prediction_count', 'missing')}"
    )


def sft_validation_line(report: dict) -> str:
    if not report:
        return "- SFT smoke dataset validation: missing"
    return (
        f"- SFT smoke dataset validation: status={report.get('status', 'missing')}, "
        f"train_rows={report.get('train_rows', 'missing')}, "
        f"val_rows={report.get('val_rows', 'missing')}, "
        f"checked_rows={report.get('checked_rows', 'missing')}"
    )


def next_step_line(
    baseline_v1: dict,
    baseline_schema_v2: dict,
    baseline_schema_v3: dict,
    baseline_schema_v3_normalized: dict,
    sft_synthetic: dict,
    sft_medication: dict,
    sft_v1_synthetic: dict,
    sft_v1_medication: dict,
    sft_v1_constrained_synthetic: dict,
    sft_v1_constrained_medication: dict,
    sft_v1_v1_1_recovered: dict,
) -> str:
    if sft_v1_v1_1_recovered:
        return "Sync the narrow JSON unit-value repair into the next Narval eval runner, then inspect remaining v1.1 extraction gaps before any tiny v2 proposal."
    if sft_v1_constrained_synthetic and sft_v1_constrained_medication:
        return "Inspect the safety/onset edge v1.1 parse-error and low extraction/summary failures; prefer constrained JSON decoding or narrowly targeted synthetic data before any tiny v2 proposal."
    if sft_v1_synthetic and sft_v1_medication:
        return "Inspect v1 per-example extraction failures and test constrained report_type/enum normalization before any further training."
    if sft_synthetic and sft_medication:
        return "Add targeted synthetic examples for remaining report_type/product-spine label failures, validate privacy/leakage, then ask for approval before one slightly larger SFT v1."
    if baseline_schema_v3_normalized:
        return "Review the SFT smoke package, then request explicit approval before submitting one guarded public/synthetic LoRA smoke run."
    if baseline_schema_v3:
        return "Review schema_v3 failures, decide whether to add normalization/constrained decoding or prepare a small public/synthetic SFT proposal for user approval."
    if baseline_schema_v2:
        return "Compare v1 versus schema_v2, run product-spine ingest on schema_v2 predictions, then update the Go/No-Go decision."
    if baseline_v1:
        return "Pull schema_v2 results from Narval, compare against v1, and verify whether schema_v2 predictions can enter the product spine."
    return "Run baseline evaluation when model access is ready; keep Narval work to interactive setup/status until the Go/No-Go gate is satisfied."


def latest_file(folder: Path, pattern: str) -> Path | None:
    if not folder.exists():
        return None
    files = sorted(folder.glob(pattern), key=lambda path: path.stat().st_mtime)
    return files[-1] if files else None


def run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, cwd=ROOT, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return "command not found: " + cmd[0]
    text = result.stdout
    if result.stderr:
        text += "\n" + result.stderr
    return text


if __name__ == "__main__":
    main()
