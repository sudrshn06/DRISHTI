import hashlib
import io
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers

from app.api.routes import inspections as inspection_routes
from app.db.session import Base
from app.models.inspection import CaptureModel, InspectionModel
from app.models.user import UserModel
from app.repositories.inspection_repository import InspectionRepository
from app.schemas.gemini import (
    GeminiAnalysisStatus,
    GeminiAuditMetadata,
    GeminiPackageAnalysis,
)
from app.schemas.image_quality import ImageQualityAssessment
from app.schemas.inspection import CaptureRecord, InspectionSession
from app.schemas.ocr import FieldCandidate, MrpNormalized, is_authoritative_field_candidate
from app.schemas.officer_review import DeclarationCorrectionRequest, OfficerDeclarationOverride
from app.schemas.report import InspectionReportSnapshot
from app.schemas.visual_assessment import CaptureVisualAssessmentSummary
from app.services.inspection_service import aggregate_candidates
from app.services.officer_review_service import (
    confirm_package_information_review,
    create_officer_declaration_override,
)


def _machine_mrp_candidate(raw_value: str = "MRP Rs 100") -> FieldCandidate:
    return FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value=raw_value,
        normalized_value=MrpNormalized(currency="INR", amount=100.0),
        evidence_ids=["evidence-1"],
        capture_ids=["capture-1"],
        confidence=0.91,
        observation_layer="OCR_OBSERVED",
        extraction_method="PADDLEOCR",
        observation_sources=["PADDLEOCR"],
    )


def _inspection_with_mrp(*, lifecycle_status: str = "READY_FOR_REVIEW") -> InspectionSession:
    capture = CaptureRecord(
        capture_id="capture-1",
        view_id="FRONT",
        image_sha256="a" * 64,
        object_key="inspections/inspection-1/captures/capture-1/source",
        field_candidates=[_machine_mrp_candidate()],
    )
    return InspectionSession(
        inspection_id="inspection-1",
        reference_date="2026-08-29",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        lifecycle_status=lifecycle_status,
        captures=[capture],
        aggregated_candidates=aggregate_candidates([capture]),
    )


def test_repeated_corrections_keep_the_original_machine_observation_and_append_history():
    session = _inspection_with_mrp()
    confirm_package_information_review(
        session,
        user_id="officer-1",
        username="inspector.one",
    )

    first = create_officer_declaration_override(
        session,
        candidate_index=0,
        field="MRP",
        confirmed_value="Rs 110",
        reason="The printed amount is 110",
        supporting_capture_id="capture-1",
        officer_user_id="officer-1",
        officer_username="inspector.one",
    )
    second = create_officer_declaration_override(
        session,
        candidate_index=0,
        field="MRP",
        confirmed_value="Rs 120",
        reason="Closer review confirms the printed amount is 120",
        supporting_capture_id="capture-1",
        officer_user_id="officer-1",
        officer_username="inspector.one",
    )

    assert len(session.officer_declaration_overrides) == 2
    assert first.observed_candidate.raw_value == "MRP Rs 100"
    assert second.observed_candidate.raw_value == "MRP Rs 100"
    assert first.observed_candidate.observation_layer == "AGGREGATED"
    assert second.observed_candidate.observation_layer == "AGGREGATED"
    assert session.aggregated_candidates[0].raw_value == "Rs 120"
    assert session.aggregated_candidates[0].observation_layer == "OFFICER_CONFIRMED"
    assert session.package_information_review is None


@pytest.mark.parametrize(
    "confirmed_candidate",
    [
        FieldCandidate(field="MRP", status="NOT_DETECTED"),
        FieldCandidate(
            field="MRP",
            status="DETECTED",
            raw_value="Rs 120",
            normalized_value=MrpNormalized(currency="INR", amount=120.0),
            observation_layer="AI_OBSERVED",
            extraction_method="GEMINI",
            observation_sources=["GEMINI"],
        ),
    ],
)
def test_officer_correction_contract_rejects_absence_and_ai_authority(confirmed_candidate):
    with pytest.raises(ValidationError):
        OfficerDeclarationOverride(
            override_id="override-1",
            target_key="MRP",
            field="MRP",
            observed_candidate=_machine_mrp_candidate(),
            confirmed_candidate=confirmed_candidate,
            supporting_capture_id="capture-1",
            reason="Visible package text checked by the officer",
            officer_user_id="officer-1",
            officer_username="inspector.one",
            confirmed_at=datetime.now(timezone.utc),
        )


