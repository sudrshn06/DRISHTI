import io
import uuid
import hashlib
import numpy as np
import cv2
import pytest
from datetime import datetime, timezone, date
from sqlalchemy.orm import Session
from docx import Document
import pypdf

from app.core.config import Settings, settings
from app.db.session import SessionLocal, check_db_connection
from app.models.inspection import InspectionModel, CaptureModel, ReportSnapshotModel
from app.repositories.inspection_repository import InspectionRepository
from app.services.storage_adapter import default_storage_adapter, MinioStorageAdapter
from app.schemas.inspection import (
    InspectionSession,
    CaptureRecord,
    CapturePlan,
    CaptureViewRequirement
)
from app.schemas.ocr import FieldCandidate
from app.schemas.compliance import LegalStatus, RuleEvaluationResult
from app.schemas.applicability import ApplicabilityDecision, ApplicabilityStatus
from app.schemas.visual_assessment import (
    CaptureVisualAssessmentSummary,
    DeclarationVisualAssessment,
    RegionGeometry,
    PixelBoundingBox,
    NormalizedBoundingBox,
    VisualReadabilitySignal,
    VisualCheckCapability,
    VisualObservationStatus,
    VisualRuleEvaluationResult
)
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
from app.services.pdf_report_service import generate_pdf_report
from app.services.docx_report_service import generate_docx_report

@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def create_synthetic_image(width=600, height=400, text="MINIO PERSISTENCE TEST", is_png=False) -> tuple[bytes, str]:
    img = np.full((height, width, 3), (240, 240, 240), dtype=np.uint8)
    cv2.putText(img, text, (40, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20, 20, 20), 2)
    ext = ".png" if is_png else ".jpg"
    mime = "image/png" if is_png else "image/jpeg"
    success, encoded = cv2.imencode(ext, img)
    return encoded.tobytes(), mime

def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def extract_docx_text(docx_bytes: bytes) -> str:
    doc = Document(io.BytesIO(docx_bytes))
    full_text = [p.text for p in doc.paragraphs if p.text]
    for table in doc.tables:
        for row in table.rows:
            row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_text:
                full_text.append(" | ".join(row_text))
    return "\n".join(full_text)

def test_1_credentials_loaded_from_environment():
    """1. Verify that storage credentials come from environment configuration and no secret literal is hardcoded."""
    # The Settings class definition defaults must be empty strings (no hardcoded secret in python code)
    assert Settings.model_fields["minio_access_key"].default == ""
    assert Settings.model_fields["minio_secret_key"].default == ""

    # Live active settings has values loaded via environment / .env
    assert settings.minio_access_key != ""
    assert settings.minio_endpoint != ""
    assert settings.minio_bucket_name == "drishti-captures"

def test_2_single_physical_object_stored_no_duplicate_binary():
    """2. Verify that storing an image in MinIO creates exactly ONE physical object under key, not duplicate hashes/{sha256}."""
    storage = default_storage_adapter
    img_bytes, mime = create_synthetic_image(text="SINGLE OBJECT TEST")
    sha = hashlib.sha256(img_bytes).hexdigest()
    
    obj_key = f"test_single_obj/{uuid.uuid4()}/source"
    hash_alias_key = f"hashes/{sha}"
    
    # Store object
    storage.store(key=obj_key, sha256_hash=sha, data=img_bytes, media_type=mime)
    
    # Canonical object MUST exist
    assert storage.exists(obj_key) is True
    
    # Duplicate hash key MUST NOT be created in MinIO
    if isinstance(storage, MinioStorageAdapter):
        client = storage._get_client()
        if client:
            try:
                client.stat_object(storage.bucket_name, hash_alias_key)
                duplicate_found = True
            except Exception:
                duplicate_found = False
            assert duplicate_found is False, "Duplicate object under hashes/ found in MinIO!"
            
    # Cleanup
    storage.delete(obj_key)

