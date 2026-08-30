import pytest
from app.schemas.ocr import OcrLine, FieldCandidate, MrpNormalized
from app.schemas.image_quality import ImageQualityAssessment
from app.schemas.visual_assessment import (
    NormalizedBoundingBox,
    PixelBoundingBox,
    RegionGeometry,
    DeclarationVisualAssessment,
    CaptureVisualAssessmentSummary,
    VisualCheckType,
    VisualObservationStatus,
    VisualFinding,
    InterferingEvidence
)
from app.services.visual_assessment_service import (
    compute_region_geometry,
    compute_median_line_height,
    compute_prominence_metrics,
    evaluate_readability,
    assess_declaration,
    assess_capture_visuals,
    evaluate_net_quantity_clearance,
    generate_all_visual_findings
)

def test_1_normalized_bbox_calculations():
    poly = [[[100.0, 200.0], [300.0, 200.0], [300.0, 400.0], [100.0, 400.0]]]
    geom = compute_region_geometry(poly, image_width=1000, image_height=800)
    
    assert geom is not None
    assert geom.pixel_box.x_min == 100.0
    assert geom.pixel_box.y_min == 200.0
    assert geom.pixel_box.x_max == 300.0
    assert geom.pixel_box.y_max == 400.0
    assert geom.pixel_box.width_px == 200.0
    assert geom.pixel_box.height_px == 200.0
    assert geom.pixel_box.area_px == 40000.0
    
    assert geom.normalized_box.x_min == 0.1
    assert geom.normalized_box.y_min == 0.25
    assert geom.normalized_box.x_max == 0.3
    assert geom.normalized_box.y_max == 0.5
    
    assert geom.width_ratio == 0.2
    assert geom.height_ratio == 0.25
    assert geom.area_ratio == 0.05

def test_2_image_relative_text_height_and_prominence():
    poly = [[[100.0, 100.0], [200.0, 100.0], [200.0, 150.0], [100.0, 150.0]]] # height = 50px
    geom = compute_region_geometry(poly, image_width=1000, image_height=1000)
    assert geom is not None
    
    prom_dominant = compute_prominence_metrics(geom, median_line_height_px=20.0)
    assert prom_dominant.height_to_image_ratio == 0.05
    assert prom_dominant.height_to_median_line_height_ratio == 2.5
    assert prom_dominant.prominence_signal == "DOMINANT"
    
    prom_sub = compute_prominence_metrics(geom, median_line_height_px=100.0)
    assert prom_sub.height_to_median_line_height_ratio == 0.5
    assert prom_sub.prominence_signal == "SUB_MEDIAN"
    
    prom_std = compute_prominence_metrics(geom, median_line_height_px=50.0)
    assert prom_std.height_to_median_line_height_ratio == 1.0
    assert prom_std.prominence_signal == "STANDARD"

def test_3_region_edge_and_cropping_detection():
    poly_edge = [[[0.0, 100.0], [50.0, 100.0], [50.0, 120.0], [0.0, 120.0]]]
    geom_edge = compute_region_geometry(poly_edge, image_width=500, image_height=500, edge_margin_px=2.0)
    assert geom_edge is not None
    assert geom_edge.touches_edge is True
    assert geom_edge.distance_to_edge_px["left"] == 0.0
    
    poly_inside = [[[50.0, 50.0], [100.0, 50.0], [100.0, 70.0], [50.0, 70.0]]]
    geom_inside = compute_region_geometry(poly_inside, image_width=500, image_height=500, edge_margin_px=2.0)
    assert geom_inside is not None
    assert geom_inside.touches_edge is False

def test_4_multiple_ocr_polygons_merged_geometry():
    poly1 = [[20.0, 20.0], [100.0, 20.0], [100.0, 40.0], [20.0, 40.0]]
    poly2 = [[20.0, 50.0], [120.0, 50.0], [120.0, 70.0], [20.0, 70.0]]
    
    geom = compute_region_geometry([poly1, poly2], image_width=400, image_height=400)
    assert geom is not None
    assert geom.pixel_box.x_min == 20.0
    assert geom.pixel_box.y_min == 20.0
    assert geom.pixel_box.x_max == 120.0
    assert geom.pixel_box.y_max == 70.0
    assert geom.pixel_box.width_px == 100.0
    assert geom.pixel_box.height_px == 50.0

