"""Focused Phase 5 readability, placement, history, and reference regressions."""

from copy import deepcopy
from datetime import date, datetime, timezone
import uuid

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes.inspections import _default_plan, _inspections, _update_session_compliance
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.inspection import CaptureModel, InspectionModel
from app.models.user import UserModel
from app.repositories.inspection_repository import InspectionRepository
from app.schemas.gemini import (
    GeminiAnalysisStatus,
    GeminiAuditMetadata,
    GeminiCaptureEvidenceReference,
    GeminiPackageAnalysis,
    GeminiPackageAuditRecord,
    StructuredDeclarationObservations,
    TextObservation,
)
from app.repositories.user_repository import UserRepository
from app.schemas.inspection import CaptureRecord, InspectionSession
from app.schemas.ocr import BusinessNormalized, FieldCandidate
from app.services.history_reference_service import related_match_basis
from app.services.image_quality import assess_image_quality
from app.services.report_service import generate_inspection_report
from app.services.reproducibility_service import deterministic_candidates_for_capture
from app.services.visual_assessment_service import assess_capture_visuals, evaluate_visual_legal_rules


client = TestClient(app)


LEGACY_GEMINI_ATTEMPT_FIELDS = {
    "primary_attempt_status": "TIMEOUT",
    "primary_attempt_response_id": None,
    "primary_attempt_failure_code": "TIMEOUT",
    "targeted_fallback_status": "SUCCEEDED",
    "targeted_fallback_response_id": "legacy-response",
    "targeted_fallback_failure_code": None,
}


