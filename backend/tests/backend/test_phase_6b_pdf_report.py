import io
import pytest
import pypdf
from datetime import date
from app.schemas.ocr import (
    FieldCandidate,
    MrpNormalized,
    NetQuantityNormalized,
    DateNormalized,
    ConsumerCareNormalized
)
from app.schemas.image_quality import ImageQualityAssessment
from app.schemas.inspection import (
    InspectionSession,
    CaptureRecord,
    CapturePlan,
    CaptureViewRequirement
)
from app.schemas.compliance import LegalStatus, RuleEvaluationResult
from app.schemas.applicability import ApplicabilityDecision, ApplicabilityStatus
from app.schemas.visual_assessment import (
    VisualCheckCapability,
    VisualObservationStatus,
    VisualRuleEvaluationResult
)
from app.schemas.report import OverallDisposition, InspectionReportSnapshot
from app.services.report_service import generate_inspection_report
from app.services.pdf_report_service import generate_pdf_report

TEST_PLAN = CapturePlan(
    capture_plan_id="plan_software_1",
    name="Standard Software Inspection",
    views=[
        CaptureViewRequirement(view_id="FRONT", display_name="Front View", required=True),
        CaptureViewRequirement(view_id="BACK", display_name="Back View", required=True)
    ],
    absence_evaluation_eligible=True
)

