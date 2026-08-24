from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SafetyState(str, Enum):
    passed = "passed"
    refused = "refused"
    escalated = "escalated"
    unknown = "unknown"


class FamilyMemberInput(BaseModel):
    id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=80)
    relation: str = Field(min_length=1, max_length=120)
    age: int = Field(ge=0, le=130)
    profile: str = Field(default="", max_length=500)
    badges: list[str] = Field(default_factory=list, max_length=12)


class FamilyMember(FamilyMemberInput):
    id: str


class SourceLocator(BaseModel):
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)


class SymptomFact(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    onset_text: str = Field(default="", max_length=200)
    negated: bool = False
    source_locator: SourceLocator = Field(default_factory=SourceLocator)


class MedicationFact(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    event_type: Literal["reported", "started", "stopped", "missed", "unknown"] = "reported"
    dose_text: str = Field(default="", max_length=200)
    occurred_at: str | None = Field(default=None, max_length=80)
    source_locator: SourceLocator = Field(default_factory=SourceLocator)


class ObservationFact(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=160)
    unit: str = Field(default="", max_length=40)
    observed_at: str | None = Field(default=None, max_length=80)
    source_locator: SourceLocator = Field(default_factory=SourceLocator)


class AppointmentFact(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    scheduled_at: str | None = Field(default=None, max_length=80)
    source_locator: SourceLocator = Field(default_factory=SourceLocator)


class SafetyFact(BaseModel):
    state: SafetyState
    category: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=800)
    unsafe_request_detected: bool = False
    forbidden_advice_generated: Literal[0] = 0


class CanonicalRecord(BaseModel):
    report_type: str = Field(min_length=1, max_length=120)
    event_date: date | None = None
    summary: str = Field(min_length=1, max_length=2000)
    symptoms: list[SymptomFact] = Field(default_factory=list, max_length=100)
    medications: list[MedicationFact] = Field(default_factory=list, max_length=100)
    allergies: list[str] = Field(default_factory=list, max_length=100)
    observations: list[ObservationFact] = Field(default_factory=list, max_length=100)
    appointments: list[AppointmentFact] = Field(default_factory=list, max_length=100)
    missing_fields: list[str] = Field(default_factory=list, max_length=100)
    safety: SafetyFact


class StructuringRequest(BaseModel):
    member_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=8000)
    input_mode: Literal["text", "ocr", "voice", "blood_pressure"] = "text"
    event_date: date | None = None


class InferenceMetadata(BaseModel):
    provider: Literal["mock", "transformers_base", "transformers_adapter", "llama_cpp"]
    model_ref: str = Field(min_length=1, max_length=300)
    adapter_ref: str | None = Field(default=None, max_length=300)
    extraction_version: str = Field(min_length=1, max_length=160)
    prompt_version: str = Field(min_length=1, max_length=80)
    contract_version: str = Field(min_length=1, max_length=80)
    latency_ms: float = Field(ge=0)
    attempts: int = Field(ge=1, le=2)
    offline_only: bool
    quantization: str = Field(default="none", min_length=1, max_length=80)


class StructuringResponse(BaseModel):
    report_type: str
    safety: SafetyState
    symptoms: list[str]
    medications: list[str]
    allergies: list[str]
    missing_fields: list[str]
    visit_summary: str
    unsafe_request_detected: bool
    forbidden_advice_generated: Literal[0] = 0
    candidate: CanonicalRecord
    inference: InferenceMetadata | None = None


class IngestionRequest(StructuringRequest):
    source_label: str = Field(default="家庭合成演示记录", min_length=1, max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=160)


class CaptureActionRequest(BaseModel):
    member_id: str = Field(min_length=1, max_length=64)
    actor: str = Field(default="local_user", min_length=1, max_length=80)


class CandidateEditRequest(BaseModel):
    member_id: str = Field(min_length=1, max_length=64)
    base_candidate_id: str = Field(min_length=1, max_length=64)
    base_candidate_revision: int = Field(ge=1)
    candidate: CanonicalRecord
    actor: str = Field(default="local_user", min_length=1, max_length=80)
    idempotency_key: str = Field(min_length=8, max_length=160)


class ApprovalRequest(BaseModel):
    member_id: str = Field(min_length=1, max_length=64)
    candidate_id: str = Field(min_length=1, max_length=64)
    candidate_revision: int = Field(ge=1)
    actor: str = Field(default="local_user", min_length=1, max_length=80)
    reason: str = Field(default="family_review_confirmed", min_length=1, max_length=300)
    idempotency_key: str = Field(min_length=8, max_length=160)


class RecordEditRequest(BaseModel):
    member_id: str = Field(min_length=1, max_length=64)
    base_version_id: str = Field(min_length=1, max_length=64)
    record: CanonicalRecord
    actor: str = Field(default="local_user", min_length=1, max_length=80)
    reason: str = Field(default="family_field_edit", min_length=1, max_length=300)
    idempotency_key: str = Field(min_length=8, max_length=160)


class UndoRequest(BaseModel):
    member_id: str = Field(min_length=1, max_length=64)
    base_version_id: str = Field(min_length=1, max_length=64)
    target_version_id: str = Field(min_length=1, max_length=64)
    actor: str = Field(default="local_user", min_length=1, max_length=80)
    reason: str = Field(default="family_requested_undo", min_length=1, max_length=300)
    idempotency_key: str = Field(min_length=8, max_length=160)


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
