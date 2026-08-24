from __future__ import annotations

"""
Legacy v0.1 demo implementation retained temporarily for file-history context.
The executable compatibility entrypoint is below this string and delegates to
``memory_api.create_app``. No legacy routes or in-memory save behavior execute.

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
    input_mode: Literal["text", "ocr", "voice", "blood_pressure"] = "text"


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


class ProductLineageResponse(BaseModel):
    origin: str
    workflow: list[str]
    current_scope: list[str]
    not_claimed: list[str]


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
        age=67,
        profile="高血压随访中，经常有报告、血压、症状和用药问题需要整理。",
        badges=["每日血压", "报告归档", "复诊准备"],
    ),
    FamilyMember(
        id="dad",
        name="爸爸",
        relation="用药记录较多",
        age=62,
        profile="血压、血脂和复诊计划需要长期归档，重点避免把用药记录误当成剂量建议。",
        badges=["药物清单", "安全边界", "随访提醒"],
    ),
    FamilyMember(
        id="self",
        name="本人",
        relation="个人健康档案",
        age=24,
        profile="体检、疫苗、过敏和保险材料归档，方便之后快速查找。",
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


@app.get("/product-lineage", response_model=ProductLineageResponse)
def product_lineage() -> ProductLineageResponse:
    return ProductLineageResponse(
        origin="Coval AI memo 的长期记忆思路，延伸到家庭健康记录、复诊准备和安全边界。",
        workflow=[
            "capture",
            "structure",
            "review",
            "save_to_sqlite_memory",
            "visit_prep_summary",
            "safety_evidence",
        ],
        current_scope=[
            "Next.js/FastAPI/SQLite demo over synthetic examples",
            "Qwen2.5-7B LoRA SFT v2 adapter packaged on private Hugging Face",
            "evaluation-first metrics for extraction, summary, safety, crisis, hallucination, and overdiagnosis",
        ],
        not_claimed=[
            "not a diagnostic system",
            "not a production RAG agent yet",
            "not a completed llama.cpp/GGUF local runtime yet",
            "not trained on real family data",
        ],
    )


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
        ModelEvidenceItem(label="Training data", value="26 synthetic rows", source="data/public/sft_v2/manifest.json"),
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
        ModelEvidenceItem(label="RAG phase", value="retrieval scaffold only", source="results/rag_v0/metrics.json"),
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
    if _contains_any(text, ["喘不上气", "喉咙发紧", "嘴唇", "胸痛", "气短"]):
        return StructuringResponse(
            report_type="危急症状",
            safety=SafetyState.escalated,
            symptoms=[term for term in ["喘不上气", "喉咙发紧", "嘴唇肿", "胸痛", "气短"] if term in text],
            medications=["新开药，名称需核对"] if "药" in text else [],
            allergies=["需要核对药物过敏史"],
            missing_fields=["药物名称", "过敏史核对", "是否出现皮疹、头晕或意识异常"],
            visit_summary=(
                "记录包含可能需要立即处理的危险信号。系统不判断病情严重程度，"
                "应立即联系急救或就近急诊，并携带相关药物包装和原始记录。"
            ),
            unsupported_claims=0,
            forbidden_advice=1,
        )

    if _contains_any(text, ["加倍", "两片", "补回来", "剂量", "能不能多吃"]):
        return StructuringResponse(
            report_type="安全请求",
            safety=SafetyState.refused,
            symptoms=["血压记录或用药问题"] if "血压" in text else [],
            medications=["药名和规格需要核对"] if "药" in text else [],
            allergies=[],
            missing_fields=["原始医嘱", "药物规格", "连续症状或血压记录"],
            visit_summary=(
                "这条记录涉及用药剂量调整。系统不提供具体加量、减量或补服建议。"
                "建议按原医嘱或药品说明处理，并联系医生或药师确认。"
            ),
            unsupported_claims=0,
            forbidden_advice=1,
        )

    if payload.input_mode == "blood_pressure" or "血压" in text:
        return StructuringResponse(
            report_type="血压记录",
            safety=SafetyState.passed,
            symptoms=[term for term in ["头晕", "胸痛", "气短", "睡得少"] if term in text],
            medications=[term for term in ["降压药", "氯沙坦"] if term in text],
            allergies=[],
            missing_fields=["测量姿势", "是否重复测量", "晚间复测值"],
            visit_summary=(
                "已整理为家庭血压记录。该摘要用于趋势整理和复诊准备，"
                "不从单次读数判断病情严重程度。"
            ),
            unsupported_claims=0,
            forbidden_advice=0,
        )

    if payload.input_mode == "ocr":
        return StructuringResponse(
            report_type="体检/化验单 OCR",
            safety=SafetyState.passed,
            symptoms=[],
            medications=[],
            allergies=[],
            missing_fields=["报告日期", "异常项目参考范围", "检查机构"],
            visit_summary=(
                "已按 OCR 文本整理为可复核的检查记录。数值和单位需要和原始报告逐项核对后再保存。"
            ),
            unsupported_claims=0,
            forbidden_advice=0,
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


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


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


"""

# Compatibility entrypoint: the durable API lives in memory_api.py. Keeping this
# module path avoids breaking existing uvicorn commands while the legacy demo
# definitions above remain available for historical comparison.
from .memory_api import create_app, default_database_path  # noqa: E402

app = create_app()
