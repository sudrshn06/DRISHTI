"""Regression coverage for deterministic inspection reproducibility."""

from copy import deepcopy
from datetime import date
from io import BytesIO

import cv2
import numpy as np
from fastapi import UploadFile

from app.schemas.compliance import LegalStatus
from app.schemas.inspection import CaptureRecord, InspectionSession
from app.schemas.ocr import (
    BusinessNormalized,
    FieldCandidate,
    MrpNormalized,
    OcrLine,
)
from app.schemas.reproducibility import CaptureProcessingProvenance
from app.repositories.inspection_repository import InspectionRepository
from app.services.candidate_extractor import extract_candidates
from app.services.compliance_service import orchestrate_compliance
from app.services.inspection_service import aggregate_candidates
from app.services.image_validator import validate_and_decode_image
from app.services.ocr_engine import canonicalize_ocr_lines
from app.services.officer_review_service import rebuild_authoritative_candidates
from app.services.reproducibility_service import build_reproducibility_record
from app.api.routes.inspections import _update_session_compliance


def _semantic_candidates(candidates: list[FieldCandidate]) -> list[dict]:
    return [
        candidate.model_dump(
            mode="json",
            exclude={"capture_ids", "evidence_ids", "confidence", "provider_evidence"},
        )
        for candidate in candidates
    ]


def _line(text: str, y: float) -> OcrLine:
    return OcrLine(
        text=text,
        confidence=0.95,
        polygon=[[10, y], [300, y], [300, y + 20], [10, y + 20]],
    )


def test_same_ocr_observations_normalize_identically_regardless_provider_order():
    observations = [_line("MRP Rs 125", 20), _line("Net Qty 500 g", 60)]

    first = canonicalize_ocr_lines(observations)
    second = canonicalize_ocr_lines(list(reversed(observations)))
    first_candidates = extract_candidates(first, {})
    second_candidates = extract_candidates(second, {})

    assert _semantic_candidates(first_candidates) == _semantic_candidates(second_candidates)


def test_same_uploaded_image_bytes_and_context_produce_same_hash_and_normalized_declarations():
    encoded_ok, encoded = cv2.imencode(".png", np.zeros((24, 32, 3), dtype=np.uint8))
    assert encoded_ok
    image_bytes = encoded.tobytes()
    first_image, first_hash = validate_and_decode_image(
        UploadFile(filename="capture.png", file=BytesIO(image_bytes))
    )
    second_image, second_hash = validate_and_decode_image(
        UploadFile(filename="capture.png", file=BytesIO(image_bytes))
    )
    observations = [_line("MRP Rs 125", 20), _line("Net Qty 500 g", 60)]

    first_candidates = extract_candidates(canonicalize_ocr_lines(observations), {})
    second_candidates = extract_candidates(canonicalize_ocr_lines(list(reversed(observations))), {})

    assert np.array_equal(first_image, second_image)
    assert first_hash == second_hash
    assert _semantic_candidates(first_candidates) == _semantic_candidates(second_candidates)


def _business_capture(capture_id: str, view_id: str, *, name=None, address=None, raw: str):
    return CaptureRecord(
        capture_id=capture_id,
        view_id=view_id,
        image_sha256=("a" if view_id == "FRONT" else "b") * 64,
        field_candidates=[FieldCandidate(
            field="MANUFACTURER_PACKER_IMPORTER",
            status="DETECTED",
            raw_value=raw,
            normalized_value=BusinessNormalized(
                role="MARKETER",
                name=name,
                address=address,
                raw_text=raw,
            ),
        )],
    )


def test_random_capture_ids_and_input_order_do_not_change_aggregated_declarations():
    first_session = [
        _business_capture("z-random", "FRONT", name="Example Foods Ltd", raw="Marketed by Example Foods Ltd"),
        _business_capture("a-random", "BACK", address="Example Industrial Area", raw="Example Industrial Area"),
    ]
    second_session = [
        _business_capture("a-other", "FRONT", name="Example Foods Ltd", raw="Marketed by Example Foods Ltd"),
        _business_capture("z-other", "BACK", address="Example Industrial Area", raw="Example Industrial Area"),
    ]

    first = aggregate_candidates(first_session)
    second = aggregate_candidates(list(reversed(second_session)))

    assert _semantic_candidates(first) == _semantic_candidates(second)


def test_repeated_aggregation_is_idempotent_and_does_not_mutate_capture_candidates():
    captures = [
        _business_capture("capture-1", "FRONT", name="Example Foods Ltd", raw="Marketed by Example Foods Ltd"),
        _business_capture("capture-2", "BACK", address="Example Industrial Area", raw="Example Industrial Area"),
    ]
    original = deepcopy(captures)

    first = aggregate_candidates(captures)
    second = aggregate_candidates(captures)

    assert captures == original
    assert _semantic_candidates(first) == _semantic_candidates(second)


