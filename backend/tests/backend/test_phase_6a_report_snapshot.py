import pytest
from datetime import date
from app.schemas.ocr import (
    OcrLine,
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
from app.services.report_service import generate_inspection_report, compute_overall_disposition
from app.api.routes.inspections import _update_session_compliance

TEST_PLAN = CapturePlan(
    capture_plan_id="plan_software_1",
    name="Standard Software Inspection",
    views=[
        CaptureViewRequirement(view_id="FRONT", display_name="Front View", required=True),
        CaptureViewRequirement(view_id="BACK", display_name="Back View", required=True),
        CaptureViewRequirement(view_id="BOTTOM", display_name="Bottom View", required=False)
    ],
    absence_evaluation_eligible=True
)

def test_1_complete_inspection_no_violations():
    # 1. Complete inspection with all PASS/NOT_APPLICABLE -> NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE
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
        inspection_id="sess_pass_6a",
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
    
    report = generate_inspection_report(session, TEST_PLAN)
    
    assert report.overall_disposition == OverallDisposition.NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE
    assert report.summary_counts.statutory_pass_count == 1
    assert report.summary_counts.statutory_fail_count == 0
    assert report.summary_counts.statutory_review_required_count == 0
    assert report.capture_summary.captured_required_count == 2
    assert len(report.capture_summary.missing_required_views) == 0

def test_2_incomplete_inspection_disposition():
    # 2. Incomplete inspection -> INCOMPLETE_INSPECTION
    rule1 = RuleEvaluationResult(
        rule_id="MRP_DECLARATION_PRESENCE",
        rule_version="1.0",
        field="MRP",
        status=LegalStatus.REVIEW_REQUIRED,
        reason="Insufficient capture coverage.",
        reference_date=date(2025, 1, 1),
        applicability=ApplicabilityDecision(rule_id="MRP_DECLARATION_PRESENCE", status=ApplicabilityStatus.APPLICABLE, reason="Applicable"),
        evidence_ids=[]
    )
    
    session = InspectionSession(
        inspection_id="sess_incomp_6a",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="INCOMPLETE_INSPECTION",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        rule_evaluations=[rule1],
        visual_rule_evaluations=[],
        captures=[
            CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    report = generate_inspection_report(session, TEST_PLAN)
    assert report.overall_disposition == OverallDisposition.INCOMPLETE_INSPECTION
    assert "BACK" in report.capture_summary.missing_required_views

def test_3_violations_found_precedence():
    # 3. Statutory violation present -> VIOLATIONS_FOUND (dominates even when incomplete or review items exist)
    rule_fail = RuleEvaluationResult(
        rule_id="MONTH_YEAR_DECLARATION_PRESENCE",
        rule_version="1.0",
        field="MONTH_YEAR",
        status=LegalStatus.FAIL,
        reason="Required declaration missing or illegal format.",
        reference_date=date(2025, 1, 1),
        applicability=ApplicabilityDecision(rule_id="MONTH_YEAR_DECLARATION_PRESENCE", status=ApplicabilityStatus.APPLICABLE, reason="Applicable"),
        evidence_ids=[]
    )
    
    session = InspectionSession(
        inspection_id="sess_fail_6a",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="INCOMPLETE_INSPECTION",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        rule_evaluations=[rule_fail],
        visual_rule_evaluations=[],
        captures=[
            CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    report = generate_inspection_report(session, TEST_PLAN)
    assert report.overall_disposition == OverallDisposition.VIOLATIONS_FOUND
    assert report.summary_counts.statutory_fail_count == 1
    assert "MONTH_YEAR_DECLARATION_PRESENCE" in report.disposition_reason

def test_4_review_required_on_complete_inspection():
    # 4. Review required present on complete inspection -> REVIEW_REQUIRED
    rule_rev = RuleEvaluationResult(
        rule_id="MRP_DECLARATION_PRESENCE",
        rule_version="1.0",
        field="MRP",
        status=LegalStatus.REVIEW_REQUIRED,
        reason="Low confidence detection requires inspector verification.",
        reference_date=date(2025, 1, 1),
        applicability=ApplicabilityDecision(rule_id="MRP_DECLARATION_PRESENCE", status=ApplicabilityStatus.APPLICABLE, reason="Applicable"),
        evidence_ids=["ev_low"]
    )
    
    session = InspectionSession(
        inspection_id="sess_rev_6a",
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
    
    report = generate_inspection_report(session, TEST_PLAN)
    assert report.overall_disposition == OverallDisposition.REVIEW_REQUIRED
    assert report.summary_counts.statutory_review_required_count == 1

def test_5_not_applicable_and_visual_findings_separation():
    # 5 & 6. NOT_APPLICABLE handling and Visual findings separated from statutory findings
    rule_na = RuleEvaluationResult(
        rule_id="MONTH_YEAR_DECLARATION_PRESENCE",
        rule_version="1.0",
        field="MONTH_YEAR",
        status=LegalStatus.NOT_APPLICABLE,
        reason="Food item date rules deferred.",
        reference_date=date(2025, 1, 1),
        applicability=ApplicabilityDecision(rule_id="MONTH_YEAR_DECLARATION_PRESENCE", status=ApplicabilityStatus.NOT_APPLICABLE, reason="Food item"),
        evidence_ids=[]
    )
    
    vrule_r7 = VisualRuleEvaluationResult(
        rule_id="RULE_7_MINIMUM_NUMERAL_HEIGHT",
        field="NET_QUANTITY",
        capability=VisualCheckCapability.NOT_EVALUABLE_FROM_CURRENT_CAPTURE,
        status=VisualObservationStatus.NOT_EVALUABLE,
        reason="2D photography without physical scale.",
        legal_reference="Rule 7",
        limitations="Requires physical measurement"
    )
    
    vrule_r8 = VisualRuleEvaluationResult(
        rule_id="RULE_8_NET_QUANTITY_SURROUNDING_CLEARANCE",
        field="NET_QUANTITY",
        capability=VisualCheckCapability.INSPECTOR_REVIEW_ONLY,
        status=VisualObservationStatus.REVIEW_REQUIRED,
        reason="Proxy line height clearance.",
        legal_reference="Rule 8",
        limitations="Line height proxy used"
    )
    
    session = InspectionSession(
        inspection_id="sess_vis_6a",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        rule_evaluations=[rule_na],
        visual_rule_evaluations=[vrule_r7, vrule_r8],
        captures=[
            CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED"),
            CaptureRecord(capture_id="c2", view_id="BACK", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    report = generate_inspection_report(session, TEST_PLAN)
    
    assert report.summary_counts.statutory_not_applicable_count == 1
    assert report.summary_counts.total_visual_checks == 2
    assert report.summary_counts.visual_not_evaluable_count == 1
    assert report.summary_counts.visual_review_required_count == 1
    # Visual review triggers overall REVIEW_REQUIRED on complete session
    assert report.overall_disposition == OverallDisposition.REVIEW_REQUIRED

def test_6_provenance_and_explicit_unknown_context_preservation():
    # 7 & 8. Provenance and explicit UNKNOWN context preserved
    mrp_cand = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs. 99.00",
        normalized_value=MrpNormalized(amount=99.0, currency="INR"),
        confidence=0.97,
        evidence_ids=["ev_mrp_99"],
        capture_ids=["cap_front_01"]
    )
    
    session = InspectionSession(
        inspection_id="sess_prov_6a",
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
        aggregated_candidates=[mrp_cand],
        captures=[
            CaptureRecord(capture_id="cap_front_01", view_id="FRONT", evidence_id="ev_mrp_99", image_sha256="abc123sha", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    report = generate_inspection_report(session, TEST_PLAN)
    
    # Check context snapshot
    assert report.inspector_context.product_origin == "UNKNOWN"
    assert report.inspector_context.regulatory_product_class == "UNKNOWN"
    assert report.inspector_context.date_regulatory_regime == "UNKNOWN"
    
    # Check extracted evidence provenance
    assert len(report.extracted_evidence) == 1
    ev_item = report.extracted_evidence[0]
    assert ev_item.field == "MRP"
    assert "ev_mrp_99" in ev_item.evidence_ids
    assert "cap_front_01" in ev_item.capture_ids
    assert "FRONT" in ev_item.view_ids
    assert ev_item.normalized_value == {"currency": "INR", "amount": 99.0}

def test_7_immutability_of_generated_snapshot():
    # 9. Modifying session after generation does not alter the generated snapshot
    session = InspectionSession(
        inspection_id="sess_imm_6a",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        capture_status="INCOMPLETE_INSPECTION",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        rule_evaluations=[],
        captures=[]
    )
    
    report = generate_inspection_report(session, TEST_PLAN)
    assert report.capture_summary.capture_status == "INCOMPLETE_INSPECTION"
    assert report.overall_disposition == OverallDisposition.INCOMPLETE_INSPECTION
    
    # Mutate the session
    session.capture_status = "COMPLETE_EVIDENCE_CAPTURE"
    session.product_origin = "IMPORTED"
    
    # The generated snapshot must remain unchanged
    assert report.capture_summary.capture_status == "INCOMPLETE_INSPECTION"
    assert report.inspector_context.product_origin == "UNKNOWN"
    assert report.overall_disposition == OverallDisposition.INCOMPLETE_INSPECTION

def test_8_no_arbitrary_compliance_score():
    # 10. Confirm no arbitrary compliance percentage or score is exposed in the schema
    report_dict = InspectionReportSnapshot.model_json_schema()
    props = report_dict.get("properties", {})
    assert "score" not in props
    assert "compliance_percentage" not in props
    assert "overall_score" not in props
