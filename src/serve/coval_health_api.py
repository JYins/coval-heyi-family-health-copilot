from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


class SafetyState(str, Enum):
    passed = "passed"
    refused = "refused"
    escalated = "escalated"


class FamilyMember(BaseModel):
    id: str
    name: str
    relation: str
    age: int
    profile: str
    badges: list[str]


class StructuringRequest(BaseModel):
    member_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=8000)
    input_mode: Literal["text", "ocr", "voice"] = "text"


class StructuringResponse(BaseModel):
    report_type: str
    safety: SafetyState
    symptoms: list[str]
    medications: list[str]
    allergies: list[str]
    missing_fields: list[str]
    visit_summary: str
    unsupported_claims: int
    forbidden_advice: int


class ModelEvidenceItem(BaseModel):
    label: str
    value: str
    source: str


class ModelEvidenceResponse(BaseModel):
    base_model: str
    adapter: str
    status: str
    metrics: list[ModelEvidenceItem]


app = FastAPI(
    title="Coval HeYi API",
    version="0.1.0",
    description="Synthetic family health memory API for the LoRA health demo.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


ROOT = Path(__file__).resolve().parents[2]
V1_1_METRICS = (
    ROOT
    / "results"
    / "sft_v1_eval_v1_1"
    / "safety_onset_edge_v1_1"
    / "metrics_recovered_report_type_template_summary.json"
)
V2_COMPARISON = ROOT / "results" / "sft_v2_eval" / "comparison.md"
V2_METRICS = (
    ROOT
    / "results"
    / "sft_v2_eval"
    / "safety_onset_edge_v1_1"
    / "metrics_recovered_report_type_template_summary.json"
)
V2_TEMPLATE_PATCH_METRICS = (
    ROOT
    / "results"
    / "sft_v2_eval_template_patch"
    / "safety_onset_edge_v1_1"
    / "metrics_recovered_report_type_template_summary.json"
)
V3_COMPARISON = ROOT / "results" / "sft_v3_eval" / "comparison_vs_v2_template_patch.md"


FAMILY_MEMBERS = [
    FamilyMember(
        id="mom",
        name="妈妈",
        relation="家庭重点照护",
        age=58,
        profile="高血压随访中，近期有呼吸道症状记录，需要把用药、过敏和就诊问题整理清楚。",
        badges=["慢病随访", "过敏核对", "就诊准备"],
    ),
    FamilyMember(
        id="dad",
        name="爸爸",
        relation="用药记录较多",
        age=61,
        profile="血压、血脂和复诊计划需要长期归档，重点避免把用药记录误当成剂量建议。",
        badges=["药物清单", "复诊提醒", "安全边界"],
    ),
    FamilyMember(
        id="self",
        name="我",
        relation="个人健康档案",
        age=24,
        profile="体检、疫苗、过敏和保险材料归档，方便以后快速查找。",
        badges=["体检", "疫苗", "保险材料"],
    ),
]


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "api": "ok",
        "llm_service": "mock",
        "model": "Qwen/Qwen2.5-7B-Instruct + LoRA SFT v2 + deterministic summary patch",
        "privacy": "synthetic_demo_only",
    }


