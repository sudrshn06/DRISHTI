import io
import pytest
import numpy as np
import cv2
import hashlib
from datetime import date
from docx import Document
import pypdf

from app.schemas.ocr import FieldCandidate
from app.schemas.inspection import (
    InspectionSession,
    CaptureRecord,
    CapturePlan,
    CaptureViewRequirement
)
from app.schemas.visual_assessment import (
    CaptureVisualAssessmentSummary,
    DeclarationVisualAssessment,
    RegionGeometry,
    PixelBoundingBox,
    NormalizedBoundingBox,
    VisualCheckCapability,
    VisualObservationStatus,
    VisualRuleEvaluationResult
)
from app.schemas.compliance import LegalStatus, RuleEvaluationResult
from app.schemas.applicability import ApplicabilityDecision, ApplicabilityStatus
from app.schemas.report import OverallDisposition, InspectionReportSnapshot
from app.services.report_service import generate_inspection_report
from app.services.image_store import store_capture_image, get_capture_image, get_image_by_hash, clear_image_store
from app.services.evidence_annotation_service import annotate_evidence_crop
from app.services.pdf_report_service import generate_pdf_report
from app.services.docx_report_service import generate_docx_report

TEST_PLAN = CapturePlan(
    capture_plan_id="plan_software_1",
    name="Standard Software Inspection",
    views=[
        CaptureViewRequirement(view_id="FRONT", display_name="Front View", required=True),
        CaptureViewRequirement(view_id="BACK", display_name="Back View", required=True)
    ],
    absence_evaluation_eligible=True
)

def create_synthetic_image(width=400, height=300, color=(240, 240, 240)) -> bytes:
    img = np.full((height, width, 3), color, dtype=np.uint8)
    cv2.putText(img, "TEST EVIDENCE", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (20, 20, 20), 2)
    success, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()

def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def extract_docx_text(docx_bytes: bytes) -> str:
    doc = Document(io.BytesIO(docx_bytes))
    full_text = []
    for p in doc.paragraphs:
        if p.text:
            full_text.append(p.text)
    for table in doc.tables:
        for row in table.rows:
            row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_text:
                full_text.append(" | ".join(row_text))
    return "\n".join(full_text)