@pytest.mark.asyncio
async def test_correction_endpoint_invalidates_review_and_reruns_deterministic_assessment(monkeypatch):
    session = _inspection_with_mrp()
    confirm_package_information_review(
        session,
        user_id="officer-1",
        username="inspector.one",
    )
    session.report_snapshot = {"marker": "preview-before-correction"}
    assessment_calls = []

    def rerun_assessment(updated_session):
        assessment_calls.append(updated_session.aggregated_candidates[0].raw_value)

    monkeypatch.setattr(inspection_routes, "_update_session_compliance", rerun_assessment)
    monkeypatch.setattr(
        InspectionRepository,
        "update_inspection_state",
        staticmethod(lambda *_args: object()),
    )

    updated = await inspection_routes.correct_inspection_declaration(
        request=DeclarationCorrectionRequest(
            candidate_index=0,
            field="MRP",
            confirmed_value="Rs 120",
            reason="The visible printed amount is 120",
            supporting_capture_id="capture-1",
        ),
        session=session,
        current_user=UserModel(
            user_id="officer-1",
            username="inspector.one",
            email="inspector.one@example.test",
            password_hash="not-used",
            full_name="Inspector One",
            role="INSPECTOR",
            is_active=True,
        ),
        db=object(),
    )

    assert assessment_calls == ["Rs 120"]
    assert updated.package_information_review is None
    assert updated.report_snapshot is None
    assert updated.overall_disposition is None


def test_capture_and_inspection_state_rollback_together_when_commit_fails():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with local_session() as db:
        db.add(InspectionModel(
            inspection_id="inspection-atomic",
            reference_date="2026-08-29",
            product_category="GENERIC_RETAIL_PACKAGE",
            capture_plan_id="plan_software_1",
            capture_status="INCOMPLETE_INSPECTION",
            evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
            lifecycle_status="DRAFT",
            product_origin="UNKNOWN",
            regulatory_product_class="UNKNOWN",
            date_regulatory_regime="UNKNOWN",
            date_package_exemption="UNKNOWN",
            is_electronic="UNKNOWN",
            package_structure="UNKNOWN",
            alcohol_context="UNKNOWN",
        ))
        db.commit()

        domain = InspectionSession(
            inspection_id="inspection-atomic",
            reference_date="2026-08-29",
            product_category="GENERIC_RETAIL_PACKAGE",
            capture_plan_id="plan_software_1",
            capture_status="COMPLETE_EVIDENCE_CAPTURE",
            lifecycle_status="READY_FOR_REVIEW",
        )
        capture = CaptureRecord(
            capture_id="capture-atomic",
            view_id="FRONT",
            image_sha256="b" * 64,
        )

        def reject_commit(_session):
            raise RuntimeError("simulated PostgreSQL commit failure")

        event.listen(db, "before_commit", reject_commit)
        with pytest.raises(RuntimeError, match="simulated PostgreSQL"):
            InspectionRepository.add_capture_and_update_inspection_state(
                db,
                domain,
                capture,
            )
        event.remove(db, "before_commit", reject_commit)

    with local_session() as verification_db:
        stored = verification_db.get(InspectionModel, "inspection-atomic")
        assert stored.capture_status == "INCOMPLETE_INSPECTION"
        assert stored.lifecycle_status == "DRAFT"
        assert verification_db.get(CaptureModel, "capture-atomic") is None


@pytest.mark.asyncio
async def test_capture_object_is_deleted_when_atomic_persistence_fails(monkeypatch):
    class FakeImage:
        shape = (12, 20, 3)

    class FakeStorage:
        def __init__(self):
            self.stored = []
            self.deleted = []

        def store(self, **kwargs):
            self.stored.append(kwargs["key"])
            return True

        def delete(self, key):
            self.deleted.append(key)
            return True

    class FakeDb:
        def __init__(self):
            self.rollback_called = False

        def rollback(self):
            self.rollback_called = True

    async def disabled_analysis(**_kwargs):
        return GeminiPackageAnalysis(
            status=GeminiAnalysisStatus.DISABLED,
            metadata=GeminiAuditMetadata(
                model="disabled",
                schema_version="1.0",
                prompt_version="stage-1",
                generated_at=datetime.now(timezone.utc),
                failure_code="DISABLED",
            ),
        )

    def fail_persistence(*_args, **_kwargs):
        raise RuntimeError("simulated persistence failure")

    storage = FakeStorage()
    db = FakeDb()
    session = _inspection_with_mrp(lifecycle_status="DRAFT")
    session.captures = []
    session.aggregated_candidates = []
    monkeypatch.setattr(inspection_routes, "default_storage_adapter", storage)
    monkeypatch.setattr(
        inspection_routes,
        "validate_and_decode_image",
        lambda _image: (FakeImage(), hashlib.sha256(b"image-bytes").hexdigest()),
    )
    monkeypatch.setattr(
        inspection_routes,
        "assess_image_quality",
        lambda _image: ImageQualityAssessment(
            width=20,
            height=12,
            blur_score=100.0,
            brightness=120.0,
            glare_percentage=0.0,
            quality_status="ACCEPTABLE",
        ),
    )
    monkeypatch.setattr(inspection_routes, "analyze_image", lambda _image: [])
    monkeypatch.setattr(inspection_routes, "extract_candidates", lambda *_args: [])
    monkeypatch.setattr(
        inspection_routes,
        "assess_capture_visuals",
        lambda **kwargs: CaptureVisualAssessmentSummary(
            capture_id=kwargs["capture_id"],
            view_id=kwargs["view_id"],
            image_width=kwargs["image_width"],
            image_height=kwargs["image_height"],
        ),
    )
    monkeypatch.setattr(inspection_routes, "refresh_detected_package_context", lambda _session: None)
    monkeypatch.setattr(inspection_routes, "_update_session_compliance", lambda _session: None)
    monkeypatch.setattr(
        inspection_routes.default_contextual_vision_service.provider,
        "analyze_package",
        disabled_analysis,
    )
    monkeypatch.setattr(
        InspectionRepository,
        "add_capture_and_update_inspection_state",
        staticmethod(fail_persistence),
        raising=False,
    )
    monkeypatch.setattr(
        InspectionRepository,
        "add_capture",
        staticmethod(fail_persistence),
    )

    upload = UploadFile(
        filename="package.jpg",
        file=io.BytesIO(b"image-bytes"),
        headers=Headers({"content-type": "image/jpeg"}),
    )
    with pytest.raises(HTTPException) as caught:
        await inspection_routes.upload_capture(
            inspection_id=session.inspection_id,
            view_id="FRONT",
            image=upload,
            session=session,
            db=db,
        )

    assert caught.value.status_code == 503
    assert len(storage.stored) == 1
    assert storage.deleted == storage.stored
    assert db.rollback_called is True


