import io
import uuid
import hashlib
import numpy as np
import cv2
from datetime import datetime, timezone
from docx import Document
import pypdf

from app.db.session import SessionLocal
from app.models.inspection import InspectionModel, CaptureModel, ReportSnapshotModel
from app.repositories.inspection_repository import InspectionRepository
from app.services.storage_adapter import default_storage_adapter
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
    ExtractedEvidenceItem,
    InspectorContextSnapshot,
    ReportSummaryCounts,
    ReportEvidenceAsset,
    InspectionReportSnapshot
)
from app.services.report_service import generate_inspection_report
from app.services.pdf_report_service import generate_pdf_report
from app.services.docx_report_service import generate_docx_report

def create_synthetic_image(text="RESTART PERSISTENCE IMAGE") -> bytes:
    img = np.full((400, 600, 3), (245, 245, 245), dtype=np.uint8)
    cv2.putText(img, text, (30, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (10, 10, 10), 2)
    success, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()

def stage_data():
    insp_id = "insp_real_restart_001"
    cap_id = "cap_real_restart_001"
    rep_id = "rep_real_restart_001"
    
    img_bytes = create_synthetic_image("STAGE RESTART IMAGE")
    sha = hashlib.sha256(img_bytes).hexdigest()
    obj_key = f"inspections/{insp_id}/captures/{cap_id}/source"
    
    # 1. MinIO
    default_storage_adapter.store(key=obj_key, sha256_hash=sha, data=img_bytes, media_type="image/jpeg", width=600, height=400)
    
    # 2. PostgreSQL
    session = SessionLocal()
    try:
        # Clean existing if any
        existing = session.get(InspectionModel, insp_id)
        if existing:
            session.delete(existing)
            session.commit()
            
        insp = InspectionModel(
            inspection_id=insp_id,
            reference_date="2025-01-01",
            product_category="RETAIL_PACKAGE",
            capture_plan_id="plan_software_1"
        )
        session.add(insp)
        session.commit()
        
        cap = CaptureRecord(
            capture_id=cap_id,
            view_id="FRONT",
            image_sha256=sha,
            object_key=obj_key,
            status="ACCEPTED",
            pipeline_status="COMPLETED"
        )
        InspectionRepository.add_capture(session, insp_id, cap)
        
        snap = InspectionReportSnapshot(
            metadata=ReportMetadata(
                report_id=rep_id,
                inspection_id=insp_id,
                report_schema_version="1.0",
                generated_at="2026-08-26T00:00:00Z",
                reference_date="2025-01-01",
                product_category="RETAIL_PACKAGE",
                capture_plan_id="plan_software_1"
            ),
            overall_disposition=OverallDisposition.NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE,
            disposition_reason="Passed all statutory checks",
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
                capture_status="COMPLETE_EVIDENCE_CAPTURE",
                evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
                overall_quality_status="ACCEPTABLE"
            ),
            declaration_findings=[
                DeclarationFindingItem(
                    rule_id="MRP_DECLARATION_PRESENCE",
                    field="MRP",
                    status="PASS",
                    reason="MRP present",
                    legal_reference="Rule 6(1)(e)",
                    applicability_status="APPLICABLE",
                    evidence_ids=["ev_restart_99"]
                )
            ],
            extracted_evidence=[
                ExtractedEvidenceItem(
                    field="MRP",
                    status="DETECTED",
                    raw_value="MRP Rs. 500",
                    normalized_value={"amount": 500.0},
                    confidence=0.99,
                    evidence_ids=["ev_restart_99"],
                    capture_ids=[cap_id],
                    view_ids=["FRONT"],
                    has_geometry=True,
                    pixel_box={"x_min": 30, "y_min": 100, "x_max": 250, "y_max": 200}
                )
            ],
            evidence_assets=[
                ReportEvidenceAsset(
                    capture_id=cap_id,
                    view_id="FRONT",
                    image_sha256=sha,
                    media_type="image/jpeg",
                    evidence_ids=["ev_restart_99"],
                    image_b64=None
                )
            ]
        )
        InspectionRepository.save_report_snapshot(session, snap)
    finally:
        session.close()
        
    print("STAGE_DATA_COMPLETE: insp_id=", insp_id, "sha=", sha)

def verify_after_restart():
    import base64
    insp_id = "insp_real_restart_001"
    cap_id = "cap_real_restart_001"
    rep_id = "rep_real_restart_001"
    
    session = SessionLocal()
    try:
        # 1. Retrieve Inspection
        insp = InspectionRepository.get_inspection(session, insp_id)
        assert insp is not None
        assert len(insp.captures) == 1
        assert insp.captures[0].capture_id == cap_id
        
        # 2. Retrieve Report
        rep_db = InspectionRepository.get_report_snapshot(session, rep_id)
        assert rep_db is not None
        assert rep_db.snapshot_payload["evidence_assets"][0]["image_b64"] is None
        
        # 3. Retrieve Object from MinIO
        obj_key = insp.captures[0].object_key
        img_bytes = default_storage_adapter.retrieve(obj_key)
        assert img_bytes is not None
        
        # 4. Verify SHA-256
        actual_sha = hashlib.sha256(img_bytes).hexdigest()
        assert actual_sha == insp.captures[0].image_sha256
        
        # 5. Regenerate PDF & DOCX from Snapshot + Hydrated Image
        snapshot = InspectionReportSnapshot.model_validate(rep_db.snapshot_payload)
        snapshot.evidence_assets[0].image_b64 = base64.b64encode(img_bytes).decode("ascii")
        
        pdf_bytes = generate_pdf_report(snapshot)
        docx_bytes = generate_docx_report(snapshot)
        
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) >= 1
        
        doc = Document(io.BytesIO(docx_bytes))
        assert len(doc.inline_shapes) >= 1
        
        print("VERIFY_AFTER_RESTART_SUCCESS: PDF size=", len(pdf_bytes), "DOCX size=", len(docx_bytes))
    finally:
        session.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify_after_restart()
    else:
        stage_data()