def _gemini_analysis_payload(*, capture_id="stored-capture", view_id="FRONT"):
    return GeminiPackageAnalysis(
        status=GeminiAnalysisStatus.SUCCEEDED,
        declarations=StructuredDeclarationObservations(
            brand_trade_name=TextObservation(
                raw_text="Advisory model brand",
                value="Advisory model brand",
                capture_id=capture_id,
                view_id=view_id,
                confidence=0.99,
                uncertain=False,
                contradiction=False,
                evidence_note="Historical advisory observation",
            )
        ),
        metadata=GeminiAuditMetadata(
            model="historical-model",
            schema_version="2.0",
            prompt_version="2.0",
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
    ).model_dump(mode="json")


def _gemini_audit_payload(*, inspection_id, capture_id, view_id, image_sha256):
    return GeminiPackageAuditRecord(
        audit_id="historical-audit",
        inspection_id=inspection_id,
        capture_evidence=[GeminiCaptureEvidenceReference(
            capture_id=capture_id,
            view_id=view_id,
            image_sha256=image_sha256,
        )],
        analysis=GeminiPackageAnalysis.model_validate(
            _gemini_analysis_payload(capture_id=capture_id, view_id=view_id)
        ),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    ).model_dump(mode="json")


def _capture_model_with_ai(ai_analysis):
    return CaptureModel(
        capture_id="trusted-capture",
        inspection_id="trusted-inspection",
        view_id="BACK",
        evidence_id="trusted-evidence",
        image_sha256="f" * 64,
        media_type="image/jpeg",
        status="ACCEPTED",
        pipeline_status="COMPLETED",
        field_candidates=[],
        ai_analysis=ai_analysis,
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )


def test_current_gemini_audit_shape_still_rehydrates_strictly():
    payload = _gemini_audit_payload(
        inspection_id="trusted-inspection",
        capture_id="trusted-capture",
        view_id="BACK",
        image_sha256="f" * 64,
    )
    capture = InspectionRepository.capture_model_to_domain(
        _capture_model_with_ai(payload)
    )

    assert capture.ai_analysis.audit_id == "historical-audit"
    assert capture.ai_analysis.analysis.metadata.model == "historical-model"


def test_earliest_gemini_analysis_shape_still_rehydrates():
    capture = InspectionRepository.capture_model_to_domain(
        _capture_model_with_ai(_gemini_analysis_payload())
    )

    assert capture.ai_analysis.audit_id == "legacy-trusted-capture"
    assert capture.ai_analysis.inspection_id == "trusted-inspection"
    assert capture.ai_analysis.capture_evidence[0].capture_id == "trusted-capture"


def test_intermediate_gemini_audit_rehydrates_without_mutating_stored_json():
    payload = _gemini_audit_payload(
        inspection_id="untrusted-inspection",
        capture_id="untrusted-capture",
        view_id="SIDE_LEFT",
        image_sha256="0" * 64,
    )
    payload["analysis"]["metadata"].update(LEGACY_GEMINI_ATTEMPT_FIELDS)
    stored_before = deepcopy(payload)

    with pytest.raises(ValidationError) as strict_error:
        GeminiPackageAuditRecord.model_validate(payload)
    assert {
        error["loc"][-1]
        for error in strict_error.value.errors()
        if error["type"] == "extra_forbidden"
    } == set(LEGACY_GEMINI_ATTEMPT_FIELDS)

    capture = InspectionRepository.capture_model_to_domain(
        _capture_model_with_ai(payload)
    )

    assert payload == stored_before
    assert capture.ai_analysis.inspection_id == "trusted-inspection"
    assert capture.ai_analysis.capture_evidence[0].model_dump() == {
        "capture_id": "trusted-capture",
        "view_id": "BACK",
        "image_sha256": "f" * 64,
    }
    assert capture.ai_analysis.analysis.metadata.model == "historical-model"


def test_current_gemini_schema_still_rejects_unknown_metadata_fields():
    payload = _gemini_audit_payload(
        inspection_id="trusted-inspection",
        capture_id="trusted-capture",
        view_id="BACK",
        image_sha256="f" * 64,
    )
    payload["analysis"]["metadata"]["unknown_future_field"] = "not-allowed"

    with pytest.raises(ValidationError):
        InspectionRepository.capture_model_to_domain(
            _capture_model_with_ai(payload)
        )


def test_intermediate_gemini_data_never_becomes_deterministic_legal_input():
    deterministic_candidate = FieldCandidate(
        field="BRAND_NAME",
        status="DETECTED",
        raw_value="Officer-visible OCR brand",
        confidence=0.91,
        evidence_ids=["trusted-evidence"],
    )
    source_capture = CaptureRecord(
        capture_id="trusted-capture",
        view_id="BACK",
        evidence_id="trusted-evidence",
        image_sha256="f" * 64,
        field_candidates=[deterministic_candidate],
        deterministic_field_candidates=[deterministic_candidate],
    )
    model = InspectionRepository._capture_record_to_model(
        "trusted-inspection", source_capture
    )
    payload = _gemini_audit_payload(
        inspection_id="trusted-inspection",
        capture_id="trusted-capture",
        view_id="BACK",
        image_sha256="f" * 64,
    )
    payload["analysis"]["metadata"].update(LEGACY_GEMINI_ATTEMPT_FIELDS)
    model.ai_analysis = payload
    model.created_at = datetime(2026, 2, 1, tzinfo=timezone.utc)

    capture = InspectionRepository.capture_model_to_domain(model)
    legal_inputs = deterministic_candidates_for_capture(capture)

    assert [candidate.raw_value for candidate in legal_inputs] == [
        "Officer-visible OCR brand"
    ]
    assert all(
        candidate.raw_value != "Advisory model brand"
        for candidate in legal_inputs
    )


def _line(text, confidence, x1, y1, x2, y2):
    from app.schemas.ocr import OcrLine
    return OcrLine(
        text=text,
        confidence=confidence,
        polygon=[[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
    )


def test_readability_preserves_quality_metrics_without_creating_legal_failure():
    image = np.full((500, 700, 3), 245, dtype=np.uint8)
    image = cv2.GaussianBlur(image, (51, 51), 0)
    quality = assess_image_quality(image)
    line = _line("Declared value", 0.61, 100, 100, 300, 128)
    candidate = FieldCandidate(
        field="MRP", status="REVIEW_REQUIRED", raw_value=line.text,
        confidence=line.confidence, evidence_ids=["evidence-a"],
    )
    summary = assess_capture_visuals(
        capture_id="capture-a", view_id="FRONT", image_width=700, image_height=500,
        ocr_lines=[line], field_candidates=[candidate], evidence_map={"0": "evidence-a"},
        quality_assessment=quality,
    )
    assessment = summary.assessments[0]
    assert assessment.readability.quality_metrics == {
        "blur_score": quality.blur_score,
        "brightness": quality.brightness,
        "glare_percentage": quality.glare_percentage,
    }
    legal = evaluate_visual_legal_rules(
        [CaptureRecord(
            capture_id="capture-a", view_id="FRONT", quality_assessment=quality,
            visual_assessment=summary, status="RETAKE_RECOMMENDED",
        )],
        [candidate],
        date(2026, 1, 1),
    )
    assert all(item.status != "FAIL" for item in legal)


def test_font_and_placement_keep_measured_evidence_but_require_review():
    lines = [
        _line("Net quantity declaration", 0.96, 80, 90, 280, 120),
        _line("Maximum retail price", 0.94, 360, 180, 610, 214),
    ]
    candidates = [
        FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value=lines[0].text, confidence=0.96, evidence_ids=["ev-q"]),
        FieldCandidate(field="MRP", status="DETECTED", raw_value=lines[1].text, confidence=0.94, evidence_ids=["ev-m"]),
    ]
    summary = assess_capture_visuals(
        capture_id="capture-layout", view_id="BACK", image_width=800, image_height=600,
        ocr_lines=lines, field_candidates=candidates, evidence_map={"0": "ev-q", "1": "ev-m"},
    )
    first = summary.assessments[0]
    assert first.geometry.pixel_box.height_px > 0
    assert first.geometry.normalized_box.y_min >= 0
    assert first.relative_position_in_image == "TOP_LEFT"
    assert first.proximity_to_declarations[0].relative_direction in {"RIGHT", "BELOW"}

    capture = CaptureRecord(
        capture_id="capture-layout", view_id="BACK", visual_assessment=summary,
    )
    legal = {item.rule_id: item for item in evaluate_visual_legal_rules([capture], candidates)}
    assert legal["RULE_7_MINIMUM_NUMERAL_HEIGHT"].status == "REVIEW_REQUIRED"
    assert legal["RULE_7_MINIMUM_NUMERAL_HEIGHT"].metrics["relative_text_measurements"]
    assert legal["RULE_8_PRINCIPAL_DISPLAY_PANEL_PLACEMENT"].status == "REVIEW_REQUIRED"
    assert legal["RULE_8_PRINCIPAL_DISPLAY_PANEL_PLACEMENT"].metrics["measured_image_placement"]
    assert "height_mm" not in str(legal).lower()

    session = InspectionSession(
        inspection_id="measured-report", reference_date="2026-01-01",
        product_category="GENERIC_RETAIL_PACKAGE", capture_plan_id="plan_software_1",
        captures=[capture], aggregated_candidates=candidates, visual_rule_evaluations=list(legal.values()),
    )
    report = generate_inspection_report(session, _default_plan)
    report_rule7 = next(
        item for item in report.visual_compliance_findings
        if item.rule_id == "RULE_7_MINIMUM_NUMERAL_HEIGHT"
    )
    assert report_rule7.metrics["relative_text_measurements"]


def _identity_candidates():
    return [
        FieldCandidate(field="COMMON_GENERIC_NAME", status="DETECTED", raw_value="Orchard crackers"),
        FieldCandidate(field="BRAND_NAME", status="DETECTED", raw_value="Northstar"),
        FieldCandidate(
            field="MANUFACTURER_PACKER_IMPORTER", status="DETECTED",
            normalized_value=BusinessNormalized(
                role="PACKER", name="Meridian Packers", address="Industrial Area",
                raw_text="Packed by Meridian Packers, Industrial Area",
            ),
        ),
        FieldCandidate(field="BARCODE", status="DETECTED", raw_value="8901234567890"),
    ]


@pytest.fixture
def history_reference_case():
    db = SessionLocal()
    username = f"phase5_{uuid.uuid4().hex[:10]}"
    user = UserRepository.create_user(
        db=db, username=username, email=f"{username}@example.test",
        password_hash=hash_password("Phase5Test!"), full_name="Phase Five Officer",
        role="INSPECTOR",
    )
    sessions = []
    for index, lifecycle in enumerate(("IN_PROGRESS", "FINALIZED", "IN_PROGRESS")):
        candidates = _identity_candidates() if index < 2 else [
            FieldCandidate(field="COMMON_GENERIC_NAME", status="DETECTED", raw_value="Different commodity"),
            FieldCandidate(field="BRAND_NAME", status="DETECTED", raw_value="Separate mark"),
        ]
        capture = CaptureRecord(
            capture_id=str(uuid.uuid4()), view_id="FRONT",
            evidence_id=str(uuid.uuid4()), image_sha256=(str(index + 1) * 64)[:64],
            field_candidates=candidates, deterministic_field_candidates=candidates,
        )
        session = InspectionSession(
            inspection_id=str(uuid.uuid4()), reference_date=f"2026-02-{14 + index:02d}",
            product_category="GENERIC_RETAIL_PACKAGE", capture_plan_id="plan_software_1",
            lifecycle_status=lifecycle, capture_status="COMPLETE_EVIDENCE_CAPTURE",
            captures=[capture], aggregated_candidates=candidates,
            deterministic_aggregated_candidates=candidates, created_by_user_id=user.user_id,
        )
        _update_session_compliance(session)
        InspectionRepository.create_inspection(db, session, created_by_user_id=user.user_id)
        InspectionRepository.add_capture_and_update_inspection_state(db, session, capture)
        if lifecycle == "FINALIZED":
            InspectionRepository.save_report_snapshot(db, generate_inspection_report(session, _default_plan))
        sessions.append(session)
        _inspections.pop(session.inspection_id, None)
    token = create_access_token(user_id=user.user_id, role=user.role, username=user.username)
    yield db, user, sessions, {"Authorization": f"Bearer {token}"}
    for session in sessions:
        _inspections.pop(session.inspection_id, None)
        model = db.get(InspectionModel, session.inspection_id)
        if model:
            db.delete(model)
    stored_user = db.get(UserModel, user.user_id)
    if stored_user:
        db.delete(stored_user)
    db.commit()
    db.close()


@pytest.mark.parametrize("term", [
    "Orchard crackers", "Northstar", "Meridian Packers", "8901234567890",
    "FINALIZED", "2026-02-14",
])
def test_history_searches_stored_identity_reference_status_and_date(history_reference_case, term):
    _, _, sessions, headers = history_reference_case
    response = client.get("/api/inspections", params={"search": term}, headers=headers)
    assert response.status_code == 200
    returned = {item["inspection_id"] for item in response.json()["items"]}
    assert returned & {sessions[0].inspection_id, sessions[1].inspection_id}


def test_related_inspections_are_reference_only_and_do_not_change_current_state(history_reference_case):
    _, _, sessions, headers = history_reference_case
    current, previous, unrelated = sessions
    before = deepcopy(client.get(f"/api/inspections/{current.inspection_id}", headers=headers).json())
    response = client.get(f"/api/inspections/{current.inspection_id}/related", headers=headers)
    assert response.status_code == 200
    references = response.json()
    assert [item["inspection_id"] for item in references] == [previous.inspection_id]
    assert references[0]["reference_only"] is True
    assert "MATCHING_BRAND_AND_PRODUCT" in references[0]["match_basis"]
    assert unrelated.inspection_id not in {item["inspection_id"] for item in references}
    after = client.get(f"/api/inspections/{current.inspection_id}", headers=headers).json()
    assert after == before
    assert current.rule_evaluations != previous.rule_evaluations or current.inspection_id != previous.inspection_id


def test_related_endpoint_rehydrates_intermediate_gemini_audit_without_writing(
    history_reference_case,
):
    db, _, sessions, headers = history_reference_case
    current, previous, _ = sessions
    previous_model = db.get(InspectionModel, previous.inspection_id)
    capture_model = previous_model.captures[0]
    payload = _gemini_audit_payload(
        inspection_id="legacy-stored-inspection",
        capture_id="legacy-stored-capture",
        view_id="SIDE_RIGHT",
        image_sha256="0" * 64,
    )
    payload["analysis"]["metadata"].update(LEGACY_GEMINI_ATTEMPT_FIELDS)
    capture_model.ai_analysis = payload
    db.commit()
    stored_before = deepcopy(payload)
    inspection_updated_before = previous_model.updated_at

    _inspections.pop(current.inspection_id, None)
    _inspections.pop(previous.inspection_id, None)
    response = client.get(
        f"/api/inspections/{current.inspection_id}/related",
        headers=headers,
    )

    assert response.status_code == 200
    assert previous.inspection_id in {
        item["inspection_id"] for item in response.json()
    }
    db.expire_all()
    stored_capture = db.get(CaptureModel, capture_model.capture_id)
    stored_inspection = db.get(InspectionModel, previous.inspection_id)
    assert stored_capture.ai_analysis == stored_before
    assert stored_inspection.updated_at == inspection_updated_before


def test_reference_match_does_not_use_previous_verdict_or_notes():
    candidates = _identity_candidates()
    current = InspectionSession(
        inspection_id="current", reference_date="2026-01-01", product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1", aggregated_candidates=candidates,
    )
    previous = current.model_copy(deep=True, update={
        "inspection_id": "previous", "lifecycle_status": "FINALIZED",
        "overall_disposition": "VIOLATIONS_FOUND", "officer_declaration_overrides": [],
    })
    assert related_match_basis(current, previous) == [
        "MATCHING_BARCODE",
        "MATCHING_BRAND_AND_PRODUCT",
        "MATCHING_PRODUCT_AND_BUSINESS",
    ]
    assert current.overall_disposition is None
    assert current.officer_declaration_overrides == []
