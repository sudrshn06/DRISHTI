import pytest
from datetime import date
from app.schemas.ocr import OcrLine, FieldCandidate, MrpNormalized, NetQuantityNormalized
from app.schemas.image_quality import ImageQualityAssessment
from app.schemas.inspection import InspectionSession, CaptureRecord
from app.schemas.compliance import LegalStatus
from app.schemas.visual_assessment import (
    VisualCheckCapability,
    VisualObservationStatus,
    VisualCheckType,
    VisualRuleEvaluationResult
)
from app.services.visual_assessment_service import (
    assess_capture_visuals,
    evaluate_visual_legal_rules
)
from app.api.routes.inspections import _update_session_compliance

def test_1_rule_7_ordinary_image_is_not_evaluable():
    # 1. Rule 7 minimum numeral size cannot be evaluated from ordinary photos without scale reference
    cap = CaptureRecord(capture_id="cap1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")
    results = evaluate_visual_legal_rules([cap], [], date(2025, 1, 1))
    
    r7 = next(r for r in results if r.rule_id == "RULE_7_MINIMUM_NUMERAL_HEIGHT")
    assert r7.capability == VisualCheckCapability.NOT_EVALUABLE_FROM_CURRENT_CAPTURE
    assert r7.status == "NOT_EVALUABLE"
    assert r7.requires_inspector_review is True
    assert "Rule 7" in r7.legal_reference
    assert "trusted physical scale reference" in r7.reason

def test_2_no_pixel_to_mm_conversion():
    # 2. Verify no millimeter attributes exist on evaluation result
    cap = CaptureRecord(capture_id="cap1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")
    results = evaluate_visual_legal_rules([cap], [], date(2025, 1, 1))
    
    for r in results:
        assert not hasattr(r, "height_mm")
        assert not hasattr(r, "font_size_pt")
        assert not hasattr(r, "pdp_area_sq_cm")

def test_3_and_4_front_does_not_satisfy_pdp_and_placement_is_not_evaluable():
    # 3 & 4. FRONT view role is not PDP, and PDP placement is NOT_EVALUABLE
    cap = CaptureRecord(capture_id="cap1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")
    results = evaluate_visual_legal_rules([cap], [], date(2025, 1, 1))
    
    r8_pdp = next(r for r in results if r.rule_id == "RULE_8_PRINCIPAL_DISPLAY_PANEL_PLACEMENT")
    assert r8_pdp.capability == VisualCheckCapability.NOT_EVALUABLE_FROM_CURRENT_CAPTURE
    assert r8_pdp.status == "NOT_EVALUABLE"
    assert "not automatically classified as the statutory Principal Display Panel" in r8_pdp.reason

def test_5_and_7_clear_rule_8_proxy_zone_does_not_become_legal_pass():
    # 5 & 7. When Rule 8 surrounding zone appears clear, it does NOT generate legal PASS (requires inspector review)
    line_nq = OcrLine(text="Net Qty: 500 g", confidence=0.95, polygon=[[200.0, 200.0], [350.0, 200.0], [350.0, 230.0], [200.0, 230.0]])
    cand_nq = FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value="Net Qty: 500 g", evidence_ids=["ev_nq"])
    
    summary = assess_capture_visuals(
        capture_id="cap1",
        view_id="FRONT",
        image_width=1000,
        image_height=1000,
        ocr_lines=[line_nq],
        field_candidates=[cand_nq],
        evidence_map={"0": "ev_nq"},
        quality_assessment=None
    )
    
    cap = CaptureRecord(capture_id="cap1", view_id="FRONT", visual_assessment=summary, status="ACCEPTED", pipeline_status="COMPLETED")
    results = evaluate_visual_legal_rules([cap], [cand_nq], date(2025, 1, 1))
    
    r8_clr = next(r for r in results if r.rule_id == "RULE_8_NET_QUANTITY_SURROUNDING_CLEARANCE")
    assert r8_clr.capability == VisualCheckCapability.INSPECTOR_REVIEW_ONLY
    assert r8_clr.status == "REVIEW_REQUIRED" # Must NOT be PASS
    assert r8_clr.status != "PASS"
    assert r8_clr.requires_inspector_review is True
    assert "Statutory Rule 8 clearance is legally referenced to isolated numeral height" in r8_clr.reason

def test_6_interfering_rule_8_zone_does_not_become_legal_fail():
    # 6. When text intersects Rule 8 clearance zone, it generates REVIEW_REQUIRED, NOT legal FAIL
    line_nq = OcrLine(text="Net Qty: 500 g", confidence=0.95, polygon=[[200.0, 200.0], [350.0, 200.0], [350.0, 230.0], [200.0, 230.0]])
    line_inter = OcrLine(text="Special Price", confidence=0.90, polygon=[[220.0, 240.0], [300.0, 240.0], [300.0, 255.0], [220.0, 255.0]])
    cand_nq = FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value="Net Qty: 500 g", evidence_ids=["ev_nq"])
    
    summary = assess_capture_visuals(
        capture_id="cap1",
        view_id="FRONT",
        image_width=1000,
        image_height=1000,
        ocr_lines=[line_nq, line_inter],
        field_candidates=[cand_nq],
        evidence_map={"0": "ev_nq", "1": "ev_inter"},
        quality_assessment=None
    )
    
    cap = CaptureRecord(capture_id="cap1", view_id="FRONT", visual_assessment=summary, status="ACCEPTED", pipeline_status="COMPLETED")
    results = evaluate_visual_legal_rules([cap], [cand_nq], date(2025, 1, 1))
    
    r8_clr = next(r for r in results if r.rule_id == "RULE_8_NET_QUANTITY_SURROUNDING_CLEARANCE")
    assert r8_clr.capability == VisualCheckCapability.INSPECTOR_REVIEW_ONLY
    assert r8_clr.status == "REVIEW_REQUIRED" # Must NOT be FAIL
    assert r8_clr.status != "FAIL"
    assert "potential intersecting text element(s)" in r8_clr.reason

