from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.health_memory import HealthMemoryStore, StoreConflict, StoreNotFound
from src.health_memory.store import digest_payload
from src.health_memory.security_gate import (
    parse_real_data_mode,
    real_data_gate,
    require_real_data_disabled,
)
from src.inference import (
    ProviderError,
    ProviderOutputError,
    ProviderUnavailable,
    StructuringProvider,
    build_provider_from_env,
    outbound_network_guard,
)

from .api_schemas import (
    ApprovalRequest,
    CaptureActionRequest,
    CandidateEditRequest,
    FamilyMember,
    FamilyMemberInput,
    IngestionRequest,
    ModelEvidenceResponse,
    ProductLineageResponse,
    RecordEditRequest,
    StructuringRequest,
    StructuringResponse,
    UndoRequest,
)
from .evidence import model_evidence


ROOT = Path(__file__).resolve().parents[2]


def default_database_path() -> Path:
    explicit_path = os.environ.get("COVAL_HEALTH_DB_PATH")
    if explicit_path:
        return Path(explicit_path)
    data_dir = os.environ.get("COVAL_DATA_DIR")
    if data_dir:
        return Path(data_dir) / "coval_health.sqlite"
    return ROOT / "data" / "local" / "coval_health.sqlite"


def create_app(
    database_path: Path | None = None,
    seed_demo: bool = True,
    provider: StructuringProvider | None = None,
) -> FastAPI:
    network_guard_enabled = os.environ.get("COVAL_BLOCK_NON_LOOPBACK", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    real_data_requested = parse_real_data_mode(os.environ.get("COVAL_REAL_DATA_MODE"))
    require_real_data_disabled(real_data_requested)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if network_guard_enabled:
            with outbound_network_guard(allow_loopback=True):
                yield
        else:
            yield

    app = FastAPI(
        title="Coval HeYi API",
        version="0.3.0",
        description="Local-first synthetic family health memory API.",
        lifespan=lifespan,
    )
    app.state.store = HealthMemoryStore(database_path or default_database_path(), seed_demo=seed_demo)
    app.state.provider = provider or build_provider_from_env()
    default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
    configured_origins = [
        origin.strip()
        for origin in os.environ.get("COVAL_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[*default_origins, *configured_origins],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    @app.exception_handler(StoreNotFound)
    async def not_found_handler(_request: Request, error: StoreNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"code": "not_found", "detail": str(error)})

    @app.exception_handler(StoreConflict)
    async def conflict_handler(_request: Request, error: StoreConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"code": error.code, "detail": str(error)})

    @app.exception_handler(ProviderUnavailable)
    async def provider_unavailable_handler(
        _request: Request, error: ProviderUnavailable
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"code": error.code, "detail": str(error)})

    @app.exception_handler(ProviderOutputError)
    async def provider_output_handler(
        _request: Request, error: ProviderOutputError
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"code": error.code, "detail": str(error)})

    @app.exception_handler(ProviderError)
    async def provider_error_handler(_request: Request, error: ProviderError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"code": error.code, "detail": str(error)})

    @app.get("/health")
    def health(request: Request) -> dict[str, Any]:
        database = _store(request).health()
        provider_status = _provider(request).describe()
        return {
            "api": "ok",
            "api_version": app.version,
            "database": database,
            "persistence": "sqlite_file",
            "llm_service": provider_status.provider,
            "model": provider_status.model_ref,
            "model_runtime": {
                **provider_status.public_dict(),
                "network_guard": network_guard_enabled,
            },
            "ocr_service": "stub",
            "asr_service": "stub",
            "privacy": "synthetic_demo_only",
            "real_data_gate": real_data_gate(),
        }

    @app.get("/product-lineage", response_model=ProductLineageResponse)
    def product_lineage() -> ProductLineageResponse:
        return ProductLineageResponse(
            origin="Coval AI memo 的长期记忆思路，延伸到家庭健康记录、复诊准备和安全边界。",
            workflow=[
                "capture_source", "lease_processing", "recover_or_reject", "review",
                "approve", "version", "timeline", "undo"
            ],
            current_scope=[
                "migration-backed local SQLite health memory over synthetic examples",
                "immutable source evidence and append-only record versions",
                "capture-first provider failure recovery with expiring leases",
                "explicit mock, Transformers adapter, and llama.cpp provider boundary",
                "evaluation evidence for the separate Qwen2.5-7B LoRA research path",
            ],
            not_claimed=[
                "not a diagnostic or medication-advice system",
                "OCR/ASR remain stubs; local 7B is claimed only when the active provider is measured",
                "not a production RAG agent",
                "not trained on real family data",
                "real-data mode remains fail-closed pending the documented security gate",
            ],
        )

    @app.get("/model-evidence", response_model=ModelEvidenceResponse)
    def get_model_evidence() -> ModelEvidenceResponse:
        return model_evidence()

    @app.get("/family-members", response_model=list[FamilyMember])
    def list_family_members(request: Request) -> list[dict[str, Any]]:
        return _store(request).list_members()

    @app.post("/family-members", response_model=FamilyMember, status_code=201)
    def create_family_member(payload: FamilyMemberInput, request: Request) -> dict[str, Any]:
        return _store(request).create_member(payload.model_dump())

    @app.put("/family-members/{member_id}", response_model=FamilyMember)
    def update_family_member(
        member_id: str, payload: FamilyMemberInput, request: Request
    ) -> dict[str, Any]:
        values = payload.model_dump()
        values["id"] = member_id
        return _store(request).update_member(member_id, values)

    @app.delete("/family-members/{member_id}", status_code=204)
    def delete_family_member(member_id: str, request: Request) -> None:
        _store(request).delete_member(member_id)

    @app.post("/structure", response_model=StructuringResponse)
    def structure(payload: StructuringRequest, request: Request) -> StructuringResponse:
        _store(request).get_member(payload.member_id)
        return _provider(request).structure(payload).response

    def process_capture(
        *,
        capture: dict[str, Any],
        request: Request,
        idempotency_key: str,
        request_digest: str,
    ) -> dict[str, Any] | JSONResponse:
        store = _store(request)
        member_id = str(capture["member_id"])
        source = capture["source"]
        if capture["state"] == "rejected":
            raise StoreConflict("Capture was rejected", "capture_rejected")
        if capture.get("record_id"):
            return store.get_record(str(capture["record_id"]), member_id)
        claimed = store.claim_capture(str(capture["source_artifact_id"]), member_id)
        if not claimed["claimed"]:
            if claimed.get("record_id"):
                return store.get_record(str(claimed["record_id"]), member_id)
            if claimed["state"] in {"rejected", "completed", "needs_review"}:
                raise StoreConflict(
                    f"Capture cannot be processed from state {claimed['state']}",
                    "capture_not_retryable",
                )
            return JSONResponse(status_code=202, content={"capture": claimed})

        lease_token = str(claimed["lease_token"])
        structuring_payload = StructuringRequest(
            member_id=member_id,
            text=str(source["original_text"]),
            input_mode=str(source["kind"]),
            event_date=source["event_date"],
        )
        try:
            provider_result = _provider(request).structure(structuring_payload)
            structured = provider_result.response
            inference = structured.inference
            if inference is None:
                raise ProviderOutputError("active provider omitted inference provenance")
        except ProviderError as error:
            failed = store.mark_capture_failed(
                str(capture["source_artifact_id"]), member_id, lease_token, error.code
            )
            return JSONResponse(
                status_code=202,
                content={
                    "capture": failed,
                    "error": {
                        "code": error.code,
                        "message": "原文已保存，本地模型暂时无法完成整理；可稍后重试或拒绝。",
                    },
                },
            )

        return store.ingest_candidate(
            member_id=member_id,
            artifact_kind=str(source["kind"]),
            source_label=str(source["label"]),
            original_text=str(source["original_text"]),
            declared_event_date=source["event_date"],
            candidate=structured.candidate.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            provider=inference.provider,
            model_ref=(
                f"{inference.model_ref} + {inference.adapter_ref} [{inference.quantization}]"
                if inference.adapter_ref
                else f"{inference.model_ref} [{inference.quantization}]"
            ),
            extraction_version=inference.extraction_version,
            prompt_version=inference.prompt_version,
            contract_version=inference.contract_version,
            source_artifact_id=str(capture["source_artifact_id"]),
            lease_token=lease_token,
        )

    @app.post("/ingestions", status_code=201, response_model=None)
    def ingest(payload: IngestionRequest, request: Request) -> dict[str, Any] | JSONResponse:
        store = _store(request)
        store.get_member(payload.member_id)
        values = payload.model_dump(mode="json")
        request_digest = digest_payload(values)
        existing = store.find_idempotent_ingestion(
            member_id=payload.member_id,
            idempotency_key=payload.idempotency_key,
            request_digest=request_digest,
        )
        if existing is not None:
            return existing
        capture = store.capture_source(
            member_id=payload.member_id,
            artifact_kind=payload.input_mode,
            source_label=payload.source_label,
            original_text=payload.text,
            declared_event_date=values["event_date"],
            idempotency_key=payload.idempotency_key,
            request_digest=request_digest,
        )
        return process_capture(
            capture=capture,
            request=request,
            idempotency_key=payload.idempotency_key,
            request_digest=request_digest,
        )

    @app.get("/ingestions")
    def list_ingestions(
        request: Request,
        member_id: str = Query(min_length=1, max_length=64),
        state: str | None = Query(default=None, max_length=40),
    ) -> list[dict[str, Any]]:
        return _store(request).list_captures(member_id, state)

    @app.get("/ingestions/{source_artifact_id}")
    def get_ingestion(
        source_artifact_id: str,
        request: Request,
        member_id: str = Query(min_length=1, max_length=64),
    ) -> dict[str, Any]:
        return _store(request).get_capture(source_artifact_id, member_id)

    @app.post("/ingestions/{source_artifact_id}/retry", response_model=None)
    def retry_ingestion(
        source_artifact_id: str,
        payload: CaptureActionRequest,
        request: Request,
    ) -> dict[str, Any] | JSONResponse:
        capture = _store(request).get_capture(source_artifact_id, payload.member_id)
        if capture["state"] in {"needs_review", "completed", "rejected"}:
            raise StoreConflict(
                f"Capture cannot be retried from state {capture['state']}",
                "capture_not_retryable",
            )
        return process_capture(
            capture=capture,
            request=request,
            idempotency_key=f"capture-process-{source_artifact_id}",
            request_digest=digest_payload({"source_artifact_id": source_artifact_id}),
        )

    @app.post("/ingestions/{source_artifact_id}/reject")
    def reject_ingestion(
        source_artifact_id: str,
        payload: CaptureActionRequest,
        request: Request,
    ) -> dict[str, Any]:
        return _store(request).reject_capture(
            source_artifact_id, payload.member_id, actor=payload.actor
        )

    @app.get("/records/{record_id}")
    def get_record(
        record_id: str,
        request: Request,
        member_id: str = Query(min_length=1, max_length=64),
    ) -> dict[str, Any]:
        return _store(request).get_record(record_id, member_id)

    @app.patch("/records/{record_id}/candidate")
    def edit_candidate(
        record_id: str, payload: CandidateEditRequest, request: Request
    ) -> dict[str, Any]:
        values = payload.model_dump(mode="json")
        return _store(request).edit_candidate(
            record_id=record_id,
            member_id=payload.member_id,
            base_candidate_id=payload.base_candidate_id,
            base_candidate_revision=payload.base_candidate_revision,
            candidate=values["candidate"],
            actor=payload.actor,
            idempotency_key=payload.idempotency_key,
            request_digest=digest_payload(values),
        )

    @app.post("/records/{record_id}/approve")
    def approve_record(
        record_id: str, payload: ApprovalRequest, request: Request
    ) -> dict[str, Any]:
        values = payload.model_dump(mode="json")
        return _store(request).approve_candidate(
            record_id=record_id,
            member_id=payload.member_id,
            candidate_id=payload.candidate_id,
            candidate_revision=payload.candidate_revision,
            actor=payload.actor,
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
            request_digest=digest_payload(values),
        )

    @app.patch("/records/{record_id}")
    def edit_record(
        record_id: str, payload: RecordEditRequest, request: Request
    ) -> dict[str, Any]:
        values = payload.model_dump(mode="json")
        return _store(request).edit_record(
            record_id=record_id,
            member_id=payload.member_id,
            base_version_id=payload.base_version_id,
            snapshot=values["record"],
            actor=payload.actor,
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
            request_digest=digest_payload(values),
        )

    @app.post("/records/{record_id}/undo")
    def undo_record(
        record_id: str, payload: UndoRequest, request: Request
    ) -> dict[str, Any]:
        values = payload.model_dump(mode="json")
        return _store(request).undo_record(
            record_id=record_id,
            member_id=payload.member_id,
            base_version_id=payload.base_version_id,
            target_version_id=payload.target_version_id,
            actor=payload.actor,
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
            request_digest=digest_payload(values),
        )

    @app.get("/records/{record_id}/versions")
    def list_versions(
        record_id: str,
        request: Request,
        member_id: str = Query(min_length=1, max_length=64),
    ) -> list[dict[str, Any]]:
        return _store(request).list_versions(record_id, member_id)

    @app.get("/records/{record_id}/audit")
    def list_audit(
        record_id: str,
        request: Request,
        member_id: str = Query(min_length=1, max_length=64),
    ) -> list[dict[str, Any]]:
        return _store(request).list_audit_events(record_id, member_id)

    @app.get("/timeline")
    def timeline(
        request: Request,
        member_id: str = Query(min_length=1, max_length=64),
    ) -> list[dict[str, Any]]:
        return _store(request).list_timeline(member_id)

    return app


def _store(request: Request) -> HealthMemoryStore:
    store = request.app.state.store
    if not isinstance(store, HealthMemoryStore):
        raise HTTPException(status_code=503, detail="Health memory store is unavailable")
    return store


def _provider(request: Request) -> StructuringProvider:
    provider = request.app.state.provider
    if not hasattr(provider, "describe") or not hasattr(provider, "structure"):
        raise HTTPException(status_code=503, detail="Structuring provider is unavailable")
    return provider