def test_5_provenance_preservation():
    poly = [[10.0, 10.0], [50.0, 10.0], [50.0, 20.0], [10.0, 20.0]]
    assessment = assess_declaration(
        field="MRP",
        evidence_ids=["ev_123", "ev_456"],
        capture_id="cap_front_01",
        view_id="FRONT",
        raw_text="MRP Rs. 50.00",
        polygons=[poly],
        image_width=500,
        image_height=500,
        median_line_height_px=10.0,
        ocr_confidence=0.95
    )
    
    assert assessment.field == "MRP"
    assert assessment.evidence_ids == ["ev_123", "ev_456"]
    assert assessment.capture_id == "cap_front_01"
    assert assessment.view_id == "FRONT"
    assert assessment.raw_text == "MRP Rs. 50.00"
    assert assessment.technical_status == "EVALUABLE"

def test_6_poor_capture_quality_yields_needs_recapture():
    quality = ImageQualityAssessment(
        width=1000,
        height=800,
        blur_score=35.0,
        brightness=120.0,
        glare_percentage=2.0,
        quality_status="RETAKE_RECOMMENDED",
        reasons=["Low sharpness (variance of Laplacian: 35.0)"]
    )
    
    sig = evaluate_readability(ocr_confidence=0.92, is_clipped=False, quality_assessment=quality)
    assert sig.technical_readability == "NEEDS_RECAPTURE"
    assert sig.capture_quality_status == "RETAKE_RECOMMENDED"
    assert "Low sharpness" in sig.readability_reasons[0]

def test_7_low_ocr_confidence_is_review_required_not_fail():
    quality = ImageQualityAssessment(
        width=1000,
        height=800,
        blur_score=150.0,
        brightness=120.0,
        glare_percentage=1.0,
        quality_status="ACCEPTABLE",
        reasons=[]
    )
    
    sig = evaluate_readability(ocr_confidence=0.65, is_clipped=False, quality_assessment=quality)
    assert sig.technical_readability == "REVIEW_REQUIRED"
    assert any("confidence is low" in r for r in sig.readability_reasons)

def test_8_no_pixel_to_mm_conversion_attributes():
    poly = [[10.0, 10.0], [50.0, 10.0], [50.0, 30.0], [10.0, 30.0]]
    geom = compute_region_geometry([poly], image_width=500, image_height=500)
    prom = compute_prominence_metrics(geom, median_line_height_px=20.0)
    
    assert not hasattr(geom, "height_mm")
    assert not hasattr(geom, "width_mm")
    assert not hasattr(geom, "area_mm2")
    assert not hasattr(prom, "font_height_mm")

def test_9_front_role_is_not_automatically_principal_display_panel():
    summary = assess_capture_visuals(
        capture_id="cap_01",
        view_id="FRONT",
        image_width=600,
        image_height=800,
        ocr_lines=[OcrLine(text="Brand Name", confidence=0.95, polygon=[[10.0, 10.0], [100.0, 10.0], [100.0, 30.0], [10.0, 30.0]])],
        field_candidates=[],
        evidence_map={},
        quality_assessment=None
    )
    assert summary.view_id == "FRONT"
    pdp_finding = next(f for f in summary.findings if f.check_type == VisualCheckType.PRINCIPAL_DISPLAY_PANEL_RULE_8)
    assert pdp_finding.status == VisualObservationStatus.NOT_EVALUABLE
    assert "not automatically classified" in pdp_finding.reason