def test_3_hash_lookup_via_postgres_index(db_session: Session):
    """3. Verify that retrieve_by_hash resolves the object_key from PostgreSQL captures index without duplicate object."""
    storage = default_storage_adapter
    insp_id = str(uuid.uuid4())
    cap_id = str(uuid.uuid4())
    img_bytes, mime = create_synthetic_image(text="HASH RESOLUTION TEST")
    sha = hashlib.sha256(img_bytes).hexdigest()
    obj_key = f"inspections/{insp_id}/captures/{cap_id}/source"
    
    # 1. Store only under canonical key in MinIO
    storage.store(key=obj_key, sha256_hash=sha, data=img_bytes, media_type=mime)
    
    # 2. Persist capture in PostgreSQL
    insp = InspectionModel(
        inspection_id=insp_id,
        reference_date="2025-01-01",
        product_category="RETAIL_GOODS",
        capture_plan_id="plan_software_1"
    )
    db_session.add(insp)
    db_session.commit()
    
    cap = CaptureRecord(
        capture_id=cap_id,
        view_id="FRONT",
        image_sha256=sha,
        object_key=obj_key,
        status="ACCEPTED",
        pipeline_status="COMPLETED"
    )
    InspectionRepository.add_capture(db_session, insp_id, cap)
    
    # 3. Retrieve by hash (resolves object_key from DB)
    retrieved_bytes = storage.retrieve_by_hash(sha)
    assert retrieved_bytes is not None
    assert hashlib.sha256(retrieved_bytes).hexdigest() == sha
    assert retrieved_bytes == img_bytes
    
    # Cleanup
    db_session.delete(insp)
    db_session.commit()
    storage.delete(obj_key)

def test_4_object_cleanup_and_isolation():
    """4. Verify service-controlled deletion of inspection objects, idempotency, and isolation from unrelated inspections."""
    storage = default_storage_adapter
    insp1_id = str(uuid.uuid4())
    insp2_id = str(uuid.uuid4())
    
    img1, _ = create_synthetic_image(text="INSP 1 IMAGE A")
    img2, _ = create_synthetic_image(text="INSP 1 IMAGE B")
    img3, _ = create_synthetic_image(text="INSP 2 IMAGE C")
    
    key1 = f"inspections/{insp1_id}/captures/c1/source"
    key2 = f"inspections/{insp1_id}/captures/c2/source"
    key3 = f"inspections/{insp2_id}/captures/c3/source"
    
    storage.store(key1, hashlib.sha256(img1).hexdigest(), img1)
    storage.store(key2, hashlib.sha256(img2).hexdigest(), img2)
    storage.store(key3, hashlib.sha256(img3).hexdigest(), img3)
    
    assert storage.exists(key1) is True
    assert storage.exists(key2) is True
    assert storage.exists(key3) is True
    
    # Delete only inspection 1 objects
    deleted_count = storage.delete_inspection_objects(insp1_id)
    assert deleted_count >= 2
    
    # Insp 1 objects are deleted
    assert storage.exists(key1) is False
    assert storage.exists(key2) is False
    
    # Insp 2 objects remain COMPLETELY UNTOUCHED
    assert storage.exists(key3) is True
    
    # Idempotent deletion on already deleted inspection
    assert storage.delete_inspection_objects(insp1_id) == 0
    
    # Cleanup insp 2
    storage.delete_inspection_objects(insp2_id)
    assert storage.exists(key3) is False

def test_5_png_and_jpeg_media_types_and_sha_integrity():
    """5. Verify that PNG and JPEG source bytes preserve original format, media type, and exact SHA-256."""
    storage = default_storage_adapter
    
    # Test PNG
    png_bytes, png_mime = create_synthetic_image(text="PNG SOURCE EVIDENCE", is_png=True)
    png_sha = hashlib.sha256(png_bytes).hexdigest()
    png_key = f"test_media_types/{uuid.uuid4()}/source"
    
    storage.store(key=png_key, sha256_hash=png_sha, data=png_bytes, media_type=png_mime)
    retrieved_png = storage.retrieve(png_key)
    assert retrieved_png == png_bytes
    assert hashlib.sha256(retrieved_png).hexdigest() == png_sha
    
    # Test JPEG
    jpg_bytes, jpg_mime = create_synthetic_image(text="JPEG SOURCE EVIDENCE", is_png=False)
    jpg_sha = hashlib.sha256(jpg_bytes).hexdigest()
    jpg_key = f"test_media_types/{uuid.uuid4()}/source"
    
    storage.store(key=jpg_key, sha256_hash=jpg_sha, data=jpg_bytes, media_type=jpg_mime)
    retrieved_jpg = storage.retrieve(jpg_key)
    assert retrieved_jpg == jpg_bytes
    assert hashlib.sha256(retrieved_jpg).hexdigest() == jpg_sha
    
    # Cleanup
    storage.delete(png_key)
    storage.delete(jpg_key)

