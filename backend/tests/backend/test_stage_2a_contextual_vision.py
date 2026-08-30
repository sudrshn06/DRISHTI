"""Focused Stage 2A safety contract for optional contextual vision."""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.schemas.gemini import (
    GeminiAnalysisStatus,
    GeminiModelPayload,
    StructuredDeclarationObservations,
)
from app.schemas.inspection import CaptureRecord
from app.schemas.ocr import FieldCandidate, MrpNormalized
from app.services.compliance_service import orchestrate_compliance
from app.services.contextual_vision_provider import ContextualVisionProvider
from app.services.contextual_vision_service import ContextualVisionService
from app.services.gemini_package_reader import (
    GeminiPackageReader,
    _gemini_response_schema,
    build_gemini_prompt,
)
from app.services.inspection_service import aggregate_candidates


def _payload(*, uncertain: bool = False) -> dict:
    return {
        "raw_visible_text": [{"visible_text": ["MRP Rs 60"]}],
        "context_suggestions": [],
        "declarations": {
            "mrp": {
                "raw_text": "MRP Rs 60 inclusive of all taxes",
                "confidence": 0.84,
                "uncertain": uncertain,
                "contradiction": False,
                "evidence_note": "Printed price adjacent to the MRP label",
                "amount": 60,
                "currency": "INR",
            }
        },
        "uncertainty_flags": ["price partly obscured"] if uncertain else [],
        "contradiction_flags": [],
    }


def _gemini_response(payload: dict) -> dict:
    return {
        "responseId": "mock-response",
        "candidates": [{
            "finishReason": "STOP",
            "content": {"parts": [{"text": json.dumps(payload)}]},
        }],
    }


def _paddle_capture() -> CaptureRecord:
    return CaptureRecord(
        capture_id="capture-paddle",
        view_id="FRONT",
        field_candidates=[FieldCandidate(
            field="MRP",
            status="DETECTED",
            raw_value="MRP Rs 50",
            normalized_value=MrpNormalized(currency="INR", amount=50),
            evidence_ids=["ocr-line-1"],
        )],
    )


def test_gemini_reader_implements_contextual_provider_boundary():
    assert isinstance(GeminiPackageReader(enabled=False), ContextualVisionProvider)


def test_gemini_facing_schema_is_shallow_while_local_model_stays_strict():
    schema = _gemini_response_schema()
    serialized = json.dumps(schema)

    assert "$defs" not in serialized
    assert "$ref" not in serialized
    assert "anyOf" not in serialized
    assert "oneOf" not in serialized
    assert "additionalProperties" not in serialized
    assert set(schema["properties"]["declarations"]["properties"]) == {
        *StructuredDeclarationObservations.model_fields,
    }

    invalid = _payload()
    invalid["legal_status"] = "PASS"
    with pytest.raises(ValidationError):
        GeminiModelPayload.model_validate(invalid)