def test_10_rule_8_clearance_fully_clear_zone():
    # Net Quantity text from (200, 200) to (300, 230) -> H = 30px
    # Vertical clearance needed: 30px (y: 170 to 260)
    # Horizontal clearance needed: 60px (x: 140 to 360)
    # Entire clearance zone fits within 600x600 image.
    poly_nq = [[200.0, 200.0], [300.0, 200.0], [300.0, 230.0], [200.0, 230.0]]
    nq_assessment = assess_declaration(
        field="NET_QUANTITY",
        evidence_ids=["ev_nq"],
        capture_id="cap_clr_1",
        view_id="FRONT",
        raw_text="Net Wt. 500g",
        polygons=[poly_nq],
        image_width=600,
        image_height=600,
        median_line_height_px=30.0,
        ocr_confidence=0.95
    )
    
    # Far-away line at (450, 450) -> does not intersect clearance zone
    line_other = OcrLine(text="Far text", confidence=0.9, polygon=[[450.0, 450.0], [550.0, 450.0], [550.0, 470.0], [450.0, 470.0]])
    line_nq = OcrLine(text="Net Wt. 500g", confidence=0.95, polygon=poly_nq)
    
    finding = evaluate_net_quantity_clearance(
        nq_assessment=nq_assessment,
        ocr_lines=[line_nq, line_other],
        evidence_map={"0": "ev_nq", "1": "ev_other"},
        image_width=600,
        image_height=600,
        quality_assessment=None
    )
    
    assert finding.status == VisualObservationStatus.REVIEW_REQUIRED
    assert finding.check_type == VisualCheckType.NET_QUANTITY_CLEARANCE
    assert finding.metrics["is_numeral_geometry_isolated"] is False
    assert "legally referenced to isolated numeral height" in finding.reason
    assert len(finding.interfering_evidence) == 0

def test_11_rule_8_clearance_with_interfering_text():
    # Net Quantity text from (200, 200) to (300, 230) -> H = 30px
    # Vertical clearance zone: (170 to 260)
    # Horizontal clearance zone: (140 to 360)
    poly_nq = [[200.0, 200.0], [300.0, 200.0], [300.0, 230.0], [200.0, 230.0]]
    nq_assessment = assess_declaration(
        field="NET_QUANTITY",
        evidence_ids=["ev_nq"],
        capture_id="cap_clr_2",
        view_id="FRONT",
        raw_text="Net Wt. 500g",
        polygons=[poly_nq],
        image_width=600,
        image_height=600,
        median_line_height_px=30.0,
        ocr_confidence=0.95
    )
    
    # Interfering line at (220, 240)-(280, 255) -> directly inside the bottom 1x clearance zone (170..260)
    line_interfering = OcrLine(text="Special Offer", confidence=0.88, polygon=[[220.0, 240.0], [280.0, 240.0], [280.0, 255.0], [220.0, 255.0]])
    line_nq = OcrLine(text="Net Wt. 500g", confidence=0.95, polygon=poly_nq)
    
    finding = evaluate_net_quantity_clearance(
        nq_assessment=nq_assessment,
        ocr_lines=[line_nq, line_interfering],
        evidence_map={"0": "ev_nq", "1": "ev_offer"},
        image_width=600,
        image_height=600,
        quality_assessment=None
    )
    
    assert finding.status == VisualObservationStatus.REVIEW_REQUIRED
    assert "intersecting text element" in finding.reason
    assert len(finding.interfering_evidence) == 1
    assert finding.interfering_evidence[0].text == "Special Offer"
    assert finding.interfering_evidence[0].evidence_id == "ev_offer"

def test_12_rule_8_clearance_extends_outside_image_boundary():
    # Net Quantity placed at top-left edge: (20, 10) to (100, 30) -> H = 20px
    # Horizontal clearance extends to x = 20 - 40 = -20 (outside image!)
    poly_nq = [[20.0, 10.0], [100.0, 10.0], [100.0, 30.0], [20.0, 30.0]]
    nq_assessment = assess_declaration(
        field="NET_QUANTITY",
        evidence_ids=["ev_nq"],
        capture_id="cap_clr_3",
        view_id="FRONT",
        raw_text="Net Wt. 500g",
        polygons=[poly_nq],
        image_width=500,
        image_height=500,
        median_line_height_px=20.0,
        ocr_confidence=0.95
    )
    
    finding = evaluate_net_quantity_clearance(
        nq_assessment=nq_assessment,
        ocr_lines=[OcrLine(text="Net Wt. 500g", confidence=0.95, polygon=poly_nq)],
        evidence_map={"0": "ev_nq"},
        image_width=500,
        image_height=500,
        quality_assessment=None
    )
    
    assert finding.status == VisualObservationStatus.NEEDS_RECAPTURE
    assert "extends beyond image boundaries" in finding.reason