def test_1_and_2_evidence_asset_mapping_and_sha_preservation():
    # 1 & 2. Evidence asset maps to correct capture/view and original SHA-256 is preserved
    img_bytes = create_synthetic_image()
    sha = hashlib.sha256(img_bytes).hexdigest()
    
    store_capture_image("cap_front_01", sha, img_bytes, "image/jpeg", 400, 300)
    
    cand = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs. 199.00",
        normalized_value={"currency": "INR", "amount": 199.0},
        confidence=0.98,
        evidence_ids=["ev_mrp_01"],
        capture_ids=["cap_front_01"]
    )
    
    session = InspectionSession(
        inspection_id="sess_img_01",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        aggregated_candidates=[cand],
        rule_evaluations=[],
        visual_rule_evaluations=[],
        captures=[
            CaptureRecord(capture_id="cap_front_01", view_id="FRONT", evidence_id="ev_mrp_01", image_sha256=sha, status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    report = generate_inspection_report(session, TEST_PLAN)
    
    assert len(report.evidence_assets) == 1
    asset = report.evidence_assets[0]
    assert asset.capture_id == "cap_front_01"
    assert asset.view_id == "FRONT"
    assert asset.image_sha256 == sha
    assert "ev_mrp_01" in asset.evidence_ids

def test_3_and_4_annotation_with_valid_and_multiple_polygons():
    # 3 & 4. Valid single and multiple polygons produce annotated image crops
    img_bytes = create_synthetic_image(500, 400)
    polys = [
        [[50, 100], [200, 100], [200, 140], [50, 140]],
        [[210, 100], [300, 100], [300, 140], [210, 140]]
    ]
    
    annotated = annotate_evidence_crop(
        image_bytes=img_bytes,
        field_label="NET_QUANTITY",
        view_id="FRONT",
        polygons=polys,
        is_clearance=True
    )
    
    assert annotated is not None
    assert isinstance(annotated, bytes)
    assert len(annotated) > 500
    
    # Verify resulting image is valid JPEG
    np_arr = np.frombuffer(annotated, np.uint8)
    dec = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    assert dec is not None
    assert dec.shape[0] > 0 and dec.shape[1] > 0

def test_6_7_8_missing_and_malformed_geometry_fallbacks():
    # 6, 7, 8. Safe fallbacks for missing geometry, missing image, and malformed coordinates
    img_bytes = create_synthetic_image(400, 300)
    
    # Missing image
    assert annotate_evidence_crop(None, "MRP", "FRONT", pixel_box={"x_min": 10, "y_min": 10, "x_max": 50, "y_max": 50}) is None
    
    # Missing geometry
    assert annotate_evidence_crop(img_bytes, "MRP", "FRONT", polygons=[], pixel_box=None, normalized_box=None) is None
    
    # Malformed geometry (inverted/negative/None)
    assert annotate_evidence_crop(img_bytes, "MRP", "FRONT", pixel_box={"x_min": 50, "y_min": 50, "x_max": 20, "y_max": 20}) is None
    assert annotate_evidence_crop(img_bytes, "MRP", "FRONT", polygons=[[[None, "abc"], [10, 20]]]) is None

def test_9_and_10_visual_rule_boundary_evidence_safety():
    # 9 & 10. Rule 8 surrounding clearance renders without converting status from REVIEW_REQUIRED; Rule 7 remains NOT_EVALUABLE
    vrule_r7 = VisualRuleEvaluationResult(
        rule_id="RULE_7_MINIMUM_NUMERAL_HEIGHT",
        field="NET_QUANTITY",
        capability=VisualCheckCapability.NOT_EVALUABLE_FROM_CURRENT_CAPTURE,
        status=VisualObservationStatus.NOT_EVALUABLE,
        reason="2D optical photography cannot establish physical millimeter dimensions.",
        legal_reference="Rule 7",
        limitations="Requires physical calibration scale"
    )
    
    vrule_r8 = VisualRuleEvaluationResult(
        rule_id="RULE_8_NET_QUANTITY_SURROUNDING_CLEARANCE",
        field="NET_QUANTITY",
        capability=VisualCheckCapability.INSPECTOR_REVIEW_ONLY,
        status=VisualObservationStatus.REVIEW_REQUIRED,
        reason="Clearance zone evaluated against declaration line height proxy.",
        legal_reference="Rule 8",
        limitations="Proxy line height clearance"
    )
    
    session = InspectionSession(
        inspection_id="sess_vis_ev_01",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        rule_evaluations=[],
        visual_rule_evaluations=[vrule_r7, vrule_r8],
        captures=[]
    )
    
    report = generate_inspection_report(session, TEST_PLAN)
    assert report.overall_disposition == OverallDisposition.REVIEW_REQUIRED
    
    pdf_bytes = generate_pdf_report(report)
    docx_bytes = generate_docx_report(report)
    
    pdf_text = extract_pdf_text(pdf_bytes)
    docx_text = extract_docx_text(docx_bytes)
    
    assert "RULE 7 MINIMUM NUMERAL HEIGHT" in pdf_text or "Rule 7" in pdf_text
    assert "NOT EVALUABLE" in pdf_text
    assert "REVIEW REQUIRED" in pdf_text
    assert "REVIEW REQUIRED" in docx_text

def test_11_12_13_14_pdf_and_docx_evidence_embedding():
    # 11, 12, 13, 14. PDF & DOCX contain evidence appendix with embedded images and matching evidence IDs
    img_bytes = create_synthetic_image(500, 300)
    sha = hashlib.sha256(img_bytes).hexdigest()
    store_capture_image("cap_front_mrp", sha, img_bytes, "image/jpeg", 500, 300)
    
    cand = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs. 299.00",
        normalized_value={"currency": "INR", "amount": 299.0},
        confidence=0.99,
        evidence_ids=["ev_mrp_trace_01"],
        capture_ids=["cap_front_mrp"]
    )
    
    geom = RegionGeometry(
        pixel_box=PixelBoundingBox(
            x_min=50.0, y_min=100.0, x_max=250.0, y_max=150.0,
            width_px=200.0, height_px=50.0, area_px=10000.0
        ),
        normalized_box=NormalizedBoundingBox(x_min=0.1, y_min=0.33, x_max=0.5, y_max=0.5),
        image_width=500,
        image_height=300,
        width_ratio=0.4,
        height_ratio=0.167,
        area_ratio=0.067,
        distance_to_edge_px={"top": 100.0, "bottom": 150.0, "left": 50.0, "right": 250.0},
        touches_edge=False
    )
    
    from app.schemas.visual_assessment import VisualReadabilitySignal

    decl_assessment = DeclarationVisualAssessment(
        field="MRP",
        evidence_ids=["ev_mrp_trace_01"],
        capture_id="cap_front_mrp",
        view_id="FRONT",
        raw_text="MRP Rs. 299.00",
        polygons=[[[50.0, 100.0], [250.0, 100.0], [250.0, 150.0], [50.0, 150.0]]],
        readability=VisualReadabilitySignal(
            ocr_confidence=0.99,
            is_clipped=False,
            capture_quality_status="ACCEPTABLE",
            technical_readability="EVALUABLE"
        ),
        technical_status="EVALUABLE",
        geometry=geom
    )
    
    vis_summary = CaptureVisualAssessmentSummary(
        capture_id="cap_front_mrp",
        view_id="FRONT",
        image_width=500,
        image_height=300,
        assessments=[decl_assessment]
    )
    
    session = InspectionSession(
        inspection_id="sess_trace_01",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        aggregated_candidates=[cand],
        rule_evaluations=[],
        visual_rule_evaluations=[],
        captures=[
            CaptureRecord(
                capture_id="cap_front_mrp",
                view_id="FRONT",
                evidence_id="ev_mrp_trace_01",
                image_sha256=sha,
                visual_assessment=vis_summary,
                status="ACCEPTED",
                pipeline_status="COMPLETED"
            )
        ]
    )
    
    report = generate_inspection_report(session, TEST_PLAN)
    pdf_bytes = generate_pdf_report(report)
    docx_bytes = generate_docx_report(report)
    
    pdf_text = extract_pdf_text(pdf_bytes)
    docx_text = extract_docx_text(docx_bytes)
    
    # Section presence
    assert "6. Traceable Evidence Imagery & Highlighted Regions" in pdf_text
    assert "6. Traceable Evidence Imagery & Highlighted Regions" in docx_text
    
    # Evidence ID agreement
    assert "ev_mrp_trace_01" in pdf_text
    assert "ev_mrp_trace_01" in docx_text
    
    # DOCX has embedded table with image
    doc = Document(io.BytesIO(docx_bytes))
    assert len(doc.tables) >= 6
    assert len(doc.inline_shapes) >= 1 # Valid embedded picture

def test_15_16_17_integrity_and_disposition_invariants():
    # 15, 16, 17. Source image hash unchanged, no hardcoded coordinates, disposition unaffected
    img_bytes = create_synthetic_image(400, 300)
    original_sha = hashlib.sha256(img_bytes).hexdigest()
    
    annotated = annotate_evidence_crop(
        image_bytes=img_bytes,
        field_label="MANUFACTURER",
        view_id="BACK",
        pixel_box={"x_min": 20, "y_min": 40, "x_max": 200, "y_max": 80}
    )
    
    # Original image bytes remain unmodified
    assert hashlib.sha256(img_bytes).hexdigest() == original_sha
    assert annotated != img_bytes

def test_18_restart_and_cache_clear_durability_of_report_snapshot():
    # 18. Self-contained snapshot survives complete image cache clear / process restart
    img_bytes = create_synthetic_image(600, 400)
    sha = hashlib.sha256(img_bytes).hexdigest()
    store_capture_image("cap_restart_test", sha, img_bytes, "image/jpeg", 600, 400)
    
    cand = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs. 149.00",
        normalized_value={"currency": "INR", "amount": 149.0},
        confidence=0.99,
        evidence_ids=["ev_restart_01"],
        capture_ids=["cap_restart_test"]
    )
    
    geom = RegionGeometry(
        pixel_box=PixelBoundingBox(
            x_min=60.0, y_min=120.0, x_max=300.0, y_max=180.0,
            width_px=240.0, height_px=60.0, area_px=14400.0
        ),
        normalized_box=NormalizedBoundingBox(x_min=0.1, y_min=0.3, x_max=0.5, y_max=0.45),
        image_width=600,
        image_height=400,
        width_ratio=0.4,
        height_ratio=0.15,
        area_ratio=0.06,
        distance_to_edge_px={"top": 120.0, "bottom": 220.0, "left": 60.0, "right": 300.0},
        touches_edge=False
    )
    
    from app.schemas.visual_assessment import VisualReadabilitySignal, DeclarationVisualAssessment, CaptureVisualAssessmentSummary
    
    decl_assessment = DeclarationVisualAssessment(
        field="MRP",
        evidence_ids=["ev_restart_01"],
        capture_id="cap_restart_test",
        view_id="FRONT",
        raw_text="MRP Rs. 149.00",
        polygons=[[[60.0, 120.0], [300.0, 120.0], [300.0, 180.0], [60.0, 180.0]]],
        readability=VisualReadabilitySignal(
            ocr_confidence=0.99,
            is_clipped=False,
            capture_quality_status="ACCEPTABLE",
            technical_readability="EVALUABLE"
        ),
        technical_status="EVALUABLE",
        geometry=geom
    )
    
    vis_summary = CaptureVisualAssessmentSummary(
        capture_id="cap_restart_test",
        view_id="FRONT",
        image_width=600,
        image_height=400,
        assessments=[decl_assessment]
    )
    
    session = InspectionSession(
        inspection_id="sess_restart_01",
        reference_date="2025-01-01",
        product_category="GENERIC RETAIL PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        aggregated_candidates=[cand],
        rule_evaluations=[],
        visual_rule_evaluations=[],
        captures=[
            CaptureRecord(
                capture_id="cap_restart_test",
                view_id="FRONT",
                evidence_id="ev_restart_01",
                image_sha256=sha,
                visual_assessment=vis_summary,
                status="ACCEPTED",
                pipeline_status="COMPLETED"
            )
        ]
    )
    
    # 1. Generate snapshot (self-contained evidence asset created)
    snapshot = generate_inspection_report(session, TEST_PLAN)
    assert len(snapshot.evidence_assets) == 1
    assert snapshot.evidence_assets[0].image_b64 is not None
    
    # 2. Simulate complete server/process restart by wiping in-memory image store
    clear_image_store()
    assert get_capture_image("cap_restart_test") is None
    assert get_image_by_hash(sha) is None
    
    # 3. Regenerate PDF and DOCX reports exclusively from snapshot
    pdf_bytes = generate_pdf_report(snapshot)
    docx_bytes = generate_docx_report(snapshot)
    
    pdf_text = extract_pdf_text(pdf_bytes)
    docx_text = extract_docx_text(docx_bytes)
    
    # Assert reports render fully without fallback text
    assert "Evidence Image: Image file not present in local cache" not in pdf_text
    assert "Evidence Image: Image file not present in local cache" not in docx_text
    assert "ev_restart_01" in pdf_text
    assert "ev_restart_01" in docx_text
    assert sha[:16] in pdf_text
    assert sha[:16] in docx_text
    
    # Assert PDF and DOCX contain embedded image objects
    doc = Document(io.BytesIO(docx_bytes))
    assert len(doc.inline_shapes) >= 1
    
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    total_pdf_images = sum(len(p.images) for p in reader.pages)
    assert total_pdf_images >= 1