@app.get("/model-evidence", response_model=ModelEvidenceResponse)
def model_evidence() -> ModelEvidenceResponse:
    source_path = V1_1_METRICS
    metrics = _load_metrics(source_path)
    status = "sft_v2_eval_pending"
    adapter = "LoRA SFT v1.1"

    if V2_METRICS.exists() and V2_COMPARISON.exists():
        source_path = V2_METRICS
        metrics = _load_metrics(source_path)
        status = "sft_v2_eval_available"
        adapter = "LoRA SFT v2 candidate"

    if V2_TEMPLATE_PATCH_METRICS.exists():
        source_path = V2_TEMPLATE_PATCH_METRICS
        metrics = _load_metrics(source_path)
        status = "sft_v2_template_patch_available"
        adapter = "LoRA SFT v2 + deterministic summary patch"

    if V2_TEMPLATE_PATCH_METRICS.exists() and V3_COMPARISON.exists():
        status = "sft_v3_ablation_complete_keep_v2_template_patch"

    evidence_items = [
        ModelEvidenceItem(
            label="Extraction F1",
            value=_format_metric(metrics.get("extraction_field_f1")),
            source=str(source_path.relative_to(ROOT)),
        ),
        ModelEvidenceItem(
            label="Summary strict",
            value=_format_metric(metrics.get("summary_point_coverage")),
            source=str(source_path.relative_to(ROOT)),
        ),
        ModelEvidenceItem(
            label="Summary relaxed",
            value=_format_metric(metrics.get("summary_point_relaxed_coverage")),
            source=str(source_path.relative_to(ROOT)),
        ),
        ModelEvidenceItem(
            label="Safety refusal",
            value=_format_percent(metrics.get("safety_refusal_rate")),
            source=str(source_path.relative_to(ROOT)),
        ),
        ModelEvidenceItem(
            label="Crisis recall",
            value=_format_percent(metrics.get("crisis_escalation_recall")),
            source=str(source_path.relative_to(ROOT)),
        ),
        ModelEvidenceItem(
            label="Hallucination / overdiagnosis",
            value=(
                f"{_format_percent(metrics.get('hallucination_rate'))} / "
                f"{_format_percent(metrics.get('overdiagnosis_rate'))}"
            ),
            source=str(source_path.relative_to(ROOT)),
        ),
    ]
    if V3_COMPARISON.exists():
        evidence_items.append(
            ModelEvidenceItem(
                label="Latest ablation",
                value="SFT v3 completed; not adopted",
                source=str(V3_COMPARISON.relative_to(ROOT)),
            )
        )

    return ModelEvidenceResponse(
        base_model="Qwen/Qwen2.5-7B-Instruct",
        adapter=adapter,
        status=status,
        metrics=evidence_items,
    )


@app.get("/family-members", response_model=list[FamilyMember])
def list_family_members() -> list[FamilyMember]:
    return FAMILY_MEMBERS


@app.post("/structure", response_model=StructuringResponse)
def structure_record(payload: StructuringRequest) -> StructuringResponse:
    known_member_ids = {member.id for member in FAMILY_MEMBERS}
    if payload.member_id not in known_member_ids:
        raise HTTPException(status_code=404, detail=f"Unknown family member: {payload.member_id}")

    text = payload.text
    if any(term in text for term in ["喘不上气", "喉咙发紧", "嘴唇"]):
        return StructuringResponse(
            report_type="危急症状",
            safety=SafetyState.escalated,
            symptoms=["喘不上气", "喉咙发紧", "嘴唇肿"],
            medications=["新开药，名称未记录"],
            allergies=["需要核对药物过敏史"],
            missing_fields=["药物名称", "过敏史核对", "是否出现皮疹或头晕"],
            visit_summary=(
                "服药后出现嘴唇肿、喉咙发紧和喘不上气，属于需要立即处理的危险信号。"
                "不要在家等待观察，应立即联系急救或就近急诊，并携带药物包装。"
            ),
            unsupported_claims=0,
            forbidden_advice=1,
        )

    if any(term in text for term in ["加倍", "两片", "补回来", "剂量"]):
        return StructuringResponse(
            report_type="安全请求",
            safety=SafetyState.refused,
            symptoms=["血压记录或用药问题"],
            medications=["药名和规格需核对"],
            allergies=[],
            missing_fields=["原始医嘱", "药物规格", "连续症状或血压记录"],
            visit_summary=(
                "这条记录涉及用药剂量调整。系统不提供具体加量、减量或补服建议。"
                "建议按原医嘱或药品说明处理，并联系医生或药师确认。"
            ),
            unsupported_claims=0,
            forbidden_advice=1,
        )

    return StructuringResponse(
        report_type="家庭健康记录",
        safety=SafetyState.passed,
        symptoms=[term for term in ["咳嗽", "发热", "喉咙痛", "鼻塞"] if term in text],
        medications=[term for term in ["布洛芬", "氯沙坦", "二甲双胍"] if term in text],
        allergies=[term for term in ["青霉素过敏"] if term in text],
        missing_fields=["开始时间", "药物剂量", "近期接触史"],
        visit_summary=(
            "已整理为家庭健康记录，可在就诊前核对症状、用药、过敏史和缺失信息。"
            "该摘要只用于沟通准备，不提供诊断或治疗方案。"
        ),
        unsupported_claims=0,
        forbidden_advice=0,
    )


def _load_metrics(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key: float(value) for key, value in data.items() if isinstance(value, (int, float))}


def _format_metric(value: float | None) -> str:
    if value is None:
        return "not run"
    return f"{value:.4f}"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "not run"
    return f"{value * 100:.0f}%"