def test_13_statutory_rule7_and_rule9_observations():
    findings = generate_all_visual_findings(
        capture_id="cap_stat_1",
        view_id="FRONT",
        image_width=800,
        image_height=800,
        assessments=[],
        ocr_lines=[],
        evidence_map={},
        quality_assessment=None,
        median_line_height=20.0
    )
    
    r7 = next(f for f in findings if f.check_type == VisualCheckType.PHYSICAL_FONT_SIZE_RULE_7)
    assert r7.status == VisualObservationStatus.NOT_EVALUABLE
    assert "cannot be deterministically evaluated" in r7.reason
    assert "strictly prohibits converting pixel dimensions" in r7.limitations
    
    r9 = next(f for f in findings if f.check_type == VisualCheckType.CONTRAST_RULE_9)
    assert r9.status == VisualObservationStatus.NOT_EVALUABLE
    assert "Rule 9(1)(a)" in r9.legal_reference

def test_14_poor_capture_quality_deduplication():
    # If image quality is poor (blur), duplicate lower-level noise is suppressed
    quality = ImageQualityAssessment(
        width=800, height=800, blur_score=30.0, brightness=100.0, glare_percentage=1.0, quality_status="RETAKE_RECOMMENDED", reasons=["Blurred"]
    )
    poly = [[50.0, 50.0], [100.0, 50.0], [100.0, 70.0], [50.0, 70.0]]
    assessment = assess_declaration(
        field="MRP",
        evidence_ids=["ev_1"],
        capture_id="cap_poor",
        view_id="FRONT",
        raw_text="MRP 100",
        polygons=[poly],
        image_width=800,
        image_height=800,
        median_line_height_px=20.0,
        ocr_confidence=0.60, # Low confidence
        quality_assessment=quality
    )
    
    findings = generate_all_visual_findings(
        capture_id="cap_poor",
        view_id="FRONT",
        image_width=800,
        image_height=800,
        assessments=[assessment],
        ocr_lines=[],
        evidence_map={},
        quality_assessment=quality,
        median_line_height=20.0
    )
    
    # Overall capture quality finding is primary NEEDS_RECAPTURE
    cap_finding = next(f for f in findings if f.check_type == VisualCheckType.CLIPPING_AND_FRAMING)
    assert cap_finding.status == VisualObservationStatus.NEEDS_RECAPTURE
    # Readability finding for MRP is suppressed/omitted under degraded capture
    readability_findings = [f for f in findings if f.check_type == VisualCheckType.READABILITY]
    assert len(readability_findings) == 0

def test_15_end_to_end_capture_visual_summary_with_findings():
    line1 = OcrLine(text="MRP Rs. 100.00", confidence=0.96, polygon=[[150.0, 100.0], [300.0, 100.0], [300.0, 130.0], [150.0, 130.0]])
    line2 = OcrLine(text="Net Qty: 500 g", confidence=0.94, polygon=[[150.0, 200.0], [300.0, 200.0], [300.0, 230.0], [150.0, 230.0]])
    
    ev_map = {"0": "ev_mrp", "1": "ev_net_qty"}
    cand_mrp = FieldCandidate(field="MRP", status="DETECTED", raw_value="MRP Rs. 100.00", evidence_ids=["ev_mrp"], confidence=0.96)
    cand_qty = FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value="Net Qty: 500 g", evidence_ids=["ev_net_qty"], confidence=0.94)
    
    summary = assess_capture_visuals(
        capture_id="cap_full_e2e",
        view_id="FRONT",
        image_width=1000,
        image_height=1000,
        ocr_lines=[line1, line2],
        field_candidates=[cand_mrp, cand_qty],
        evidence_map=ev_map,
        quality_assessment=ImageQualityAssessment(
            width=1000, height=1000, blur_score=200.0, brightness=130.0, glare_percentage=0.5, quality_status="ACCEPTABLE", reasons=[]
        )
    )
    
    assert summary.overall_visual_status == "REVIEW_REQUIRED"
    assert len(summary.findings) >= 5 # Net Quantity clearance, MRP readability, MRP prominence, Rule 7, Rule 9, PDP
    
    nq_finding = next(f for f in summary.findings if f.check_type == VisualCheckType.NET_QUANTITY_CLEARANCE)
    assert nq_finding.status == VisualObservationStatus.REVIEW_REQUIRED
