import uuid
import pytest
from datetime import datetime, timezone, date
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal, engine, check_db_connection
from app.models.inspection import InspectionModel, CaptureModel, ReportSnapshotModel
from app.repositories.inspection_repository import InspectionRepository
from app.schemas.inspection import (
    InspectionSession,
    CaptureRecord,
    CapturePlan,
    CaptureViewRequirement
)
from app.schemas.ocr import FieldCandidate
from app.schemas.compliance import LegalStatus, RuleEvaluationResult
from app.schemas.applicability import ApplicabilityDecision, ApplicabilityStatus
from app.schemas.report import (
    OverallDisposition,
    ReportMetadata,
    CaptureSummary,
    CaptureViewSummary,
    DeclarationFindingItem,
    VisualComplianceFindingItem,
    ExtractedEvidenceItem,
    InspectorContextSnapshot,
    ReportSummaryCounts,
    ReportEvidenceAsset,
    InspectionReportSnapshot
)
from app.services.report_service import generate_inspection_report
from app.services.storage_adapter import default_storage_adapter

@pytest.fixture
def db_session():
    """Yields a fresh SQLAlchemy database session connected to PostgreSQL."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def test_1_db_connectivity():
    """1. Test PostgreSQL connectivity using SessionLocal."""
    assert check_db_connection() is True

def test_2_and_3_and_4_inspection_persistence_and_unknown_context_and_reference_date(db_session: Session):
    """2, 3, 4. Test inspection persistence, explicit reference date, and UNKNOWN context retention across fresh sessions."""
    insp_id = str(uuid.uuid4())
    domain_session = InspectionSession(
        inspection_id=insp_id,
        reference_date="2025-01-01",
        product_category="ELECTRONICS",
        product_origin="UNKNOWN",
        regulatory_product_class="UNKNOWN",
        date_regulatory_regime="UNKNOWN",
        date_package_exemption="UNKNOWN",
        is_electronic="UNKNOWN",
        package_structure="UNKNOWN",
        alcohol_context="UNKNOWN",
        capture_plan_id="plan_software_1",
        capture_status="INCOMPLETE_INSPECTION",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION"
    )

    # 1. Create in database
    InspectionRepository.create_inspection(db_session, domain_session)
    db_session.close()

    # 2. Open a completely fresh session and retrieve
    fresh_session = SessionLocal()
    try:
        retrieved = InspectionRepository.get_inspection(fresh_session, insp_id)
        assert retrieved is not None
        assert retrieved.inspection_id == insp_id
        assert retrieved.reference_date == "2025-01-01"
        assert retrieved.product_category == "ELECTRONICS"
        
        # Verify UNKNOWN is preserved honestly without hidden defaults
        assert retrieved.product_origin == "UNKNOWN"
        assert retrieved.regulatory_product_class == "UNKNOWN"
        assert retrieved.date_regulatory_regime == "UNKNOWN"
        assert retrieved.date_package_exemption == "UNKNOWN"
        assert retrieved.is_electronic == "UNKNOWN"
        assert retrieved.package_structure == "UNKNOWN"
        assert retrieved.alcohol_context == "UNKNOWN"
        
        # Verify audit timestamps exist
        assert retrieved.created_at is not None
        assert retrieved.updated_at is not None
    finally:
        # Cleanup
        if retrieved:
            fresh_session.delete(retrieved)
            fresh_session.commit()
        fresh_session.close()

def test_5_capture_metadata_and_hash_persistence(db_session: Session):
    """5. Test capture metadata, dimensions, view ID, and SHA-256 persistence attached to an inspection."""
    insp_id = str(uuid.uuid4())
    cap_id = str(uuid.uuid4())
    sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    insp_model = InspectionModel(
        inspection_id=insp_id,
        reference_date="2025-01-01",
        product_category="FOOD_COMMODITY",
        capture_plan_id="plan_software_1"
    )
    db_session.add(insp_model)
    db_session.commit()

    capture = CaptureRecord(
        capture_id=cap_id,
        view_id="FRONT",
        evidence_id="ev_img_01",
        image_sha256=sha,
        status="ACCEPTED",
        pipeline_status="COMPLETED"
    )

    # Add capture via repository
    InspectionRepository.add_capture(db_session, insp_id, capture)
    db_session.close()

    # Fresh session retrieval
    fresh_session = SessionLocal()
    try:
        retrieved_insp = InspectionRepository.get_inspection(fresh_session, insp_id)
        assert retrieved_insp is not None
        assert len(retrieved_insp.captures) == 1
        
        retrieved_cap = retrieved_insp.captures[0]
        assert retrieved_cap.capture_id == cap_id
        assert retrieved_cap.view_id == "FRONT"
        assert retrieved_cap.image_sha256 == sha
        assert retrieved_cap.status == "ACCEPTED"
        assert retrieved_cap.pipeline_status == "COMPLETED"
    finally:
        if retrieved_insp:
            fresh_session.delete(retrieved_insp)
            fresh_session.commit()
        fresh_session.close()

def test_6_and_7_and_8_report_snapshot_persistence_and_deserialization(db_session: Session):
    """6, 7, 8. Test immutable report snapshot persistence, payload preservation, and fresh-session deserialization."""
    insp_id = str(uuid.uuid4())
    rep_id = str(uuid.uuid4())
    sha = "33349924259931b1d7d078b5e683ee3abf333333333333333333333333333333"

    insp_model = InspectionModel(
        inspection_id=insp_id,
        reference_date="2025-01-01",
        product_category="RETAIL_PACKAGE",
        capture_plan_id="plan_software_1"
    )
    db_session.add(insp_model)
    db_session.commit()

    snapshot = InspectionReportSnapshot(
        metadata=ReportMetadata(
            report_id=rep_id,
            inspection_id=insp_id,
            report_schema_version="1.0",
            generated_at="2026-08-25T18:00:00Z",
            reference_date="2025-01-01",
            product_category="RETAIL_PACKAGE",
            capture_plan_id="plan_software_1"
        ),
        overall_disposition=OverallDisposition.REVIEW_REQUIRED,
        disposition_reason="One item requires review",
        summary_counts=ReportSummaryCounts(
            total_statutory_checks=1,
            statutory_pass_count=1,
            statutory_fail_count=0,
            statutory_review_required_count=0,
            statutory_not_applicable_count=0,
            total_visual_checks=1,
            visual_review_required_count=1,
            visual_not_evaluable_count=0,
            visual_observation_clear_count=0
        ),
        inspector_context=InspectorContextSnapshot(
            product_origin="DOMESTIC",
            regulatory_product_class="NON_FOOD",
            date_regulatory_regime="GENERAL",
            date_package_exemption="NONE",
            is_electronic="NON_ELECTRONIC",
            package_structure="SINGLE",
            alcohol_context="NON_ALCOHOLIC"
        ),
        capture_summary=CaptureSummary(
            total_views_required=2,
            captured_required_count=2,
            missing_required_views=[],
            capture_status="COMPLETE_EVIDENCE_CAPTURE",
            evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
            overall_quality_status="ACCEPTABLE",
            views=[
                CaptureViewSummary(
                    view_id="FRONT",
                    display_name="Front View",
                    required=True,
                    captured=True,
                    capture_id="cap_f01",
                    image_sha256=sha
                )
            ]
        ),
        declaration_findings=[
            DeclarationFindingItem(
                rule_id="MRP_DECLARATION_PRESENCE",
                field="MRP",
                status="PASS",
                reason="MRP declared.",
                legal_reference="Rule 6(1)(e)",
                applicability_status="APPLICABLE",
                evidence_ids=["ev_mrp_1"]
            )
        ],
        visual_compliance_findings=[
            VisualComplianceFindingItem(
                rule_id="RULE_8_NET_QUANTITY_SURROUNDING_CLEARANCE",
                field="NET_QUANTITY",
                capability="INSPECTOR_REVIEW_ONLY",
                status="REVIEW_REQUIRED",
                reason="Clearance proxy",
                legal_reference="Rule 8",
                limitations="Line height proxy"
            )
        ],
        extracted_evidence=[
            ExtractedEvidenceItem(
                field="MRP",
                status="DETECTED",
                raw_value="MRP Rs. 100",
                normalized_value={"amount": 100.0},
                confidence=0.99,
                evidence_ids=["ev_mrp_1"],
                capture_ids=["cap_f01"],
                view_ids=["FRONT"]
            )
        ],
        evidence_assets=[
            ReportEvidenceAsset(
                capture_id="cap_f01",
                view_id="FRONT",
                image_sha256=sha,
                media_type="image/jpeg",
                evidence_ids=["ev_mrp_1"],
                image_b64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            )
        ]
    )

    # Save to database
    InspectionRepository.save_report_snapshot(db_session, snapshot)
    db_session.close()

    # Open fresh session and verify
    fresh_session = SessionLocal()
    try:
        rep_record = InspectionRepository.get_report_snapshot(fresh_session, rep_id)
        assert rep_record is not None
        assert rep_record.report_id == rep_id
        assert rep_record.inspection_id == insp_id
        assert rep_record.overall_disposition == "REVIEW_REQUIRED"
        
        # Verify large image_b64 is NOT stored in PostgreSQL JSON payload
        assert rep_record.snapshot_payload["evidence_assets"][0]["image_b64"] is None
        
        # Deserialize JSON payload back to Pydantic domain snapshot
        deserialized = InspectionReportSnapshot.model_validate(rep_record.snapshot_payload)
        assert deserialized.metadata.report_id == rep_id
        assert deserialized.overall_disposition == OverallDisposition.REVIEW_REQUIRED
        assert len(deserialized.declaration_findings) == 1
        assert deserialized.declaration_findings[0].rule_id == "MRP_DECLARATION_PRESENCE"
        assert deserialized.evidence_assets[0].image_sha256 == sha
        assert deserialized.evidence_assets[0].image_b64 is None  # Durable binary object storage deferred to Phase 7B
    finally:
        insp = InspectionRepository.get_inspection(fresh_session, insp_id)
        if insp:
            fresh_session.delete(insp)
            fresh_session.commit()
        fresh_session.close()

def test_9_and_10_and_11_cascade_delete_and_duplicate_constraints(db_session: Session):
    """9, 10, 11. Test CASCADE delete on inspection and duplicate ID constraint safety."""
    insp_id = str(uuid.uuid4())
    cap_id = str(uuid.uuid4())

    insp = InspectionModel(
        inspection_id=insp_id,
        reference_date="2025-01-01",
        product_category="TEST_CAT",
        capture_plan_id="plan_software_1"
    )
    db_session.add(insp)
    db_session.commit()

    cap = CaptureModel(
        capture_id=cap_id,
        inspection_id=insp_id,
        view_id="FRONT",
        image_sha256="test_sha_01"
    )
    db_session.add(cap)
    db_session.commit()

    # Verify duplicate inspection_id raises IntegrityError
    dup_session = SessionLocal()
    try:
        dup_insp = InspectionModel(
            inspection_id=insp_id,
            reference_date="2025-01-01",
            product_category="DUP_CAT",
            capture_plan_id="plan_software_1"
        )
        dup_session.add(dup_insp)
        with pytest.raises(IntegrityError):
            dup_session.commit()
    finally:
        dup_session.rollback()
        dup_session.close()

    # Verify CASCADE delete deletes child captures
    db_session.delete(insp)
    db_session.commit()

    assert db_session.get(InspectionModel, insp_id) is None
    assert db_session.get(CaptureModel, cap_id) is None

def test_12_storage_adapter_interface():
    """12. Test storage adapter abstraction boundary."""
    adapter = default_storage_adapter
    adapter.store("key_test", "sha_test_123", b"test_data", "image/jpeg", 100, 100)
    assert adapter.retrieve("key_test") == b"test_data"
    assert adapter.retrieve_by_hash("sha_test_123") == b"test_data"
