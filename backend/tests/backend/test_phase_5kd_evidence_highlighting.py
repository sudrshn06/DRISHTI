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
    VisualFinding
)
from app.services.visual_assessment_service import (
    compute_region_geometry,
    assess_declaration,
    assess_capture_visuals,
    evaluate_visual_legal_rules
)
from app.api.routes.inspections import _update_session_compliance

def test_1_evidence_id_maps_to_correct_capture_and_view():
    # 1. Evidence ID maps to correct capture and view
    line1 = OcrLine(text="MRP Rs. 50.00", confidence=0.95, polygon=[[100.0, 100.0], [250.0, 100.0], [250.0, 130.0], [100.0, 130.0]])
    cand_mrp = FieldCandidate(field="MRP", status="DETECTED", raw_value="MRP Rs. 50.00", evidence_ids=["ev_front_mrp"])
    
    summary = assess_capture_visuals(
        capture_id="cap_front_01",
        view_id="FRONT",
        image_width=800,
        image_height=600,
        ocr_lines=[line1],
        field_candidates=[cand_mrp],
        evidence_map={"0": "ev_front_mrp"}
    )
    
    assert len(summary.assessments) == 1
    assessment = summary.assessments[0]
    assert assessment.capture_id == "cap_front_01"
    assert assessment.view_id == "FRONT"
    assert "ev_front_mrp" in assessment.evidence_ids
    assert assessment.geometry is not None
    assert assessment.geometry.pixel_box.width_px == 150.0

def test_2_and_3_multiple_evidence_polygons_and_multiple_captures():
    # 2 & 3. Multiple evidence polygons across multiple captures
    line_front = OcrLine(text="Net Wt: 250 g", confidence=0.94, polygon=[[100.0, 200.0], [250.0, 200.0], [250.0, 230.0], [100.0, 230.0]])
    cand_front = FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value="Net Wt: 250 g", evidence_ids=["ev_front_nq"])
    
    summary_front = assess_capture_visuals(
        capture_id="cap_f",
        view_id="FRONT",
        image_width=1000,
        image_height=1000,
        ocr_lines=[line_front],
        field_candidates=[cand_front],
        evidence_map={"0": "ev_front_nq"}
    )
    
    line_back = OcrLine(text="Consumer Care: care@brand.com", confidence=0.92, polygon=[[50.0, 50.0], [300.0, 50.0], [300.0, 80.0], [50.0, 80.0]])
    cand_back = FieldCandidate(field="CONSUMER_CARE", status="DETECTED", raw_value="care@brand.com", evidence_ids=["ev_back_cc"])
    
    summary_back = assess_capture_visuals(
        capture_id="cap_b",
        view_id="BACK",
        image_width=1200,
        image_height=800,
        ocr_lines=[line_back],
        field_candidates=[cand_back],
        evidence_map={"0": "ev_back_cc"}
    )
    
    cap_f = CaptureRecord(capture_id="cap_f", view_id="FRONT", visual_assessment=summary_front, status="ACCEPTED", pipeline_status="COMPLETED")
    cap_b = CaptureRecord(capture_id="cap_b", view_id="BACK", visual_assessment=summary_back, status="ACCEPTED", pipeline_status="COMPLETED")
    
    visual_rules = evaluate_visual_legal_rules([cap_f, cap_b], [cand_front, cand_back], date(2025, 1, 1))
    
    assert len(visual_rules) == 6
    nq_rule = next(r for r in visual_rules if r.rule_id == "RULE_8_NET_QUANTITY_SURROUNDING_CLEARANCE")
    assert "ev_front_nq" in nq_rule.evidence_ids
    assert "cap_f" in nq_rule.capture_ids
    assert "cap_b" in nq_rule.capture_ids

def test_4_and_5_missing_and_malformed_geometry_safe_fallback():
    # 4 & 5. Missing / Malformed geometry fails safely without raising exceptions
    geom_empty = compute_region_geometry([], 1000, 1000)
    assert geom_empty is None
    
    geom_malformed = compute_region_geometry([[[None, "bad"], [100.0]]], 1000, 1000)
    assert geom_malformed is None
    
    assessment = assess_declaration(
        field="GENERIC_FIELD",
        evidence_ids=["ev_none"],
        capture_id="cap_safe",
        view_id="FRONT",
        raw_text="No Box Text",
        polygons=[[[float('nan'), 10.0]]],
        image_width=1000,
        image_height=1000,
        median_line_height_px=20.0,
        ocr_confidence=0.9
    )
    assert assessment.geometry is None
    assert len(assessment.polygons) == 0

def test_6_and_7_visual_findings_link_to_supporting_evidence():
    # 6 & 7. Visual findings link directly to supporting evidence IDs
    line_nq = OcrLine(text="Net Qty: 1 kg", confidence=0.95, polygon=[[200.0, 200.0], [350.0, 200.0], [350.0, 230.0], [200.0, 230.0]])
    cand_nq = FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value="Net Qty: 1 kg", evidence_ids=["ev_nq_link"])
    
    summary = assess_capture_visuals(
        capture_id="cap_link",
        view_id="FRONT",
        image_width=1000,
        image_height=1000,
        ocr_lines=[line_nq],
        field_candidates=[cand_nq],
        evidence_map={"0": "ev_nq_link"}
    )
    
    finding = next(f for f in summary.findings if f.check_type == VisualCheckType.NET_QUANTITY_CLEARANCE)
    assert "ev_nq_link" in finding.evidence_ids
    assert finding.capture_id == "cap_link"
    assert finding.view_id == "FRONT"

def test_8_and_9_normalized_coordinate_scaling_and_no_hardcoding():
    # 8 & 9. Normalized coordinates scale correctly and contain 0 hardcoded assumptions
    poly = [[100.0, 200.0], [300.0, 200.0], [300.0, 400.0], [100.0, 400.0]]
    geom = compute_region_geometry([poly], 1000, 1000)
    
    assert geom.normalized_box.x_min == 0.1
    assert geom.normalized_box.y_min == 0.2
    assert geom.normalized_box.x_max == 0.3
    assert geom.normalized_box.y_max == 0.4
    assert geom.width_ratio == 0.2
    assert geom.height_ratio == 0.2
    
    # Different aspect ratio: 2000 x 500
    geom_wide = compute_region_geometry([poly], 2000, 500)
    assert geom_wide.normalized_box.x_min == 0.05
    assert geom_wide.normalized_box.y_min == 0.4
    assert geom_wide.normalized_box.x_max == 0.15
    assert geom_wide.normalized_box.y_max == 0.8
    assert geom_wide.width_ratio == 0.1
    assert geom_wide.height_ratio == 0.4

def test_10_existing_legal_presence_results_remain_completely_unchanged():
    # 10. Existing presence evaluations remain completely intact
    mrp_cand = FieldCandidate(
        field="MRP",
        status="DETECTED",
        normalized_value=MrpNormalized(amount=250.0, currency="INR"),
        evidence_ids=["ev_mrp"]
    )
    
    session = InspectionSession(
        inspection_id="test_sess_5kd",
        reference_date="2025-01-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_software_1",
        aggregated_candidates=[mrp_cand],
        captures=[CaptureRecord(capture_id="c1", view_id="FRONT", status="ACCEPTED", pipeline_status="COMPLETED")]
    )
    
    _update_session_compliance(session)
    
    mrp_rule = next(r for r in session.rule_evaluations if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_rule.status == LegalStatus.PASS
    assert mrp_rule.rule_id == "MRP_DECLARATION_PRESENCE"