def test_gemini_variation_cannot_replace_the_deterministic_legal_candidate():
    deterministic = FieldCandidate(field="MRP", status="NOT_DETECTED")
    gemini_promoted = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs 125",
        normalized_value=MrpNormalized(currency="INR", amount=125),
        observation_layer="RECONCILED",
        extraction_method="HYBRID_RECONCILIATION",
        observation_sources=["GOOGLE_GEMINI"],
        reconciliation_reason="GEMINI_EXPLICIT_EVIDENCE",
        provider_evidence=[{
            "provider": "GOOGLE_GEMINI",
            "raw_text": "MRP Rs 125",
            "normalized_value": {"currency": "INR", "amount": 125},
            "evidence_note": "Visible declaration",
        }],
    )
    session = InspectionSession(
        inspection_id="inspection-reproducibility",
        reference_date="2026-08-24",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        captures=[CaptureRecord(
            capture_id="capture-random",
            view_id="FRONT",
            image_sha256="c" * 64,
            field_candidates=[gemini_promoted],
            deterministic_field_candidates=[deterministic],
        )],
    )

    rebuild_authoritative_candidates(session)

    # The hybrid observation remains visible for officer review.
    assert len(session.aggregated_candidates) == 1
    assert session.aggregated_candidates[0].field == "MRP"
    assert session.aggregated_candidates[0].status == "DETECTED"
    # It cannot replace the persisted OCR input at the legal boundary.
    assert session.deterministic_aggregated_candidates is not None
    assert session.deterministic_aggregated_candidates[0].field == "MRP"
    assert session.deterministic_aggregated_candidates[0].status == "NOT_DETECTED"
    session.product_origin = "DOMESTIC"
    session.regulatory_product_class = "NON_FOOD"
    session.is_electronic = "NON_ELECTRONIC"
    session.package_structure = "SINGLE"
    session.alcohol_context = "NON_ALCOHOLIC"
    session.date_regulatory_regime = "GENERAL"
    session.date_package_exemption = "NONE"
    session.evidence_sufficiency = "SUFFICIENT_FOR_ABSENCE_EVALUATION"
    session.capture_status = "COMPLETE_EVIDENCE_CAPTURE"

    _update_session_compliance(session)

    mrp_result = next(item for item in session.rule_evaluations if item.field == "MRP")
    assert mrp_result.status == LegalStatus.FAIL
    assert session.reproducibility is not None

    provider_failed = session.model_copy(deep=True)
    provider_failed.inspection_id = "inspection-provider-failed"
    provider_failed.captures[0].capture_id = "different-random-capture"
    provider_failed.captures[0].field_candidates = [deterministic]
    provider_failed.aggregated_candidates = []
    provider_failed.deterministic_aggregated_candidates = None
    provider_failed.rule_evaluations = None
    provider_failed.reproducibility = None
    rebuild_authoritative_candidates(provider_failed)
    _update_session_compliance(provider_failed)

    assert [(item.rule_id, item.status) for item in provider_failed.rule_evaluations] == [
        (item.rule_id, item.status) for item in session.rule_evaluations
    ]
    assert provider_failed.reproducibility.result_fingerprint == session.reproducibility.result_fingerprint


def test_same_deterministic_inputs_repeat_identical_rule_statuses_and_fingerprint():
    candidate = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs 125",
        normalized_value=MrpNormalized(currency="INR", amount=125),
    )
    kwargs = dict(
        candidates=[candidate],
        reference_date=date(2026, 8, 24),
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin="DOMESTIC",
        regulatory_category="NON_FOOD",
        is_electronic="NON_ELECTRONIC",
        package_structure="SINGLE",
        alcohol_context="NON_ALCOHOLIC",
        date_regulatory_regime="GENERAL",
        date_package_exemption="NONE",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        inspection_complete=True,
    )
    first_results = orchestrate_compliance(**kwargs)
    second_results = orchestrate_compliance(**kwargs)
    assert [(item.rule_id, item.status) for item in first_results] == [
        (item.rule_id, item.status) for item in second_results
    ]
    assert any(item.status == LegalStatus.PASS for item in first_results)

    def make_session(capture_id: str) -> InspectionSession:
        return InspectionSession(
            inspection_id=f"inspection-{capture_id}",
            reference_date="2026-08-24",
            product_category="GENERIC_RETAIL_PACKAGE",
            product_origin="DOMESTIC",
            regulatory_product_class="NON_FOOD",
            date_regulatory_regime="GENERAL",
            date_package_exemption="NONE",
            is_electronic="NON_ELECTRONIC",
            package_structure="SINGLE",
            alcohol_context="NON_ALCOHOLIC",
            capture_plan_id="plan_software_1",
            captures=[CaptureRecord(
                capture_id=capture_id,
                view_id="FRONT",
                image_sha256="d" * 64,
                field_candidates=[candidate],
                deterministic_field_candidates=[candidate],
            )],
            aggregated_candidates=[candidate],
            rule_evaluations=first_results,
        )

    first_record = build_reproducibility_record(make_session("random-one"))
    second_record = build_reproducibility_record(make_session("random-two"))

    assert first_record.result_fingerprint == second_record.result_fingerprint
    assert first_record.captures[0].image_sha256 == "d" * 64
    assert first_record.ruleset_identifier
    assert first_record.confirmed_package_context["product_origin"] == "DOMESTIC"

    changed_context = make_session("random-three")
    changed_context.product_origin = "IMPORTED"
    changed_record = build_reproducibility_record(changed_context)
    assert changed_record.result_fingerprint != first_record.result_fingerprint


def test_deterministic_capture_inputs_and_processing_versions_round_trip_in_existing_json_column():
    deterministic = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs 125",
        normalized_value=MrpNormalized(currency="INR", amount=125),
    )
    capture = CaptureRecord(
        capture_id="capture-round-trip",
        view_id="BACK",
        image_sha256="e" * 64,
        field_candidates=[deterministic],
        deterministic_field_candidates=[deterministic],
        processing_provenance=CaptureProcessingProvenance(
            ocr_engine="PADDLEOCR",
            ocr_engine_version="test-version",
            preprocessing_config_id="test-preprocessing-config",
        ),
    )

    stored = InspectionRepository._capture_record_to_model("inspection-round-trip", capture)
    assert isinstance(stored.field_candidates, dict)
    restored = InspectionRepository.capture_model_to_domain(stored)

    assert restored.image_sha256 == capture.image_sha256
    assert restored.view_id == "BACK"
    assert restored.deterministic_field_candidates == [deterministic]
    assert restored.processing_provenance == capture.processing_provenance