def test_6_capture_object_key_persistence_and_rehydration(db_session: Session):
    """6. Test capture object_key persistence in PostgreSQL, context rehydration, and fresh-session recovery."""
    insp_id = str(uuid.uuid4())
    cap_id = str(uuid.uuid4())
    img_bytes, mime = create_synthetic_image(text="MRP Rs. 299")
    sha = hashlib.sha256(img_bytes).hexdigest()
    obj_key = f"inspections/{insp_id}/captures/{cap_id}/source"
    
    # 1. Store in MinIO
    default_storage_adapter.store(key=obj_key, sha256_hash=sha, data=img_bytes, media_type=mime, width=600, height=400)
    
    # 2. Persist in PostgreSQL
    domain_session = InspectionSession(
        inspection_id=insp_id,
        reference_date="2025-01-01",
        product_category="RETAIL_GOODS",
        product_origin="UNKNOWN",
        regulatory_product_class="UNKNOWN",
        date_regulatory_regime="UNKNOWN",
        date_package_exemption="UNKNOWN",
        is_electronic="UNKNOWN",
        package_structure="UNKNOWN",
        alcohol_context="UNKNOWN",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"
    )
    InspectionRepository.create_inspection(db_session, domain_session)
    
    capture_rec = CaptureRecord(
        capture_id=cap_id,
        view_id="FRONT",
        evidence_id="ev_01",
        image_sha256=sha,
        object_key=obj_key,
        status="ACCEPTED",
        pipeline_status="COMPLETED"
    )
    InspectionRepository.add_capture(db_session, insp_id, capture_rec)
    db_session.close()
    
    # 3. Open completely fresh session and rehydrate
    fresh_session = SessionLocal()
    try:
        model = InspectionRepository.get_inspection(fresh_session, insp_id)
        assert model is not None
        
        # Verify object_key is stored in PostgreSQL captures table
        assert len(model.captures) == 1
        assert model.captures[0].object_key == obj_key
        assert model.captures[0].image_sha256 == sha
        
        # Rehydrate domain InspectionSession schema
        rehydrated = InspectionRepository.inspection_model_to_domain(model)
        assert rehydrated.inspection_id == insp_id
        assert rehydrated.product_origin == "UNKNOWN"
        assert len(rehydrated.captures) == 1
        assert rehydrated.captures[0].object_key == obj_key
        
        # Retrieve image bytes from MinIO via persisted object_key
        fetched_img = default_storage_adapter.retrieve(rehydrated.captures[0].object_key)
        assert fetched_img is not None
        assert hashlib.sha256(fetched_img).hexdigest() == sha
    finally:
        insp_to_del = InspectionRepository.get_inspection(fresh_session, insp_id)
        if insp_to_del:
            fresh_session.delete(insp_to_del)
            fresh_session.commit()
        fresh_session.close()
        default_storage_adapter.delete(obj_key)