@pytest.mark.asyncio
async def test_authenticated_capture_endpoint_falls_back_to_legacy_server_key(monkeypatch):
    image_bytes = b"legacy-image"
    capture = CaptureRecord(
        capture_id="legacy-capture",
        view_id="FRONT",
        image_sha256=hashlib.sha256(image_bytes).hexdigest(),
        object_key="legacy/stale/object-key",
    )
    session = InspectionSession(
        inspection_id="legacy-inspection",
        reference_date="2026-08-29",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        captures=[capture],
    )

    class LegacyStorage:
        def __init__(self):
            self.keys = []

        def retrieve(self, key):
            self.keys.append(key)
            legacy_key = "inspections/legacy-inspection/captures/legacy-capture/source.jpg"
            return image_bytes if key == legacy_key else None

        def retrieve_by_hash(self, _sha256):
            return None

    storage = LegacyStorage()
    monkeypatch.setattr(inspection_routes, "default_storage_adapter", storage)

    response = await inspection_routes.get_capture_image(
        capture_id="legacy-capture",
        session=session,
    )

    assert response.body == image_bytes
    assert response.headers["cache-control"] == "private, no-store, max-age=0"
    assert "legacy/stale/object-key" in storage.keys
    assert "inspections/legacy-inspection/captures/legacy-capture/source.jpg" in storage.keys
    assert "object_key" not in capture.model_dump(mode="json")


@pytest.mark.asyncio
async def test_mutable_inspection_does_not_show_an_older_report_snapshot(monkeypatch):
    session = _inspection_with_mrp(lifecycle_status="READY_FOR_REVIEW")
    session.report_snapshot = None
    stale = {"marker": "stale-before-correction"}
    fresh = {"marker": "fresh-after-correction"}

    monkeypatch.setattr(
        InspectionRepository,
        "get_latest_report_snapshot_for_inspection",
        staticmethod(lambda *_args: SimpleNamespace(snapshot_payload=stale)),
    )
    monkeypatch.setattr(
        InspectionRepository,
        "save_report_snapshot",
        staticmethod(lambda *_args: None),
    )
    monkeypatch.setattr(
        InspectionReportSnapshot,
        "model_validate",
        classmethod(lambda _cls, payload: payload),
    )
    monkeypatch.setattr(inspection_routes, "generate_inspection_report", lambda *_args: fresh)

    report = await inspection_routes.get_inspection_report(
        inspection_id=session.inspection_id,
        session=session,
        db=object(),
    )

    assert report is fresh
    assert session.report_snapshot is fresh


@pytest.mark.asyncio
async def test_finalized_inspection_keeps_its_in_memory_immutable_report(monkeypatch):
    session = _inspection_with_mrp(lifecycle_status="FINALIZED")
    immutable = {"marker": "officer-finalized"}
    session.report_snapshot = immutable
    monkeypatch.setattr(
        inspection_routes,
        "generate_inspection_report",
        lambda *_args: pytest.fail("a finalized report must not be regenerated"),
    )

    report = await inspection_routes.get_inspection_report(
        inspection_id=session.inspection_id,
        session=session,
        db=object(),
    )

    assert report is immutable
    assert is_authoritative_field_candidate(session.aggregated_candidates[0])
