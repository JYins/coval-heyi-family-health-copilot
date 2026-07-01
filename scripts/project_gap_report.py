from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results" / "progress"


def main() -> None:
    now = datetime.now()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"project_gap_report_{now:%Y%m%d_%H%M%S}.md"

    evidence = load_evidence()
    report = render_report(now, evidence)
    out_path.write_text(report, encoding="utf-8")
    (OUT_DIR / "latest_project_gap_report.md").write_text(report, encoding="utf-8")
    print(out_path)


def load_evidence() -> dict[str, Any]:
    return {
        "baseline_v1": read_json(ROOT / "results" / "baseline" / "metrics_qwen7b_63312758.json"),
        "schema_v3_template": read_json(
            ROOT / "results" / "baseline_schema_v3" / "metrics_report_type_template_summary.json"
        ),
        "product_spine": read_json(ROOT / "results" / "product_spine" / "synthetic_v0_report.json"),
        "sft_v1_constrained_synthetic": read_json(
            ROOT
            / "results"
            / "sft_v1_eval_constrained"
            / "synthetic_v0"
            / "metrics_report_type_template_summary.json"
        ),
        "sft_v1_constrained_medication": read_json(
            ROOT
            / "results"
            / "sft_v1_eval_constrained"
            / "medication_contrast_v0"
            / "metrics_report_type_template_summary.json"
        ),
        "sft_v1_v1_1": read_json(
            ROOT
            / "results"
            / "sft_v1_eval_v1_1"
            / "safety_onset_edge_v1_1"
            / "metrics_report_type_template_summary.json"
        ),
        "sft_v1_v1_1_recovered": read_json(
            ROOT
            / "results"
            / "sft_v1_eval_v1_1"
            / "safety_onset_edge_v1_1"
            / "metrics_recovered_report_type_template_summary.json"
        ),
        "recovery_report": read_json(
            ROOT / "results" / "sft_v1_eval_v1_1" / "safety_onset_edge_v1_1" / "recovery_report.json"
        ),
        "recovered_contract": read_json(
            ROOT
            / "results"
            / "sft_v1_eval_v1_1"
            / "safety_onset_edge_v1_1"
            / "contract_validation_recovered_report_type_template_summary.json"
        ),
        "recovered_product": read_json(
            ROOT
            / "results"
            / "sft_v1_eval_v1_1"
            / "safety_onset_edge_v1_1"
            / "product_spine_recovered_report.json"
        ),
    }


def render_report(now: datetime, evidence: dict[str, Any]) -> str:
    readiness = estimate_readiness(evidence)
    remaining = remaining_steps(evidence)
    lines = [
        f"# Project Gap Report {now:%Y-%m-%d %H:%M:%S}",
        "",
        "This report uses only public/synthetic artifacts already present in the repo.",
        "It is a project-management estimate, not a clinical-quality claim.",
        "",
        "## How Far Along",
        "",
        f"- Portfolio/research story readiness: about {readiness['story_percent']}%.",
        f"- Local pipeline and eval infrastructure readiness: about {readiness['infra_percent']}%.",
        f"- Remaining focused work blocks: {len(remaining)}.",
        "",
        "## Evidence Snapshot",
        "",
        metric_row("Base 7B baseline", evidence["baseline_v1"]),
        metric_row("Schema v3 plus product template", evidence["schema_v3_template"]),
        metric_row("SFT v1 constrained synthetic", evidence["sft_v1_constrained_synthetic"]),
        metric_row("SFT v1 constrained medication", evidence["sft_v1_constrained_medication"]),
        metric_row("SFT v1 v1.1 hard slice", evidence["sft_v1_v1_1"]),
        metric_row("SFT v1 v1.1 hard slice recovered", evidence["sft_v1_v1_1_recovered"]),
        recovery_row(evidence["recovery_report"]),
        contract_row(evidence["recovered_contract"]),
        product_row(evidence["recovered_product"]),
        "",
        "## Completed",
        "",
        "- Eval-first harness for extraction, summary coverage, unsupported claims, safety refusal, crisis escalation, hallucination, and overdiagnosis.",
        "- Fake-data product spine: structured reports flow into timeline, doctor summary, safety refusal, and crisis escalation artifacts.",
        "- Base-model baseline and schema/prompt comparisons are logged.",
        "- One SFT adapter has been trained and evaluated against synthetic, medication-contrast, and harder safety/onset examples.",
        "- Constrained product-layer normalization and narrow JSON unit-value recovery improved ingestion without changing safety decisions.",
        "",
        "## Remaining",
        "",
    ]
    lines.extend(f"- {step}" for step in remaining)
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "- Do not run a broad rank/data-size sweep yet.",
            "- Next best move: sync the parser/recovery patch to Narval, run one eval-only confirmation, then inspect remaining v1.1 misses before deciding whether a tiny v2 data patch is justified.",
            "- After that, switch from research iteration to packaging: README results table, model/eval card, privacy boundary, and a demo narrative.",
            "",
        ]
    )
    return "\n".join(lines)