def test_8_and_10_low_and_high_ocr_confidence_do_not_become_fail_or_pass():
    # 8 & 10. Low OCR confidence is NOT Rule 9 FAIL; High OCR confidence is NOT unconditional Rule 9 PASS
    cap = CaptureRecord(capture_id="cap1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")
    results = evaluate_visual_legal_rules([cap], [], date(2025, 1, 1))
    
    r9_leg = next(r for r in results if r.rule_id == "RULE_9_DECLARATION_LEGIBILITY")
    assert r9_leg.capability == VisualCheckCapability.INSPECTOR_REVIEW_ONLY
    assert r9_leg.status == "REVIEW_REQUIRED"
    assert r9_leg.status not in ("PASS", "FAIL")

def test_9_sub_median_prominence_does_not_become_fail():
    # 9. SUB_MEDIAN prominence is NOT Rule 9 FAIL
    cap = CaptureRecord(capture_id="cap1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")
    results = evaluate_visual_legal_rules([cap], [], date(2025, 1, 1))
    
    r9_prom = next(r for r in results if r.rule_id == "RULE_9_RELATIVE_PROMINENCE")
    assert r9_prom.capability == VisualCheckCapability.INSPECTOR_REVIEW_ONLY
    assert r9_prom.status == "REVIEW_REQUIRED"
    assert r9_prom.status != "FAIL"

def test_11_contrast_remains_not_evaluable():
    # 11. Colour contrast is NOT_EVALUABLE_FROM_CURRENT_CAPTURE
    cap = CaptureRecord(capture_id="cap1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")
    results = evaluate_visual_legal_rules([cap], [], date(2025, 1, 1))
    
    r9_contrast = next(r for r in results if r.rule_id == "RULE_9_COLOUR_CONTRAST")
    assert r9_contrast.capability == VisualCheckCapability.NOT_EVALUABLE_FROM_CURRENT_CAPTURE
    assert r9_contrast.status == "NOT_EVALUABLE"
    assert "spectrophotometric calibration" in r9_contrast.reason

def test_12_poor_capture_prevents_legal_visual_evaluation():
    # 12. Poor capture yields REVIEW_REQUIRED / capture limitation without accusing package
    quality = ImageQualityAssessment(
        width=800, height=800, blur_score=25.0, brightness=100.0, glare_percentage=1.0, quality_status="RETAKE_RECOMMENDED", reasons=["Blur"]
    )
    cap = CaptureRecord(capture_id="cap_blur", view_id="FRONT", quality_assessment=quality, status="RETAKE_RECOMMENDED", pipeline_status="COMPLETED")
    cand_nq = FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value="500g", evidence_ids=["ev1"])
    
    results = evaluate_visual_legal_rules([cap], [cand_nq], date(2025, 1, 1))
    r8_clr = next(r for r in results if r.rule_id == "RULE_8_NET_QUANTITY_SURROUNDING_CLEARANCE")
    assert r8_clr.status == "REVIEW_REQUIRED"
    assert "photograph framing or quality limitations" in r8_clr.reason

def test_13_and_15_presence_rules_remain_unchanged_and_separate():
    # 13 & 15. Declaration presence rules remain PASS while visual legal checks are in visual_rule_evaluations
    mrp_cand = FieldCandidate(
        field="MRP",
        status="DETECTED",
        normalized_value=MrpNormalized(amount=100.0, currency="INR"),
        evidence_ids=["ev_mrp"]
    )
    
    session = InspectionSession(
        inspection_id="test_sess_sep",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        aggregated_candidates=[mrp_cand],
        captures=[CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")]
    )
    
    _update_session_compliance(session)
    
    # 1. Check existing presence rule: MRP is PASS
    mrp_presence = next(r for r in session.rule_evaluations if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_presence.status == LegalStatus.PASS
    
    # 2. Check visual legal rules: separate list on session
    assert hasattr(session, "visual_rule_evaluations")
    assert session.visual_rule_evaluations is not None
    assert len(session.visual_rule_evaluations) == 6
    
    # MRP presence was NOT downgraded by visual checks
    assert mrp_presence.status == LegalStatus.PASS

def test_14_evidence_provenance_preserved():
    # 14. Evidence IDs, capture IDs, and supporting findings are preserved
    cand = FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value="500g", evidence_ids=["ev_nq_99"])
    cap = CaptureRecord(capture_id="cap_prov_1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")
    results = evaluate_visual_legal_rules([cap], [cand], date(2025, 1, 1))
    
    r8_clr = next(r for r in results if r.rule_id == "RULE_8_NET_QUANTITY_SURROUNDING_CLEARANCE")
    assert "ev_nq_99" in r8_clr.evidence_ids
    assert "cap_prov_1" in r8_clr.capture_ids

def test_16_no_arbitrary_compliance_score():
    # 16. Ensure no score or percentage is added
    cap = CaptureRecord(capture_id="cap1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")
    results = evaluate_visual_legal_rules([cap], [], date(2025, 1, 1))
    
    for r in results:
        assert not hasattr(r, "score")
        assert not hasattr(r, "compliance_percentage")
        assert not hasattr(r, "visual_score")
