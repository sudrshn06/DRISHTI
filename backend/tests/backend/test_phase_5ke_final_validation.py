import pytest
from datetime import date
from app.schemas.ocr import (
    OcrLine,
    FieldCandidate,
    MrpNormalized,
    NetQuantityNormalized,
    DateNormalized,
    ConsumerCareNormalized,
    CountryOfOriginNormalized,
    CommonGenericNameNormalized,
    UnitSalePriceNormalized
)
from app.schemas.image_quality import ImageQualityAssessment
from app.schemas.inspection import InspectionSession, CaptureRecord, CapturePlan, CaptureViewRequirement
from app.schemas.compliance import LegalStatus
from app.schemas.visual_assessment import (
    VisualCheckCapability,
    VisualObservationStatus,
    VisualCheckType
)
from app.services.compliance_service import orchestrate_compliance
from app.services.visual_assessment_service import (
    assess_capture_visuals,
    evaluate_visual_legal_rules
)
from app.services.inspection_service import (
    aggregate_candidates,
    evaluate_completeness,
    evaluate_evidence_sufficiency
)
from app.api.routes.inspections import _update_session_compliance, compute_active_clarification

# Prototype software capture plan
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

def test_scenario_a_non_food_package_with_valid_mfd_2024():
    """Scenario A: NON_FOOD package with valid MFD evaluated in 2024+ -> PASS for general regime."""
    mfd_cand = FieldCandidate(
        field="MONTH_YEAR",
        status="DETECTED",
        raw_value="MFD 03/2024",
        normalized_value=DateNormalized(type="MANUFACTURED", month=3, year=2024),
        evidence_ids=["ev_mfd"]
    )
    
    session = InspectionSession(
        inspection_id="sess_scen_a",
        reference_date="2024-05-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        regulatory_product_class="NON_FOOD",
        date_regulatory_regime="GENERAL",
        date_package_exemption="NONE",
        capture_plan_id="plan_software_1",
        aggregated_candidates=[mfd_cand],
        captures=[CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")]
    )
    
    _update_session_compliance(session)
    
    date_rule = next(r for r in session.rule_evaluations if r.rule_id == "MONTH_YEAR_DECLARATION_PRESENCE")
    assert date_rule.status == LegalStatus.PASS
    assert date_rule.applicability.status.value == "APPLICABLE"

def test_scenario_b_non_food_package_with_pkd_only_in_2024():
    """Scenario B: NON_FOOD package with PKD only in 2024+ -> FAIL under post-2024 Rule 6(1)(d) amendment (G.S.R. 714(E))."""
    pkd_cand = FieldCandidate(
        field="MONTH_YEAR",
        status="DETECTED",
        raw_value="PKD 03/2024",
        normalized_value=DateNormalized(type="PACKED", month=3, year=2024),
        evidence_ids=["ev_pkd"]
    )
    
    session = InspectionSession(
        inspection_id="sess_scen_b",
        reference_date="2024-05-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        regulatory_product_class="NON_FOOD",
        date_regulatory_regime="GENERAL",
        date_package_exemption="NONE",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        aggregated_candidates=[pkd_cand],
        captures=[
            CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED"),
            CaptureRecord(capture_id="c2", view_id="BACK", status="ACCEPTED", pipeline_status="COMPLETED")
        ]
    )
    
    _update_session_compliance(session)
    
    date_rule = next(r for r in session.rule_evaluations if r.rule_id == "MONTH_YEAR_DECLARATION_PRESENCE")
    assert date_rule.status == LegalStatus.FAIL
    assert "Required declaration was not detected" in date_rule.reason or "No candidate found" in date_rule.reason

def test_scenario_c_pre_2024_historical_date_semantics():
    """Scenario C: Pre-2024 package where historical PKD was legally permitted prior to G.S.R. 714(E) taking effect."""
    pkd_cand = FieldCandidate(
        field="MONTH_YEAR",
        status="DETECTED",
        raw_value="PKD 08/2023",
        normalized_value=DateNormalized(type="PACKED", month=8, year=2023),
        evidence_ids=["ev_pkd_old"]
    )
    
    session = InspectionSession(
        inspection_id="sess_scen_c",
        reference_date="2023-09-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        regulatory_product_class="NON_FOOD",
        date_regulatory_regime="GENERAL",
        date_package_exemption="NONE",
        capture_plan_id="plan_software_1",
        aggregated_candidates=[pkd_cand],
        captures=[CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")]
    )
    
    _update_session_compliance(session)
    
    date_rule = next(r for r in session.rule_evaluations if r.rule_id == "MONTH_YEAR_DECLARATION_PRESENCE")
    assert date_rule.status == LegalStatus.PASS

def test_scenario_d_food_package_date_deferred():
    """Scenario D: FOOD package -> Date rule deferred under Legal Metrology general regime."""
    session = InspectionSession(
        inspection_id="sess_scen_d",
        reference_date="2024-05-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        regulatory_product_class="FOOD",
        date_regulatory_regime="FOOD",
        date_package_exemption="NONE",
        capture_plan_id="plan_software_1",
        aggregated_candidates=[],
        captures=[CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")]
    )
    
    _update_session_compliance(session)
    
    date_rule = next(r for r in session.rule_evaluations if r.rule_id == "MONTH_YEAR_DECLARATION_PRESENCE")
    assert date_rule.status == LegalStatus.NOT_APPLICABLE
    assert date_rule.applicability.status.value == "NOT_APPLICABLE"

def test_scenario_e_two_view_package_evidence_split():
    """Scenario E: Two-view package with evidence split across FRONT and BACK views."""
    poly_mrp = [[100.0, 100.0], [250.0, 100.0], [250.0, 130.0], [100.0, 130.0]]
    line_front = OcrLine(text="MRP Rs. 150.00", confidence=0.96, polygon=poly_mrp)
    cand_mrp = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs. 150.00",
        normalized_value=MrpNormalized(amount=150.0, currency="INR"),
        evidence_ids=["ev_mrp_f"]
    )
    
    summary_front = assess_capture_visuals(
        capture_id="cap_f",
        view_id="FRONT",
        image_width=1000,
        image_height=1000,
        ocr_lines=[line_front],
        field_candidates=[cand_mrp],
        evidence_map={"0": "ev_mrp_f"}
    )
    
    poly_cc = [[50.0, 50.0], [400.0, 50.0], [400.0, 80.0], [50.0, 80.0]]
    line_back = OcrLine(text="Care: customercare@generic.in", confidence=0.94, polygon=poly_cc)
    cand_cc = FieldCandidate(
        field="CONSUMER_CARE",
        status="DETECTED",
        raw_value="Care: customercare@generic.in",
        normalized_value=ConsumerCareNormalized(email="customercare@generic.in"),
        evidence_ids=["ev_cc_b"]
    )
    
    summary_back = assess_capture_visuals(
        capture_id="cap_b",
        view_id="BACK",
        image_width=1000,
        image_height=1000,
        ocr_lines=[line_back],
        field_candidates=[cand_cc],
        evidence_map={"0": "ev_cc_b"}
    )
    
    cap_f = CaptureRecord(capture_id="cap_f", view_id="FRONT", visual_assessment=summary_front, field_candidates=[cand_mrp], status="ACCEPTED", pipeline_status="COMPLETED")
    cap_b = CaptureRecord(capture_id="cap_b", view_id="BACK", visual_assessment=summary_back, field_candidates=[cand_cc], status="ACCEPTED", pipeline_status="COMPLETED")
    
    session = InspectionSession(
        inspection_id="sess_scen_e",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        captures=[cap_f, cap_b]
    )
    
    session.aggregated_candidates = aggregate_candidates(session.captures)
    session.capture_status = evaluate_completeness(TEST_PLAN, session.captures)
    session.evidence_sufficiency = evaluate_evidence_sufficiency(TEST_PLAN, session.captures)
    
    assert session.capture_status == "COMPLETE_EVIDENCE_CAPTURE"
    assert session.evidence_sufficiency == "SUFFICIENT_FOR_ABSENCE_EVALUATION"
    
    _update_session_compliance(session)
    
    mrp_res = next(r for r in session.rule_evaluations if r.rule_id == "MRP_DECLARATION_PRESENCE")
    cc_res = next(r for r in session.rule_evaluations if r.rule_id == "CONSUMER_CARE_DECLARATION_PRESENCE")
    assert mrp_res.status == LegalStatus.PASS
    assert cc_res.status == LegalStatus.PASS
    
    # Visual rules preserve cross-view capture IDs
    assert len(session.visual_rule_evaluations) == 6
    for vr in session.visual_rule_evaluations:
        assert "cap_f" in vr.capture_ids
        assert "cap_b" in vr.capture_ids

def test_scenario_f_malformed_low_confidence_declaration():
    """Scenario F: Low confidence declaration produces REVIEW_REQUIRED without legal FAIL."""
    cand_low = FieldCandidate(
        field="MRP",
        status="REVIEW_REQUIRED",
        raw_value="MR? 50",
        confidence=0.55,
        evidence_ids=["ev_low"]
    )
    
    session = InspectionSession(
        inspection_id="sess_scen_f",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        aggregated_candidates=[cand_low],
        captures=[CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")]
    )
    
    _update_session_compliance(session)
    
    mrp_rule = next(r for r in session.rule_evaluations if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_rule.status == LegalStatus.REVIEW_REQUIRED
    assert mrp_rule.status != LegalStatus.FAIL

def test_scenario_g_poor_quality_capture_requires_recapture():
    """Scenario G: Poor-quality capture requiring recapture does not accuse the package of statutory failure."""
    quality = ImageQualityAssessment(
        width=600, height=600, blur_score=15.0, brightness=80.0, glare_percentage=5.0,
        quality_status="RETAKE_RECOMMENDED", reasons=["Image blur detected", "Severe specular glare"]
    )
    
    line = OcrLine(text="Net Qty 100g", confidence=0.88, polygon=[[100.0, 100.0], [200.0, 100.0], [200.0, 120.0], [100.0, 120.0]])
    cand_qty = FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value="Net Qty 100g", evidence_ids=["ev_g"])
    
    summary = assess_capture_visuals(
        capture_id="cap_blur",
        view_id="FRONT",
        image_width=600,
        image_height=600,
        ocr_lines=[line],
        field_candidates=[cand_qty],
        evidence_map={"0": "ev_g"},
        quality_assessment=quality
    )
    
    assert summary.overall_visual_status == "NEEDS_RECAPTURE"
    
    cap = CaptureRecord(capture_id="cap_blur", view_id="FRONT", quality_assessment=quality, visual_assessment=summary, status="RETAKE_RECOMMENDED", pipeline_status="COMPLETED")
    results = evaluate_visual_legal_rules([cap], [cand_qty], date(2025, 1, 1))
    
    nq_clr = next(r for r in results if r.rule_id == "RULE_8_NET_QUANTITY_SURROUNDING_CLEARANCE")
    assert nq_clr.status == "REVIEW_REQUIRED"
    assert "photograph framing or quality limitations" in nq_clr.reason

def test_scenario_h_missing_evidence_with_insufficient_capture_coverage():
    """Scenario H: Missing declarations with incomplete surface coverage must NEVER evaluate to FAIL."""
    session = InspectionSession(
        inspection_id="sess_scen_h",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        aggregated_candidates=[], # No declarations found on 1 view
        captures=[CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")]
    )
    
    session.capture_status = evaluate_completeness(TEST_PLAN, session.captures)
    session.evidence_sufficiency = evaluate_evidence_sufficiency(TEST_PLAN, session.captures)
    
    assert session.capture_status == "INCOMPLETE_INSPECTION"
    assert session.evidence_sufficiency == "INSUFFICIENT_FOR_ABSENCE_EVALUATION"
    
    _update_session_compliance(session)
    
    # Missing MRP declaration on partial inspection
    mrp_rule = next(r for r in session.rule_evaluations if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_rule.status == LegalStatus.REVIEW_REQUIRED
    assert mrp_rule.status != LegalStatus.FAIL
    assert "No candidate found" in mrp_rule.reason or "Insufficient evidence" in mrp_rule.reason