def estimate_readiness(evidence: dict[str, Any]) -> dict[str, int]:
    story = 55
    infra = 60
    if evidence["product_spine"]:
        story += 8
        infra += 10
    if evidence["sft_v1_constrained_synthetic"] and evidence["sft_v1_constrained_medication"]:
        story += 10
        infra += 10
    if evidence["sft_v1_v1_1_recovered"]:
        story += 7
        infra += 8
    if ready_contract(evidence["recovered_contract"]):
        infra += 5
    if safety_gates_pass(evidence["sft_v1_v1_1_recovered"]):
        story += 5
        infra += 5
    return {"story_percent": min(story, 85), "infra_percent": min(infra, 95)}


def remaining_steps(evidence: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    if not evidence["sft_v1_v1_1_recovered"]:
        steps.append("Finish recovered v1.1 evaluation on saved public/synthetic raw outputs.")
    if evidence["sft_v1_v1_1_recovered"]:
        steps.append("Sync the narrow JSON unit-value repair into the Narval eval runner and run one eval-only confirmation.")
    if evidence["sft_v1_v1_1_recovered"]:
        steps.append("Inspect remaining v1.1 misses: onset granularity, extra appointment typing, and summary exactness.")
    steps.append("Decide whether a tiny v2 data patch is justified; skip broad sweeps unless the failure analysis demands it.")
    steps.append("Package the project story: README results table, model/eval card, privacy policy, reproducibility notes, and resume bullets.")
    steps.append("Polish the fake-data product demo path so the research result plugs back into the family-health copilot narrative.")
    return steps


def metric_row(label: str, metrics: dict[str, Any]) -> str:
    if not metrics:
        return f"- {label}: missing"
    keys = [
        "example_count",
        "extraction_field_f1",
        "summary_point_relaxed_coverage",
        "safety_refusal_rate",
        "crisis_escalation_recall",
        "hallucination_rate",
        "overdiagnosis_rate",
    ]
    values = ", ".join(f"{key}={metrics.get(key, 'missing')}" for key in keys)
    return f"- {label}: {values}"


def recovery_row(report: dict[str, Any]) -> str:
    if not report:
        return "- JSON recovery: missing"
    return (
        "- JSON recovery: "
        f"parse_errors={report.get('parse_error_count', 'missing')}, "
        f"unit_repairs={report.get('json_repair_applied_count', 'missing')}"
    )


def contract_row(report: dict[str, Any]) -> str:
    if not report:
        return "- Recovered contract: missing"
    count = report.get("prediction_count", "missing")
    return (
        "- Recovered contract: "
        f"valid={report.get('valid_contract_count', 'missing')}/{count}, "
        f"product_spine_ready={report.get('product_spine_ready_count', 'missing')}/{count}, "
        f"evaluable={report.get('evaluable_count', 'missing')}/{count}"
    )


def product_row(report: dict[str, Any]) -> str:
    if not report:
        return "- Recovered product spine: missing"
    doctor_summary = report.get("doctor_summary", {})
    return (
        "- Recovered product spine: "
        f"timeline={len(report.get('timeline') or [])}, "
        f"recent_reports={len(doctor_summary.get('recent_reports') or [])}, "
        f"lab_items={len(doctor_summary.get('lab_items') or [])}, "
        f"symptoms={len(doctor_summary.get('symptoms') or [])}, "
        f"refusals={len(report.get('safety_refusals') or [])}, "
        f"escalations={len(report.get('safety_escalations') or [])}"
    )


def ready_contract(report: dict[str, Any]) -> bool:
    count = report.get("prediction_count")
    return bool(
        count
        and report.get("valid_contract_count") == count
        and report.get("product_spine_ready_count") == count
        and report.get("evaluable_count") == count
    )


def safety_gates_pass(metrics: dict[str, Any]) -> bool:
    return bool(
        metrics
        and metrics.get("safety_refusal_rate") == 1.0
        and metrics.get("safety_false_refusal_rate") == 0.0
        and metrics.get("crisis_escalation_recall") == 1.0
        and metrics.get("crisis_false_escalation_rate") == 0.0
        and metrics.get("hallucination_rate") == 0.0
        and metrics.get("overdiagnosis_rate") == 0.0
    )


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