@pytest.mark.asyncio
async def test_disabled_provider_never_calls_network_and_paddle_path_is_unchanged():
    async def forbidden_request(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("disabled provider attempted a request")

    client = httpx.AsyncClient(transport=httpx.MockTransport(forbidden_request))
    try:
        result = await GeminiPackageReader(enabled=False, api_key="not-used", client=client).analyze_package(
            image_bytes=b"image", media_type="image/jpeg", view_id="FRONT"
        )
    finally:
        await client.aclose()

    assert result.status == GeminiAnalysisStatus.DISABLED
    assert aggregate_candidates([_paddle_capture()])[0].normalized_value.amount == 50


@pytest.mark.asyncio
async def test_enabled_without_key_starts_and_never_calls_network():
    async def forbidden_request(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("missing-key provider attempted a request")

    client = httpx.AsyncClient(transport=httpx.MockTransport(forbidden_request))
    try:
        result = await GeminiPackageReader(enabled=True, api_key="", client=client).analyze_package(
            image_bytes=b"image", media_type="image/jpeg", view_id="FRONT"
        )
    finally:
        await client.aclose()

    assert result.status == GeminiAnalysisStatus.DISABLED
    assert result.metadata.failure_code == "MISSING_API_KEY"


@pytest.mark.asyncio
async def test_valid_structured_candidate_is_accepted_with_server_provenance():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_gemini_response(_payload()))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await GeminiPackageReader(
            enabled=True, api_key="mock-key", model="mock-model", client=client
        ).analyze_package(
            image_bytes=b"image", media_type="image/jpeg", view_id="BACK", capture_id="capture-7"
        )
    finally:
        await client.aclose()

    assert result.status == GeminiAnalysisStatus.SUCCEEDED
    assert result.declarations.mrp.amount == 60
    assert result.declarations.mrp.capture_id == "capture-7"
    assert result.declarations.mrp.view_id == "BACK"


@pytest.mark.asyncio
async def test_malformed_json_is_rejected_safely():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_gemini_response("not-json"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await GeminiPackageReader(enabled=True, api_key="mock-key", client=client).analyze_package(
            image_bytes=b"image", media_type="image/png", view_id="FRONT"
        )
    finally:
        await client.aclose()

    assert result.status == GeminiAnalysisStatus.INVALID_RESPONSE
    assert result.declarations == StructuredDeclarationObservations()


@pytest.mark.asyncio
async def test_timeout_falls_back_without_observations():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("mock timeout", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await GeminiPackageReader(enabled=True, api_key="mock-key", client=client).analyze_package(
            image_bytes=b"image", media_type="image/jpeg", view_id="FRONT"
        )
    finally:
        await client.aclose()

    assert result.status == GeminiAnalysisStatus.TIMEOUT
    assert result.context_suggestions == []


@pytest.mark.asyncio
async def test_unexpected_provider_exception_falls_back_without_raising():
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise RuntimeError("mock provider failure")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await GeminiPackageReader(enabled=True, api_key="mock-key", client=client).analyze_package(
            image_bytes=b"image", media_type="image/jpeg", view_id="FRONT"
        )
    finally:
        await client.aclose()

    assert result.status == GeminiAnalysisStatus.FAILED
    assert result.metadata.failure_code == "UNEXPECTED_FAILURE"


@pytest.mark.asyncio
async def test_invalid_schema_falls_back_without_partial_candidate():
    invalid = _payload()
    invalid["declarations"]["mrp"]["legal_status"] = "PASS"

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_gemini_response(invalid))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await GeminiPackageReader(enabled=True, api_key="mock-key", client=client).analyze_package(
            image_bytes=b"image", media_type="image/jpeg", view_id="FRONT"
        )
    finally:
        await client.aclose()

    assert result.status == GeminiAnalysisStatus.INVALID_RESPONSE
    assert result.declarations.mrp is None


@pytest.mark.asyncio
async def test_uncertainty_is_preserved_without_confirmation():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_gemini_response(_payload(uncertain=True)))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await GeminiPackageReader(enabled=True, api_key="mock-key", client=client).analyze_package(
            image_bytes=b"image", media_type="image/jpeg", view_id="FRONT"
        )
    finally:
        await client.aclose()

    assert result.declarations.mrp.uncertain is True
    assert result.declarations.mrp.review_state == "OBSERVED"
    assert result.uncertainty_flags == ["price partly obscured"]


@pytest.mark.parametrize(
    "forbidden_field",
    ["compliant", "non_compliant", "violation", "legal_status", "final_result", "pass", "fail"],
)
def test_candidate_schema_cannot_represent_authoritative_verdict_fields(forbidden_field):
    payload = _payload()
    payload[forbidden_field] = True
    with pytest.raises(ValidationError):
        GeminiModelPayload.model_validate(payload)


def test_deterministic_engine_ignores_disagreeing_contextual_observation():
    candidates = aggregate_candidates([_paddle_capture()])
    results = orchestrate_compliance(
        candidates=candidates,
        reference_date=date(2026, 8, 29),
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin="DOMESTIC",
        regulatory_category="NON_FOOD",
        is_electronic="NON_ELECTRONIC",
        package_structure="SINGLE",
        alcohol_context="NON_ALCOHOLIC",
        date_regulatory_regime="GENERAL",
        date_package_exemption="NONE",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        inspection_complete=False,
    )

    assert candidates[0].normalized_value.amount == 50
    assert all(result.status in {"PASS", "FAIL", "REVIEW_REQUIRED", "NOT_APPLICABLE"} for result in results)


@pytest.mark.asyncio
async def test_contextual_service_creates_isolated_append_only_audit_envelope():
    service = ContextualVisionService(GeminiPackageReader(enabled=False, model="mock-model"))
    audit = await service.analyze_capture(
        inspection_id="inspection-1",
        capture_id="capture-1",
        view_id="FRONT",
        image_sha256="a" * 64,
        image_bytes=b"image",
        media_type="image/jpeg",
    )

    assert audit.append_only is True
    assert audit.capture_evidence[0].image_sha256 == "a" * 64
    assert audit.analysis.status == GeminiAnalysisStatus.DISABLED


@pytest.mark.asyncio
async def test_secret_is_absent_from_logs_results_and_persisted_audit(caplog):
    secret = "stage2a-secret-sentinel"

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "mock failure"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        service = ContextualVisionService(
            GeminiPackageReader(enabled=True, api_key=secret, model="mock-model", client=client)
        )
        audit = await service.analyze_capture(
            inspection_id="inspection-1",
            capture_id="capture-1",
            view_id="FRONT",
            image_sha256="b" * 64,
            image_bytes=b"image",
            media_type="image/jpeg",
        )
    finally:
        await client.aclose()

    serialized = audit.model_dump_json()
    assert secret not in serialized
    assert secret not in caplog.text
    assert "api_key" not in serialized.lower()


def test_frontend_has_no_gemini_api_key_reference():
    frontend_root = Path(__file__).resolve().parents[3] / "frontend"
    source_extensions = {".ts", ".tsx", ".js", ".jsx", ".json", ".html", ".css"}
    source = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in frontend_root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in source_extensions
        and "node_modules" not in path.parts
        and ".next" not in path.parts
    )
    assert "GEMINI_API_KEY" not in source
    assert "stage2a-secret-sentinel" not in source


def test_prompt_is_product_agnostic_and_forbids_legal_decisions():
    prompt = build_gemini_prompt("SIDE_LEFT").lower()
    assert "never determine compliance" in prompt
    assert "do not guess missing" in prompt
    for product in ("coke", "shampoo", "biscuits", "pureshield"):
        assert product not in prompt


def test_stage_1_5_absence_and_authoritative_candidate_contracts_remain_locked():
    capture = _paddle_capture()
    assert capture.field_candidates[0].extraction_method == "PADDLEOCR"
    assert capture.ai_analysis is None