def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def test_1_and_2_valid_pdf_generation_and_magic_header():
    # 1 & 2. Valid PDF generation and %PDF header
    rule1 = RuleEvaluationResult(
        rule_id="MRP_DECLARATION_PRESENCE",
        rule_version="1.0",
        field="MRP",
        status=LegalStatus.PASS,
        reason="MRP declaration present and valid.",
        source_reference="Rule 6(1)(e)",
        reference_date=date(2025, 1, 1),
        applicability=ApplicabilityDecision(rule_id="MRP_DECLARATION_PRESENCE", status=ApplicabilityStatus.APPLICABLE, reason="Applicable"),
        evidence_ids=["ev_mrp"]
    )
    
    session = InspectionSession(
        inspection_id="sess_pdf_01",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        rule_evaluations=[rule1],
        visual_rule_evaluations=[],
        captures=[
            CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED"),
            CaptureRecord(capture_id="c2", view_id="BACK", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    snapshot = generate_inspection_report(session, TEST_PLAN)
    pdf_bytes = generate_pdf_report(snapshot)
    
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")
    
    text = extract_pdf_text(pdf_bytes)
    assert "DRISHTI: PACKAGED COMMODITY INSPECTION REPORT" in text

def test_3_and_4_report_id_and_exact_disposition_rendering():
    # 3 & 4. Report ID, Inspection ID, and exact overall disposition
    rule_fail = RuleEvaluationResult(
        rule_id="MONTH_YEAR_DECLARATION_PRESENCE",
        rule_version="1.0",
        field="MONTH_YEAR",
        status=LegalStatus.FAIL,
        reason="Required date of manufacture missing across complete captures.",
        source_reference="Rule 6(1)(d)",
        reference_date=date(2025, 1, 1),
        applicability=ApplicabilityDecision(rule_id="MONTH_YEAR_DECLARATION_PRESENCE", status=ApplicabilityStatus.APPLICABLE, reason="Applicable"),
        evidence_ids=[]
    )
    
    session = InspectionSession(
        inspection_id="sess_fail_pdf_test",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        rule_evaluations=[rule_fail],
        visual_rule_evaluations=[],
        captures=[
            CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED"),
            CaptureRecord(capture_id="c2", view_id="BACK", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    snapshot = generate_inspection_report(session, TEST_PLAN)
    pdf_bytes = generate_pdf_report(snapshot)
    text = extract_pdf_text(pdf_bytes)
    
    assert snapshot.overall_disposition == OverallDisposition.VIOLATIONS_FOUND
    assert "OVERALL DISPOSITION: VIOLATIONS FOUND" in text
    assert "sess_fail_pdf_test" in text
    assert snapshot.metadata.report_id in text

def test_5_incomplete_inspection_disposition_rendered():
    # 5. Incomplete inspection clearly rendered
    session = InspectionSession(
        inspection_id="sess_incomp_pdf",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="INCOMPLETE_INSPECTION",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        rule_evaluations=[],
        visual_rule_evaluations=[],
        captures=[
            CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    snapshot = generate_inspection_report(session, TEST_PLAN)
    pdf_bytes = generate_pdf_report(snapshot)
    text = extract_pdf_text(pdf_bytes)
    
    assert snapshot.overall_disposition == OverallDisposition.INCOMPLETE_INSPECTION
    assert "OVERALL DISPOSITION: INCOMPLETE INSPECTION" in text

def test_6_and_7_review_required_distinct_from_fail():
    # 6 & 7. REVIEW_REQUIRED rendered distinctly from FAIL
    rule_rev = RuleEvaluationResult(
        rule_id="NET_QUANTITY_DECLARATION_PRESENCE",
        rule_version="1.0",
        field="NET_QUANTITY",
        status=LegalStatus.REVIEW_REQUIRED,
        reason="Unparsed unit declaration requires inspector confirmation.",
        source_reference="Rule 6(1)(f)",
        reference_date=date(2025, 1, 1),
        applicability=ApplicabilityDecision(rule_id="NET_QUANTITY_DECLARATION_PRESENCE", status=ApplicabilityStatus.APPLICABLE, reason="Applicable"),
        evidence_ids=["ev_nq_low"]
    )
    
    session = InspectionSession(
        inspection_id="sess_rev_pdf",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        rule_evaluations=[rule_rev],
        visual_rule_evaluations=[],
        captures=[
            CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED"),
            CaptureRecord(capture_id="c2", view_id="BACK", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    snapshot = generate_inspection_report(session, TEST_PLAN)
    pdf_bytes = generate_pdf_report(snapshot)
    text = extract_pdf_text(pdf_bytes)
    
    assert snapshot.overall_disposition == OverallDisposition.REVIEW_REQUIRED
    assert "OVERALL DISPOSITION: REVIEW REQUIRED" in text

def test_8_and_9_visual_findings_and_not_applicable():
    # 8 & 9. NOT_APPLICABLE and Visual findings separate
    rule_na = RuleEvaluationResult(
        rule_id="MONTH_YEAR_DECLARATION_PRESENCE",
        rule_version="1.0",
        field="MONTH_YEAR",
        status=LegalStatus.NOT_APPLICABLE,
        reason="Food item date rules deferred.",
        source_reference="Rule 6(1)(d)",
        reference_date=date(2025, 1, 1),
        applicability=ApplicabilityDecision(rule_id="MONTH_YEAR_DECLARATION_PRESENCE", status=ApplicabilityStatus.NOT_APPLICABLE, reason="Food item"),
        evidence_ids=[]
    )
    
    vrule_r7 = VisualRuleEvaluationResult(
        rule_id="RULE_7_MINIMUM_NUMERAL_HEIGHT",
        field="NET_QUANTITY",
        capability=VisualCheckCapability.NOT_EVALUABLE_FROM_CURRENT_CAPTURE,
        status=VisualObservationStatus.NOT_EVALUABLE,
        reason="2D photography without physical calibration target.",
        legal_reference="Legal Metrology Rules, 2011 Rule 7",
        limitations="Cannot evaluate physical millimeters from uncalibrated 2D optical photo."
    )
    
    session = InspectionSession(
        inspection_id="sess_na_vis_pdf",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        rule_evaluations=[rule_na],
        visual_rule_evaluations=[vrule_r7],
        captures=[
            CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED"),
            CaptureRecord(capture_id="c2", view_id="BACK", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    snapshot = generate_inspection_report(session, TEST_PLAN)
    pdf_bytes = generate_pdf_report(snapshot)
    text = extract_pdf_text(pdf_bytes)
    
    assert "NOT APPLICABLE" in text
    assert "RULE 7 MINIMUM NUMERAL HEIGHT" in text or "Rule 7" in text
    assert "NOT EVALUABLE" in text

def test_10_and_11_unknown_context_and_legal_references():
    # 10 & 11. UNKNOWN context rendered honestly and legal references preserved
    session = InspectionSession(
        inspection_id="sess_unknown_pdf",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin="UNKNOWN",
        regulatory_product_class="UNKNOWN",
        date_regulatory_regime="UNKNOWN",
        date_package_exemption="UNKNOWN",
        is_electronic="UNKNOWN",
        package_structure="UNKNOWN",
        alcohol_context="UNKNOWN",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        rule_evaluations=[],
        visual_rule_evaluations=[],
        captures=[
            CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED"),
            CaptureRecord(capture_id="c2", view_id="BACK", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    snapshot = generate_inspection_report(session, TEST_PLAN)
    pdf_bytes = generate_pdf_report(snapshot)
    text = extract_pdf_text(pdf_bytes)
    
    assert "Unknown / Not established" in text

def test_12_snapshot_is_not_recomputed_determinism():
    # 12. Snapshot data is purely presented without alteration
    rule = RuleEvaluationResult(
        rule_id="MRP_DECLARATION_PRESENCE",
        rule_version="1.0",
        field="MRP",
        status=LegalStatus.PASS,
        reason="Deterministic statutory test reason.",
        source_reference="Rule 6(1)(e)",
        reference_date=date(2025, 1, 1),
        applicability=ApplicabilityDecision(rule_id="MRP_DECLARATION_PRESENCE", status=ApplicabilityStatus.APPLICABLE, reason="Applicable"),
        evidence_ids=["ev_1"]
    )
    
    session = InspectionSession(
        inspection_id="sess_det_pdf",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        rule_evaluations=[rule],
        visual_rule_evaluations=[],
        captures=[
            CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED"),
            CaptureRecord(capture_id="c2", view_id="BACK", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    snapshot = generate_inspection_report(session, TEST_PLAN)
    pdf1 = generate_pdf_report(snapshot)
    pdf2 = generate_pdf_report(snapshot)
    
    text1 = extract_pdf_text(pdf1)
    text2 = extract_pdf_text(pdf2)
    assert text1 == text2

def test_13_and_14_no_arbitrary_score_and_no_fully_compliant_substitution():
    # 13 & 14. Confirm no compliance score or "fully compliant" in PDF
    session = InspectionSession(
        inspection_id="sess_safe_pdf",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        rule_evaluations=[],
        visual_rule_evaluations=[],
        captures=[
            CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED"),
            CaptureRecord(capture_id="c2", view_id="BACK", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    snapshot = generate_inspection_report(session, TEST_PLAN)
    pdf_bytes = generate_pdf_report(snapshot)
    text = extract_pdf_text(pdf_bytes)
    
    assert "FULLY COMPLIANT" not in text
    assert "100% COMPLIANT" not in text
    assert "Compliance Score" not in text
    assert "Compliance Percentage" not in text
    assert "score" not in text.lower()

def test_15_and_16_multipage_and_long_strings_safety():
    # 15 & 16. Multipage generation with very long strings
    long_reason = "Detailed examination of the package declaration demonstrates that " * 20
    long_rule = RuleEvaluationResult(
        rule_id="MANUFACTURER_DECLARATION_PRESENCE",
        rule_version="1.0",
        field="MANUFACTURER_PACKER_IMPORTER",
        status=LegalStatus.PASS,
        reason=long_reason,
        source_reference="Legal Metrology Rules, 2011 Rule 6(1)(a)",
        reference_date=date(2025, 1, 1),
        applicability=ApplicabilityDecision(rule_id="MANUFACTURER_DECLARATION_PRESENCE", status=ApplicabilityStatus.APPLICABLE, reason="Applicable"),
        evidence_ids=["ev_long_1", "ev_long_2"]
    )
    
    cand = FieldCandidate(
        field="MANUFACTURER_PACKER_IMPORTER",
        status="DETECTED",
        raw_value="Manufactured by: Very Long Generic Manufacturing Company Private Limited, Industrial Area, Sector 62, Complex Building, Floor 4, Bangalore 560001, Karnataka, India",
        normalized_value={"role": "MANUFACTURER", "name": "Very Long Generic Manufacturing Company", "address": "Bangalore 560001", "pin_code": "560001"},
        evidence_ids=["ev_long_1"]
    )
    
    session = InspectionSession(
        inspection_id="sess_multipage_pdf",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        aggregated_candidates=[cand],
        rule_evaluations=[long_rule] * 5,
        visual_rule_evaluations=[],
        captures=[
            CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED"),
            CaptureRecord(capture_id="c2", view_id="BACK", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    snapshot = generate_inspection_report(session, TEST_PLAN)
    pdf_bytes = generate_pdf_report(snapshot)
    
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 2
    assert pdf_bytes.startswith(b"%PDF-")