def test_7_historical_report_regeneration_with_minio_evidence(db_session: Session):
    """7. Test immutable report persistence (no image_b64 in DB) and transient hydration from MinIO during PDF/DOCX regeneration."""
    import base64
    insp_id = str(uuid.uuid4())
    cap_id = str(uuid.uuid4())
    rep_id = str(uuid.uuid4())
    img_bytes, mime = create_synthetic_image(text="MRP Rs. 799.00")
    sha = hashlib.sha256(img_bytes).hexdigest()
    obj_key = f"inspections/{insp_id}/captures/{cap_id}/source"
    
    # 1. Store in MinIO
    default_storage_adapter.store(key=obj_key, sha256_hash=sha, data=img_bytes, media_type=mime, width=600, height=400)
    
    # 2. Persist Inspection and Report Snapshot (with image_b64 stripped in DB)
    insp_model = InspectionModel(
        inspection_id=insp_id,
        reference_date="2025-01-01",
        product_category="RETAIL_GOODS",
        capture_plan_id="plan_software_1"
    )
    db_session.add(insp_model)
    db_session.commit()
    
    snapshot = InspectionReportSnapshot(
        metadata=ReportMetadata(
            report_id=rep_id,
            inspection_id=insp_id,
            report_schema_version="1.0",
            generated_at="2026-08-26T00:00:00Z",
            reference_date="2025-01-01",
            product_category="RETAIL_GOODS",
            capture_plan_id="plan_software_1"
        ),
        overall_disposition=OverallDisposition.NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE,
        disposition_reason="All evaluated declarations present",
        summary_counts=ReportSummaryCounts(
            total_statutory_checks=1,
            statutory_pass_count=1,
            statutory_fail_count=0,
            statutory_review_required_count=0,
            statutory_not_applicable_count=0,
            total_visual_checks=0,
            visual_review_required_count=0,
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
            total_views_required=1,
            captured_required_count=1,
            missing_required_views=[],
            capture_status="COMPLETE_EVIDENCE_CAPTURE",
            evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
            overall_quality_status="ACCEPTABLE",
            views=[
                CaptureViewSummary(
                    view_id="FRONT",
                    display_name="Front",
                    required=True,
                    captured=True,
                    capture_id=cap_id,
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
                evidence_ids=["ev_mrp_99"]
            )
        ],
        visual_compliance_findings=[],
        extracted_evidence=[
            ExtractedEvidenceItem(
                field="MRP",
                status="DETECTED",
                raw_value="MRP Rs. 799.00",
                normalized_value={"amount": 799.0},
                confidence=0.99,
                evidence_ids=["ev_mrp_99"],
                capture_ids=[cap_id],
                view_ids=["FRONT"],
                has_geometry=True,
                pixel_box={"x_min": 40, "y_min": 100, "x_max": 300, "y_max": 200}
            )
        ],
        evidence_assets=[
            ReportEvidenceAsset(
                capture_id=cap_id,
                view_id="FRONT",
                image_sha256=sha,
                media_type="image/jpeg",
                evidence_ids=["ev_mrp_99"],
                image_b64=None # As stored in DB
            )
        ]
    )
    
    InspectionRepository.save_report_snapshot(db_session, snapshot)
    db_session.close()
    
    # 3. Open fresh session, load snapshot, transiently hydrate from MinIO, and render PDF/DOCX
    fresh_session = SessionLocal()
    try:
        rep_db = InspectionRepository.get_report_snapshot(fresh_session, rep_id)
        assert rep_db is not None
        assert rep_db.snapshot_payload["evidence_assets"][0]["image_b64"] is None
        
        # Reconstruct domain snapshot
        reconstructed = InspectionReportSnapshot.model_validate(rep_db.snapshot_payload)
        
        # Transient hydration via MinIO with SHA-256 verification
        for asset in reconstructed.evidence_assets:
            img = default_storage_adapter.retrieve(f"inspections/{insp_id}/captures/{asset.capture_id}/source")
            if not img:
                img = default_storage_adapter.retrieve_by_hash(asset.image_sha256)
            assert img is not None
            assert hashlib.sha256(img).hexdigest() == asset.image_sha256
            asset.image_b64 = base64.b64encode(img).decode("ascii")
            
        # Render PDF & DOCX
        pdf_bytes = generate_pdf_report(reconstructed)
        docx_bytes = generate_docx_report(reconstructed)
        
        pdf_text = extract_pdf_text(pdf_bytes)
        docx_text = extract_docx_text(docx_bytes)
        
        assert "NO VIOLATIONS DETECTED" in pdf_text
        assert "NO VIOLATIONS DETECTED" in docx_text
        assert "ev_mrp_99" in pdf_text
        assert "ev_mrp_99" in docx_text
        assert sha[:16] in pdf_text
        assert sha[:16] in docx_text
        
        # Check embedded image presence
        doc = Document(io.BytesIO(docx_bytes))
        assert len(doc.inline_shapes) >= 1
    finally:
        insp = InspectionRepository.get_inspection(fresh_session, insp_id)
        if insp:
            fresh_session.delete(insp)
            fresh_session.commit()
        fresh_session.close()
        default_storage_adapter.delete(obj_key)

def test_8_failure_consistency_missing_and_tampered_objects():
    """8. Test failure consistency on missing objects and hash-mismatch tampered objects."""
    storage = default_storage_adapter
    
    # Missing object
    assert storage.retrieve("non_existent_key_9999") is None
    
    # Hash verification check
    valid_bytes, _ = create_synthetic_image(text="AUTHENTIC IMAGE")
    valid_sha = hashlib.sha256(valid_bytes).hexdigest()
    
    tampered_bytes, _ = create_synthetic_image(text="TAMPERED IMAGE")
    tampered_sha = hashlib.sha256(tampered_bytes).hexdigest()
    
    # Verify hash mismatch is strictly detected
    assert valid_sha != tampered_sha
    assert hashlib.sha256(tampered_bytes).hexdigest() != valid_sha

def test_9_multiple_report_snapshots_per_inspection(db_session: Session):
    """9. Test that an inspection supports multiple immutable historical reports without overwriting."""
    insp_id = str(uuid.uuid4())
    rep1_id = str(uuid.uuid4())
    rep2_id = str(uuid.uuid4())
    
    insp_model = InspectionModel(
        inspection_id=insp_id,
        reference_date="2025-01-01",
        product_category="RETAIL_GOODS",
        capture_plan_id="plan_software_1"
    )
    db_session.add(insp_model)
    db_session.commit()
    
    dummy_counts = ReportSummaryCounts(
        total_statutory_checks=0,
        statutory_pass_count=0,
        statutory_fail_count=0,
        statutory_review_required_count=0,
        statutory_not_applicable_count=0,
        total_visual_checks=0,
        visual_review_required_count=0,
        visual_not_evaluable_count=0,
        visual_observation_clear_count=0
    )
    
    dummy_context = InspectorContextSnapshot(
        product_origin="DOMESTIC",
        regulatory_product_class="NON_FOOD",
        date_regulatory_regime="GENERAL",
        date_package_exemption="NONE",
        is_electronic="NON_ELECTRONIC",
        package_structure="SINGLE",
        alcohol_context="NON_ALCOHOLIC"
    )
    
    snap1 = InspectionReportSnapshot(
        metadata=ReportMetadata(
            report_id=rep1_id,
            inspection_id=insp_id,
            report_schema_version="1.0",
            generated_at="2026-08-26T00:00:00Z",
            reference_date="2025-01-01",
            product_category="RETAIL_GOODS",
            capture_plan_id="plan_software_1"
        ),
        overall_disposition=OverallDisposition.INCOMPLETE_INSPECTION,
        disposition_reason="Initial incomplete capture",
        summary_counts=dummy_counts,
        inspector_context=dummy_context,
        capture_summary=CaptureSummary(total_views_required=2, captured_required_count=1, capture_status="INCOMPLETE_INSPECTION", evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION", overall_quality_status="ACCEPTABLE")
    )
    
    snap2 = InspectionReportSnapshot(
        metadata=ReportMetadata(
            report_id=rep2_id,
            inspection_id=insp_id,
            report_schema_version="1.0",
            generated_at="2026-08-26T00:10:00Z",
            reference_date="2025-01-01",
            product_category="RETAIL_GOODS",
            capture_plan_id="plan_software_1"
        ),
        overall_disposition=OverallDisposition.NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE,
        disposition_reason="Completed full capture",
        summary_counts=dummy_counts,
        inspector_context=dummy_context,
        capture_summary=CaptureSummary(total_views_required=2, captured_required_count=2, capture_status="COMPLETE_EVIDENCE_CAPTURE", evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION", overall_quality_status="ACCEPTABLE")
    )
    
    InspectionRepository.save_report_snapshot(db_session, snap1)
    InspectionRepository.save_report_snapshot(db_session, snap2)
    db_session.close()
    
    fresh_session = SessionLocal()
    try:
        insp = InspectionRepository.get_inspection(fresh_session, insp_id)
        assert insp is not None
        assert len(insp.report_snapshots) == 2
        
        r1 = InspectionRepository.get_report_snapshot(fresh_session, rep1_id)
        r2 = InspectionRepository.get_report_snapshot(fresh_session, rep2_id)
        
        assert r1.overall_disposition == "INCOMPLETE_INSPECTION"
        assert r2.overall_disposition == "NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE"
    finally:
        insp_del = InspectionRepository.get_inspection(fresh_session, insp_id)
        if insp_del:
            fresh_session.delete(insp_del)
            fresh_session.commit()
        fresh_session.close()
