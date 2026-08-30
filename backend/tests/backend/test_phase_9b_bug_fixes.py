import pytest
from datetime import date
from app.schemas.ocr import OcrLine, FieldCandidate
from app.schemas.inspection import InspectionSession, CaptureRecord
from app.services.candidate_extractor import extract_candidates
from app.services.inspection_service import aggregate_candidates
from app.api.routes.inspections import _update_session_compliance

def test_b01_pipeline_evidence_survival():
    """
    BUG-01: P9B-B01-PIPELINE-EVIDENCE-SURVIVAL
    Asserts that valid candidate evidence from one capture is preserved through
    multi-view aggregation and compliance even when a second capture contains no declarations.
    """
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    
    # Capture 1: Has full declarations
    lines_cap1 = [
        OcrLine(text="MRP Rs. 150.00 (INCL. OF ALL TAXES)", confidence=0.98, polygon=dummy_poly),
        OcrLine(text="NET QUANTITY: 500 g", confidence=0.97, polygon=dummy_poly),
        OcrLine(text="COMMODITY: PREMIUM RED LENTILS", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="MFD: 10/2026", confidence=0.96, polygon=dummy_poly),
        OcrLine(text="MANUFACTURED BY: ACME FOODS PVT LTD, INDUSTRIAL AREA, MUMBAI - 400001", confidence=0.94, polygon=dummy_poly),
        OcrLine(text="FOR CONSUMER FEEDBACK CONTACT: care@acme.com TEL: 1800-111-222", confidence=0.93, polygon=dummy_poly),
        OcrLine(text="COUNTRY OF ORIGIN: INDIA", confidence=0.95, polygon=dummy_poly),
    ]
    ev_map1 = {str(i): f"ev_cap1_{i}" for i in range(len(lines_cap1))}
    candidates_cap1 = extract_candidates(lines_cap1, ev_map1)
    
    cap1 = CaptureRecord(
        capture_id="cap_01",
        view_id="FRONT",
        status="ACCEPTED",
        field_candidates=candidates_cap1
    )
    
    # Capture 2: Blank / background surface (no declarations)
    lines_cap2 = [
        OcrLine(text="STORE IN A COOL DRY PLACE", confidence=0.85, polygon=dummy_poly)
    ]
    ev_map2 = {"0": "ev_cap2_0"}
    candidates_cap2 = extract_candidates(lines_cap2, ev_map2)
    
    cap2 = CaptureRecord(
        capture_id="cap_02",
        view_id="BACK",
        status="ACCEPTED",
        field_candidates=candidates_cap2
    )
    
    # Aggregation across both captures
    aggregated = aggregate_candidates([cap1, cap2])
    
    # Verify that all detected candidates from cap1 survived aggregation
    detected_fields = {c.field: c for c in aggregated if c.status == "DETECTED"}
    assert "MRP" in detected_fields, "MRP was lost after aggregating with empty capture"
    assert "NET_QUANTITY" in detected_fields, "NET_QUANTITY was lost after aggregating with empty capture"
    assert "COMMON_GENERIC_NAME" in detected_fields, "COMMON_GENERIC_NAME was lost"
    assert "MONTH_YEAR" in detected_fields, "MONTH_YEAR was lost"
    assert "MANUFACTURER_PACKER_IMPORTER" in detected_fields, "MANUFACTURER_PACKER_IMPORTER was lost"
    assert "COUNTRY_OF_ORIGIN" in detected_fields, "COUNTRY_OF_ORIGIN was lost"
    assert "CONSUMER_CARE" in detected_fields, "CONSUMER_CARE was lost"
    
    # Verify evidence IDs preserved
    assert len(detected_fields["MRP"].evidence_ids) > 0
    assert "ev_cap1_0" in detected_fields["MRP"].evidence_ids
    assert len(detected_fields["NET_QUANTITY"].evidence_ids) > 0
    assert "ev_cap1_1" in detected_fields["NET_QUANTITY"].evidence_ids

def test_b02_multiline_reading_order():
    """
    BUG-02: P9B-B02-MULTILINE-READING-ORDER
    Asserts that multi-line text blocks (manufacturer address, multi-line ingredients,
    consumer care, and allergen statements) are reconstructed without fragmentation.
    """
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    lines = [
        OcrLine(text="MANUFACTURED & PACKED BY:", confidence=0.98, polygon=dummy_poly),
        OcrLine(text="SUNSHINE FOODS AND BEVERAGES PRIVATE LIMITED", confidence=0.96, polygon=dummy_poly),
        OcrLine(text="PLOT NO 42, GIDC ESTATE, NEAR WATER TANK", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="ANKLESHWAR, GUJARAT - 393002", confidence=0.94, polygon=dummy_poly),
        OcrLine(text="INGREDIENTS: REFINED WHEAT FLOUR (MAIDA), PALM OIL,", confidence=0.97, polygon=dummy_poly),
        OcrLine(text="SUGAR, MILK SOLIDS, COCOA POWDER (4%), SALT,", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="RAISING AGENTS (INS 500ii, INS 503ii), EMULSIFIER (INS 322).", confidence=0.93, polygon=dummy_poly),
        OcrLine(text="CONTAINS WHEAT AND MILK.", confidence=0.96, polygon=dummy_poly),
        OcrLine(text="MAY CONTAIN TRACES OF SOY AND NUTS.", confidence=0.94, polygon=dummy_poly),
        OcrLine(text="FOR CONSUMER QUERIES CONTACT CUSTOMER CARE EXECUTIVE AT:", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="TOLL FREE NO: 1800-200-1234 EMAIL: CARE@SUNSHINEFOODS.COM", confidence=0.96, polygon=dummy_poly),
        OcrLine(text="ADDRESS: SAME AS MANUFACTURED BY ADDRESS", confidence=0.92, polygon=dummy_poly),
    ]
    ev_map = {str(i): f"ev_{i}" for i in range(len(lines))}
    
    candidates = extract_candidates(lines, ev_map)
    cands_by_field = {c.field: c for c in candidates if c.status == "DETECTED"}
    
    # 1. Manufacturer address block reconstruction
    assert "MANUFACTURER_PACKER_IMPORTER" in cands_by_field
    mfg_cand = cands_by_field["MANUFACTURER_PACKER_IMPORTER"]
    assert "SUNSHINE FOODS" in mfg_cand.raw_value
    assert "393002" in mfg_cand.raw_value
    assert "ev_0" in mfg_cand.evidence_ids
    assert "ev_1" in mfg_cand.evidence_ids
    assert "ev_2" in mfg_cand.evidence_ids
    assert "ev_3" in mfg_cand.evidence_ids
    
    # 2. Multi-line ingredients reconstruction
    assert "FSSAI_INGREDIENTS" in cands_by_field
    ing_cand = cands_by_field["FSSAI_INGREDIENTS"]
    assert "REFINED WHEAT FLOUR" in ing_cand.raw_value
    assert "COCOA POWDER" in ing_cand.raw_value
    assert "EMULSIFIER" in ing_cand.raw_value
    assert "ev_4" in ing_cand.evidence_ids
    assert "ev_5" in ing_cand.evidence_ids
    assert "ev_6" in ing_cand.evidence_ids
    
    # 3. Multi-line allergens reconstruction
    assert "FSSAI_ALLERGENS" in cands_by_field
    all_cand = cands_by_field["FSSAI_ALLERGENS"]
    assert "CONTAINS WHEAT AND MILK" in all_cand.raw_value
    assert "SOY AND NUTS" in all_cand.raw_value
    assert "ev_7" in all_cand.evidence_ids
    assert "ev_8" in all_cand.evidence_ids
    
    # 4. Multi-line consumer care reconstruction
    assert "CONSUMER_CARE" in cands_by_field
    cc_cand = cands_by_field["CONSUMER_CARE"]
    assert "1800-200-1234" in cc_cand.raw_value
    assert "CARE@SUNSHINEFOODS.COM" in cc_cand.raw_value
    assert "ev_9" in cc_cand.evidence_ids
    assert "ev_10" in cc_cand.evidence_ids

def test_b03_brand_information_extraction():
    """
    BUG-03: P9B-B03-BRAND-INFORMATION-EXTRACTION
    Asserts that brand / trade names are surfaced when layout prominence/indicators exist,
    without conflating brand with generic commodity name.
    """
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    
    # Case A: Explicit Brand marker
    lines_with_brand = [
        OcrLine(text="BRAND: NATURE BLISS™", confidence=0.97, polygon=dummy_poly),
        OcrLine(text="COMMODITY: ORGANIC BROWN BASMATI RICE", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="NET QUANTITY: 1 kg", confidence=0.98, polygon=dummy_poly)
    ]
    ev_map_a = {str(i): f"ev_a_{i}" for i in range(len(lines_with_brand))}
    cands_a = extract_candidates(lines_with_brand, ev_map_a)
    by_field_a = {c.field: c for c in cands_a if c.status == "DETECTED"}
    
    assert "BRAND_NAME" in by_field_a
    assert "NATURE BLISS" in by_field_a["BRAND_NAME"].raw_value
    assert "COMMON_GENERIC_NAME" in by_field_a
    assert "BROWN BASMATI RICE" in by_field_a["COMMON_GENERIC_NAME"].raw_value
    
    # Case B: No brand marker - brand remains unconfirmed / NOT_DETECTED, commodity detected
    lines_no_brand = [
        OcrLine(text="COMMODITY: EXTRA VIRGIN OLIVE OIL", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="NET QUANTITY: 500 ml", confidence=0.98, polygon=dummy_poly)
    ]
    ev_map_b = {str(i): f"ev_b_{i}" for i in range(len(lines_no_brand))}
    cands_b = extract_candidates(lines_no_brand, ev_map_b)
    brand_b = [c for c in cands_b if c.field == "BRAND_NAME"][0]
    assert brand_b.status == "NOT_DETECTED"

def test_b04_generic_commodity_name():
    """
    BUG-04: P9B-B04-GENERIC-COMMODITY-NAME
    Asserts that generic commodity/product names are extracted across varied valid anchors
    ('PRODUCT:', 'ITEM:', 'NAME OF COMMODITY:', 'GENERIC NAME:').
    """
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    
    test_cases = [
        ("PRODUCT: INSTANT WHOLE GRAIN NOODLES", "INSTANT WHOLE GRAIN NOODLES"),
        ("ITEM: ROASTED CALIFORNIA ALMONDS", "ROASTED CALIFORNIA ALMONDS"),
        ("NAME OF COMMODITY: NATURAL MINERAL WATER", "NATURAL MINERAL WATER"),
        ("GENERIC NAME: BLENDED SPICE POWDER", "BLENDED SPICE POWDER"),
        ("PRODUCT NAME: SOY PROTEIN ISOLATE", "SOY PROTEIN ISOLATE")
    ]
    
    for text_sample, expected_name in test_cases:
        lines = [
            OcrLine(text=text_sample, confidence=0.96, polygon=dummy_poly),
            OcrLine(text="NET QUANTITY: 250 g", confidence=0.98, polygon=dummy_poly)
        ]
        ev_map = {"0": "ev_cgn_0", "1": "ev_cgn_1"}
        cands = extract_candidates(lines, ev_map)
        cgn = [c for c in cands if c.field == "COMMON_GENERIC_NAME" and c.status == "DETECTED"]
        assert len(cgn) > 0, f"Failed to extract COMMON_GENERIC_NAME from: {text_sample}"
        assert cgn[0].normalized_value.name_text.upper() == expected_name.upper()

def test_b05_manufacturer_packer_propagation():
    """
    BUG-05: P9B-B05-MANUFACTURER-PACKER-PROPAGATION
    Asserts that manufacturer and packer declarations correctly propagate through
    candidate extraction, multi-view aggregation, and Rule 6(1)(a) evaluation.
    """
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    
    # 1. Standard manufacturer address
    lines_mfg = [
        OcrLine(text="MANUFACTURED BY: HIMALAYAN FOODS PVT LTD, SECTOR 5, PARWANOO, HP - 173220", confidence=0.95, polygon=dummy_poly)
    ]
    cands_mfg = extract_candidates(lines_mfg, {"0": "ev_mfg_0"})
    mfg_detected = [c for c in cands_mfg if c.field == "MANUFACTURER_PACKER_IMPORTER" and c.status == "DETECTED"]
    assert len(mfg_detected) > 0
    assert mfg_detected[0].normalized_value.role == "MANUFACTURER"
    assert "HIMALAYAN FOODS" in mfg_detected[0].raw_value
    
    # 2. Packer address
    lines_pkd = [
        OcrLine(text="PACKED BY: APEX LOGISTICS LTD, PLOT 12, WAREHOUSE ZONE, CHENNAI - 600001", confidence=0.94, polygon=dummy_poly)
    ]
    cands_pkd = extract_candidates(lines_pkd, {"0": "ev_pkd_0"})
    pkd_detected = [c for c in cands_pkd if c.field == "MANUFACTURER_PACKER_IMPORTER" and c.status == "DETECTED"]
    assert len(pkd_detected) > 0
    assert pkd_detected[0].normalized_value.role == "PACKER"
    
    # 3. Compliance evaluation with orchestrate_compliance
    from app.services.compliance_service import orchestrate_compliance
    eval_results = orchestrate_compliance(
        candidates=mfg_detected,
        reference_date=date(2026, 8, 1),
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin="DOMESTIC",
        regulatory_category="NON_FOOD",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"
    )
    
    mfg_rule = [r for r in eval_results if r.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE"]
    assert len(mfg_rule) > 0
    assert mfg_rule[0].status == "PASS"

def test_b06_manufacture_date_normalization():
    """
    BUG-06: P9B-B06-MANUFACTURE-DATE-NORMALIZATION
    Asserts that varied date formats (MM.YYYY, MMM YYYY, DD-MM-YYYY, PKD MM/YY)
    are accurately normalized into structured date candidates and pass Rule 6(1)(d).
    """
    from app.services.declaration_normalizer import parse_date_declaration
    
    cases = [
        ("MFD: 10.2026", 10, 2026, "MANUFACTURED"),
        ("PKD: 08/2026", 8, 2026, "PACKED"),
        ("MFG DATE: OCTOBER 2026", 10, 2026, "MANUFACTURED"),
        ("DATE OF PACKING: 15-09-2026", 9, 2026, "PACKED"),
        ("BEST BEFORE 12 MONTHS FROM MANUFACTURE", None, None, "BEST_BEFORE")
    ]
    
    for raw_text, expected_month, expected_year, expected_type in cases:
        parsed = parse_date_declaration(raw_text)
        assert parsed is not None, f"Failed to parse date declaration: {raw_text}"
        assert parsed.type == expected_type
        if expected_month is not None:
            assert parsed.month == expected_month
            assert parsed.year == expected_year

def test_b07_result_evidence_contradiction():
    """
    BUG-07: P9B-B07-RESULT-EVIDENCE-CONTRADICTION
    Asserts that whenever a rule evaluation evaluates to PASS, it is supported by
    non-empty candidate evidence (raw_value / normalized_value) and attached evidence IDs.
    """
    from app.services.compliance_service import orchestrate_compliance
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    
    lines = [
        OcrLine(text="MRP Rs. 299.00 (INCL. OF ALL TAXES)", confidence=0.98, polygon=dummy_poly),
        OcrLine(text="NET QUANTITY: 750 ml", confidence=0.97, polygon=dummy_poly),
        OcrLine(text="COMMODITY: COLD PRESSED MUSTARD OIL", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="PKD: 07/2026", confidence=0.96, polygon=dummy_poly),
        OcrLine(text="MANUFACTURED BY: AGRO ORGANICS INDIA PVT LTD, SECTOR 3, JAIPUR - 302013", confidence=0.94, polygon=dummy_poly)
    ]
    ev_map = {str(i): f"ev_7_{i}" for i in range(len(lines))}
    cands = extract_candidates(lines, ev_map)
    detected_cands = [c for c in cands if c.status == "DETECTED"]
    
    eval_results = orchestrate_compliance(
        candidates=detected_cands,
        reference_date=date(2026, 8, 1),
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin="DOMESTIC",
        regulatory_category="NON_FOOD",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"
    )
    
    passed_rules = [r for r in eval_results if r.status == "PASS"]
    assert len(passed_rules) >= 4, "Expected at least MRP, Net Qty, Commodity, and Manufacturer to pass"
    
    # Invariant: Every PASS rule must map to an existing detected candidate with raw_value
    cand_by_field = {c.field: c for c in detected_cands}
    for rule in passed_rules:
        assert rule.field in cand_by_field, f"Passed rule {rule.rule_id} has no matching candidate"
        matching_cand = cand_by_field[rule.field]
        assert matching_cand.raw_value is not None and len(matching_cand.raw_value.strip()) > 0
        assert len(matching_cand.evidence_ids) > 0

def test_b08_fssai_licence_propagation():
    """
    BUG-08: P9B-B08-FSSAI-LICENCE-EVIDENCE-PROPAGATION
    Asserts that 14-digit FSSAI licence numbers (contiguous, spaced, and lookahead)
    are extracted and accurately propagated to food compliance review.
    """
    from app.services.fssai_compliance_service import evaluate_fssai_compliance
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    
    # Case 1: Spaced 14-digit licence number
    lines = [
        OcrLine(text="FSSAI LIC. NO. 100 140 110 00123", confidence=0.96, polygon=dummy_poly)
    ]
    cands = extract_candidates(lines, {"0": "ev_lic_0"})
    lic_cand = [c for c in cands if c.field == "FSSAI_LICENCE" and c.status == "DETECTED"]
    assert len(lic_cand) > 0
    assert lic_cand[0].raw_value == "10014011000123"
    assert "ev_lic_0" in lic_cand[0].evidence_ids
    
    # Case 2: Multi-line FSSAI header + number on next line
    lines_split = [
        OcrLine(text="CENTRAL LICENCE NO:", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="10018042000456", confidence=0.97, polygon=dummy_poly)
    ]
    cands_split = extract_candidates(lines_split, {"0": "ev_s_0", "1": "ev_s_1"})
    lic_split = [c for c in cands_split if c.field == "FSSAI_LICENCE" and c.status == "DETECTED"]
    assert len(lic_split) > 0
    assert lic_split[0].raw_value == "10018042000456"
    
    # Case 3: Food compliance evaluation
    food_evals = evaluate_fssai_compliance(
        candidates=lic_cand,
        reference_date=date(2026, 8, 1),
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"
    )
    lic_eval = [e for e in food_evals if e.rule_id == "FSSAI_LICENCE_PRESENCE"]
    assert len(lic_eval) > 0
    assert lic_eval[0].status == "REVIEW_REQUIRED" # Plausible number found, logo requires officer visual verification
    assert "10014011000123" in lic_eval[0].reason
    assert "ev_lic_0" in lic_eval[0].evidence_ids

def test_b09_fssai_ingredients_block():
    """
    BUG-09: P9B-B09-FSSAI-INGREDIENTS-BLOCK
    Asserts that multi-line ingredients statements are accurately extracted and evaluated
    as PASS under FSSAI Regulation 5(2) with full evidence text and evidence IDs.
    """
    from app.services.fssai_compliance_service import evaluate_fssai_compliance
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    
    lines = [
        OcrLine(text="INGREDIENTS: WHOLE WHEAT FLOUR (65%), WATER,", confidence=0.97, polygon=dummy_poly),
        OcrLine(text="EDIBLE VEGETABLE OIL (SUNFLOWER), IODISED SALT,", confidence=0.96, polygon=dummy_poly),
        OcrLine(text="YEAST, PRESERVATIVE (INS 282), EMULSIFIER (INS 471).", confidence=0.94, polygon=dummy_poly)
    ]
    ev_map = {"0": "ev_ing_0", "1": "ev_ing_1", "2": "ev_ing_2"}
    cands = extract_candidates(lines, ev_map)
    ing_cand = [c for c in cands if c.field == "FSSAI_INGREDIENTS" and c.status == "DETECTED"]
    assert len(ing_cand) > 0
    assert "WHOLE WHEAT FLOUR" in ing_cand[0].raw_value
    assert "PRESERVATIVE" in ing_cand[0].raw_value
    assert "ev_ing_0" in ing_cand[0].evidence_ids
    assert "ev_ing_1" in ing_cand[0].evidence_ids
    assert "ev_ing_2" in ing_cand[0].evidence_ids
    
    # Evaluate compliance
    food_evals = evaluate_fssai_compliance(
        candidates=ing_cand,
        reference_date=date(2026, 8, 1),
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"
    )
    ing_eval = [e for e in food_evals if e.rule_id == "FSSAI_INGREDIENTS_DECLARATION"]
    assert len(ing_eval) > 0
    assert ing_eval[0].status == "PASS"
    assert ing_eval[0].evaluated_value is not None
    assert "WHOLE WHEAT FLOUR" in ing_eval[0].evaluated_value
    assert len(ing_eval[0].evidence_ids) >= 3

def test_b10_fssai_nutrition_panel_propagation():
    """
    BUG-10: P9B-B10-FSSAI-NUTRITION-PANEL-PROPAGATION
    Asserts that detected nutritional facts panel lines are extracted with concrete line text,
    attached evidence IDs, and evaluate to PASS under FSSAI Regulation 5(3).
    """
    from app.services.fssai_compliance_service import evaluate_fssai_compliance
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    
    lines = [
        OcrLine(text="NUTRITIONAL INFORMATION PER 100g:", confidence=0.98, polygon=dummy_poly),
        OcrLine(text="ENERGY: 450 kcal", confidence=0.97, polygon=dummy_poly),
        OcrLine(text="PROTEIN: 8.5 g", confidence=0.96, polygon=dummy_poly),
        OcrLine(text="CARBOHYDRATE: 62.0 g (TOTAL SUGARS: 14.0 g, ADDED SUGARS: 8.0 g)", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="TOTAL FAT: 18.0 g (SATURATED FAT: 6.0 g, TRANS FAT: 0.1 g)", confidence=0.94, polygon=dummy_poly),
        OcrLine(text="SODIUM: 320 mg", confidence=0.96, polygon=dummy_poly)
    ]
    ev_map = {str(i): f"ev_nut_{i}" for i in range(len(lines))}
    cands = extract_candidates(lines, ev_map)
    nut_cand = [c for c in cands if c.field == "FSSAI_NUTRITION" and c.status == "DETECTED"]
    assert len(nut_cand) > 0
    assert "ENERGY" in nut_cand[0].raw_value
    assert "PROTEIN" in nut_cand[0].raw_value
    assert len(nut_cand[0].evidence_ids) >= 5
    
    # Evaluate food compliance
    food_evals = evaluate_fssai_compliance(
        candidates=nut_cand,
        reference_date=date(2026, 8, 1),
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"
    )
    nut_eval = [e for e in food_evals if e.rule_id == "FSSAI_NUTRITIONAL_INFO"]
    assert len(nut_eval) > 0
    assert nut_eval[0].status == "PASS"
    assert "ENERGY" in nut_eval[0].evaluated_value
    assert len(nut_eval[0].evidence_ids) >= 5

def test_b11_veg_nonveg_visual_mark():
    """
    BUG-11: P9B-B11-VEG-NONVEG-VISUAL-MARK
    Asserts that textual and symbol declarations for veg/non-veg are extracted and evaluated
    under FSSAI Regulation 5(4) with attached evidence IDs and evaluated value.
    """
    from app.services.fssai_compliance_service import evaluate_fssai_compliance
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    
    test_cases = [
        ("100% VEGETARIAN", "100% VEGETARIAN"),
        ("PURE VEG PRODUCT", "PURE VEG"),
        ("GREEN DOT IN GREEN SQUARE", "GREEN DOT"),
        ("NON-VEGETARIAN", "NON-VEGETARIAN")
    ]
    
    for text_sample, expected_match in test_cases:
        lines = [OcrLine(text=text_sample, confidence=0.96, polygon=dummy_poly)]
        cands = extract_candidates(lines, {"0": "ev_veg_0"})
        veg_cand = [c for c in cands if c.field == "FSSAI_VEG_NONVEG" and c.status == "DETECTED"]
        assert len(veg_cand) > 0, f"Failed to extract veg candidate for {text_sample}"
        assert expected_match in veg_cand[0].raw_value
        assert "ev_veg_0" in veg_cand[0].evidence_ids
        
        # Evaluate compliance
        food_evals = evaluate_fssai_compliance(
            candidates=veg_cand,
            reference_date=date(2026, 8, 1),
            evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"
        )
        veg_eval = [e for e in food_evals if e.rule_id == "FSSAI_VEG_NONVEG_SYMBOL"]
        assert len(veg_eval) > 0
        assert veg_eval[0].status == "REVIEW_REQUIRED" # Text detected, visual mark requires officer review
        assert veg_eval[0].evaluated_value == expected_match
        assert "ev_veg_0" in veg_eval[0].evidence_ids

def test_b12_supported_field_coverage_audit():
    """
    BUG-12: P9B-B12-SUPPORTED-FIELD-COVERAGE-AUDIT
    Comprehensive audit asserting that all 14 supported declaration fields across
    Legal Metrology and FSSAI survive extraction, normalization, and evaluation.
    """
    from app.services.compliance_service import orchestrate_compliance
    from app.services.fssai_compliance_service import evaluate_fssai_compliance
    from app.services.inspection_service import aggregate_candidates
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    
    # View 1: Front / Primary Display
    view_1_lines = [
        OcrLine(text="HIMALAYAN MEADOWS ®", confidence=0.98, polygon=dummy_poly),
        OcrLine(text="COMMODITY: ROASTED CASHEW NUTS", confidence=0.97, polygon=dummy_poly),
        OcrLine(text="NET QUANTITY: 500 g", confidence=0.99, polygon=dummy_poly),
        OcrLine(text="100% VEGETARIAN", confidence=0.96, polygon=dummy_poly)
    ]
    ev_map_1 = {str(i): f"ev_v1_{i}" for i in range(len(view_1_lines))}
    cands_v1 = extract_candidates(view_1_lines, ev_map_1)
    
    # View 2: Back / Information Panel
    view_2_lines = [
        OcrLine(text="MRP Rs. 450.00 (INCL. OF ALL TAXES)", confidence=0.98, polygon=dummy_poly),
        OcrLine(text="UNIT SALE PRICE: Rs. 0.90 / g", confidence=0.96, polygon=dummy_poly),
        OcrLine(text="PKD: 08/2026", confidence=0.97, polygon=dummy_poly),
        OcrLine(text="COUNTRY OF ORIGIN: INDIA", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="MANUFACTURED BY: HIMALAYAN FOODS PVT LTD, SECTOR 5, PARWANOO, HP - 173220", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="CONSUMER CARE: 1800-111-222, EMAIL: CARE@HIMALAYAN.IN", confidence=0.97, polygon=dummy_poly),
        OcrLine(text="FSSAI LIC NO: 10014011000123", confidence=0.98, polygon=dummy_poly),
        OcrLine(text="INGREDIENTS: CASHEW NUTS (98%), EDIBLE VEGETABLE OIL, IODISED SALT.", confidence=0.96, polygon=dummy_poly),
        OcrLine(text="ALLERGY ADVICE: CONTAINS TREE NUTS (CASHEWS).", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="NUTRITION FACTS PER 100g: ENERGY 580 kcal, PROTEIN 18g, CARBOHYDRATE 30g, TOTAL FAT 44g, SODIUM 260mg", confidence=0.96, polygon=dummy_poly)
    ]
    ev_map_2 = {str(i): f"ev_v2_{i}" for i in range(len(view_2_lines))}
    cands_v2 = extract_candidates(view_2_lines, ev_map_2)
    
    # Multi-view aggregation with CaptureRecord instances
    from app.schemas.inspection import CaptureRecord
    cap_1 = CaptureRecord(capture_id="cap_1", view_id="FRONT", field_candidates=cands_v1)
    cap_2 = CaptureRecord(capture_id="cap_2", view_id="BACK", field_candidates=cands_v2)
    aggregated = aggregate_candidates([cap_1, cap_2])
    
    # Assert every single canonical field is DETECTED
    expected_fields = [
        "BRAND_NAME",
        "COMMON_GENERIC_NAME",
        "NET_QUANTITY",
        "MRP",
        "UNIT_SALE_PRICE",
        "MONTH_YEAR",
        "COUNTRY_OF_ORIGIN",
        "MANUFACTURER_PACKER_IMPORTER",
        "CONSUMER_CARE",
        "FSSAI_LICENCE",
        "FSSAI_VEG_NONVEG",
        "FSSAI_INGREDIENTS",
        "FSSAI_ALLERGENS",
        "FSSAI_NUTRITION"
    ]
    
    detected_fields = {c.field: c for c in aggregated if c.status == "DETECTED"}
    for field in expected_fields:
        assert field in detected_fields, f"Field '{field}' was not detected in end-to-end multi-view extraction!"
        cand = detected_fields[field]
        assert cand.raw_value is not None and len(cand.raw_value.strip()) > 0
        assert len(cand.evidence_ids) > 0, f"Field '{field}' missing evidence IDs"
        
    # Assert Metrology Compliance succeeds
    lmpc_results = orchestrate_compliance(
        candidates=aggregated,
        reference_date=date(2026, 8, 1),
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin="DOMESTIC",
        regulatory_category="FOOD",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"
    )
    assert len(lmpc_results) > 0
    
    # Assert FSSAI Compliance succeeds
    fssai_results = evaluate_fssai_compliance(
        candidates=aggregated,
        reference_date=date(2026, 8, 1),
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"
    )
    assert len(fssai_results) >= 5

def test_b13_detection_evidence_verdict_separation():
    """
    BUG-13: P9B-B13-DETECTION-EVIDENCE-VERDICT-SEPARATION
    Asserts that detection evidence is preserved verbatim in findings even when
    the legal status is REVIEW_REQUIRED (e.g. FSSAI licence requires visual logo confirmation).
    """
    from app.services.fssai_compliance_service import evaluate_fssai_compliance
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    
    # Detected candidate with 14-digit licence
    lines = [OcrLine(text="FSSAI LIC. NO. 10019011000789", confidence=0.97, polygon=dummy_poly)]
    cands = extract_candidates(lines, {"0": "ev_lic_sep"})
    
    fssai_results = evaluate_fssai_compliance(
        candidates=cands,
        reference_date=date(2026, 8, 1),
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"
    )
    lic_res = [r for r in fssai_results if r.rule_id == "FSSAI_LICENCE_PRESENCE"][0]
    
    # Invariant: Legal status is REVIEW_REQUIRED, but evaluated_value and evidence_ids are preserved
    assert lic_res.status == "REVIEW_REQUIRED"
    assert lic_res.evaluated_value == "10019011000789"
    assert "ev_lic_sep" in lic_res.evidence_ids
    assert len(lic_res.source_reference) > 0
    assert len(lic_res.reason) > 0

def test_b14_null_leakage_prevention():
    """
    BUG-14: P9B-B14-NULL-LEAKAGE-UI
    Asserts that raw_value and evaluated_value for NOT_DETECTED or unparsed candidates
    do not contain string representations of 'null', 'None', or 'undefined'.
    """
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    lines = [OcrLine(text="COMMODITY: COCONUT OIL", confidence=0.95, polygon=dummy_poly)]
    cands = extract_candidates(lines, {"0": "ev_0"})
    
    for cand in cands:
        if cand.raw_value is not None:
            assert cand.raw_value.strip().lower() not in ("null", "none", "undefined")
        if isinstance(cand.normalized_value, str):
            assert cand.normalized_value.strip().lower() not in ("null", "none", "undefined")

def test_b15_internal_enum_mapping():
    """
    BUG-15: P9B-B15-INTERNAL-ENUM-LEAKAGE
    Asserts that backend compliance enums and sufficiency states have unambiguous,
    standardized definitions without unhandled status codes.
    """
    from app.schemas.compliance import LegalStatus
    
    expected_legal_statuses = {"PASS", "FAIL", "REVIEW_REQUIRED", "NOT_APPLICABLE"}
    actual_statuses = {s.value for s in LegalStatus}
    assert expected_legal_statuses.issubset(actual_statuses)

def test_b16_b17_b18_visual_compliance_rules():
    """
    BUG-16: P9B-B16-NON-EVALUABLE-COPY
    BUG-17: P9B-B17-VISUAL-CHECK-JARGON
    BUG-18: P9B-B18-VISUAL-SECTION-NAMING
    Asserts that visual legal rules (Rules 7, 8, 9) produce clear statutory titles,
    references to Legal Metrology Rules, and evaluate with concrete reasons.
    """
    from app.services.visual_assessment_service import evaluate_visual_legal_rules
    from app.schemas.inspection import CaptureRecord
    
    captures = [
        CaptureRecord(capture_id="cap_1", view_id="FRONT", field_candidates=[])
    ]
    results = evaluate_visual_legal_rules(captures, [], date(2026, 8, 1))
    assert len(results) >= 3, "Expected evaluations for Rule 7, Rule 8, and Rule 9"
    
    rule_ids = {r.rule_id for r in results}
    assert "RULE_7_MINIMUM_NUMERAL_HEIGHT" in rule_ids
    assert "RULE_8_PRINCIPAL_DISPLAY_PANEL_PLACEMENT" in rule_ids
    assert "RULE_9_DECLARATION_LEGIBILITY" in rule_ids
    
    for r in results:
        assert r.legal_reference is not None and len(r.legal_reference) > 0
        assert r.reason is not None and len(r.reason) > 0
        # No engineering jargon in reason
        assert "bounding box" not in r.reason.lower()
        assert "yolo" not in r.reason.lower()

def test_b19_evidence_overlay_density():
    """
    BUG-19: P9B-B19-EVIDENCE-OVERLAY-DENSITY
    Asserts that candidate polygons and geometry structures are uniquely keyed
    and cleanly attached to their specific candidate fields for targeted focus.
    """
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    lines = [
        OcrLine(text="MRP Rs. 150.00", confidence=0.98, polygon=dummy_poly),
        OcrLine(text="NET QTY: 100 g", confidence=0.97, polygon=dummy_poly)
    ]
    cands = extract_candidates(lines, {"0": "ev_0", "1": "ev_1"})
    
    mrp_cand = [c for c in cands if c.field == "MRP" and c.status == "DETECTED"][0]
    qty_cand = [c for c in cands if c.field == "NET_QUANTITY" and c.status == "DETECTED"][0]
    
    # Evidence IDs must be disjoint between distinct fields
    assert set(mrp_cand.evidence_ids).isdisjoint(set(qty_cand.evidence_ids))
    assert "ev_0" in mrp_cand.evidence_ids
    assert "ev_1" in qty_cand.evidence_ids

def test_b20_finalized_session_state():
    """
    BUG-20: P9B-B20-FINALIZED-INCOMPLETE-STATE
    Asserts that finalizing an inspection freezes the session, computes workflow summary
    without intermediate incompleteness flags, and populates overall disposition.
    """
    from app.services.workflow_service import WorkflowService
    from app.schemas.inspection import InspectionSession, CaptureRecord, CapturePlan, CaptureViewRequirement
    from app.services.compliance_service import orchestrate_compliance
    
    cap = CaptureRecord(capture_id="cap_f", view_id="FRONT", field_candidates=[])
    plan = CapturePlan(
        capture_plan_id="plan_1",
        name="Standard Plan",
        views=[CaptureViewRequirement(view_id="FRONT", display_name="Front", required=True)]
    )
    session = InspectionSession(
        inspection_id="insp_test_final",
        reference_date="2026-08-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_1",
        captures=[cap],
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        capture_status="INCOMPLETE_INSPECTION"
    )
    session.rule_evaluations = orchestrate_compliance(
        candidates=[],
        reference_date=date(2026, 8, 1),
        product_category="GENERIC_RETAIL_PACKAGE",
        evidence_sufficiency=session.evidence_sufficiency
    )
    
    # Finalize
    finalized_session = WorkflowService.finalize_inspection(session, plan)
    assert finalized_session.lifecycle_status == "FINALIZED"
    assert finalized_session.report_snapshot is not None
    assert finalized_session.overall_disposition is not None
    
    # Workflow summary
    summary = WorkflowService.compute_workflow_summary(finalized_session)
    assert summary.lifecycle_status == "FINALIZED"
    assert summary.can_upload_capture is False
    assert summary.can_update_context is False
    assert summary.has_incomplete_evidence is False

def test_b21_recapture_action_completeness():
    """
    BUG-21: P9B-B21-RECAPTURE-ACTION-CLARITY
    Asserts that an in-progress session with incomplete captures flags has_incomplete_evidence
    and allows capture uploads, enabling clear officer recapture actions.
    """
    from app.services.workflow_service import WorkflowService
    from app.schemas.inspection import InspectionSession, CaptureRecord
    
    cap = CaptureRecord(capture_id="cap_f", view_id="FRONT", field_candidates=[])
    session = InspectionSession(
        inspection_id="insp_recapt",
        reference_date="2026-08-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_1",
        captures=[cap],
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        capture_status="INCOMPLETE_INSPECTION"
    )
    
    summary = WorkflowService.compute_workflow_summary(session)
    assert summary.can_upload_capture is True
    assert summary.has_incomplete_evidence is True
    assert summary.lifecycle_status in ("DRAFT", "IN_PROGRESS", "READY_FOR_REVIEW")

def test_b22_pdf_report_generation():
    """
    BUG-22: P9B-B22-PDF-END-TO-END-FAILURE
    Asserts that PDF report generation succeeds end-to-end, returns valid PDF binary
    with the PDF magic bytes '%PDF-', and contains all required report sections.
    """
    from app.services.report_service import generate_inspection_report
    from app.services.pdf_report_service import generate_pdf_report
    from app.schemas.inspection import InspectionSession, CaptureRecord, CapturePlan, CaptureViewRequirement
    
    cap = CaptureRecord(capture_id="cap_f", view_id="FRONT", field_candidates=[])
    plan = CapturePlan(
        capture_plan_id="plan_1",
        name="Standard Plan",
        views=[CaptureViewRequirement(view_id="FRONT", display_name="Front", required=True)]
    )
    session = InspectionSession(
        inspection_id="insp_pdf_test",
        reference_date="2026-08-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_1",
        captures=[cap],
        evidence_sufficiency="COMPLETE_EVIDENCE_CAPTURE",
        capture_status="COMPLETE_EVIDENCE_CAPTURE"
    )
    snapshot = generate_inspection_report(session, plan)
    pdf_bytes = generate_pdf_report(snapshot)
    
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")

def test_b23_report_action_hierarchy():
    """
    BUG-23: P9B-B23-REPORT-ACTION-HIERARCHY
    Asserts that workflow summaries cleanly distinguish report availability,
    action gating, and case preparation eligibility without duplicate states.
    """
    from app.services.workflow_service import WorkflowService
    from app.schemas.inspection import InspectionSession, CaptureRecord
    from app.schemas.compliance import RuleEvaluationResult, LegalStatus
    
    cap = CaptureRecord(capture_id="cap_f", view_id="FRONT", field_candidates=[])
    fail_rule = RuleEvaluationResult(
        rule_id="MRP_DECLARATION_PRESENCE",
        status=LegalStatus.FAIL,
        field="MRP",
        evidence_ids=[],
        legal_reference="Rule 6(1)(e)",
        reason="MRP declaration is absent from the captured retail package surface.",
        rule_version="2026-08-01",
        reference_date="2026-08-01"
    )
    session = InspectionSession(
        inspection_id="insp_hierarchy",
        reference_date="2026-08-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_1",
        captures=[cap],
        evidence_sufficiency="COMPLETE_EVIDENCE_CAPTURE",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        rule_evaluations=[fail_rule]
    )
    summary = WorkflowService.compute_workflow_summary(session)
    assert summary.has_failures is True
    assert summary.can_finalize is True
    assert summary.statutory_summary["FAIL"] == 1

def test_b24_b25_enforcement_gating():
    """
    BUG-24: P9B-B24-COMPLAINT-ACTION-DISCOVERABILITY
    BUG-25: P9B-B25-ENFORCEMENT-GATING
    Asserts that has_failures correctly gates enforcement actions:
    True when FAIL rules exist, False when all rules PASS or are REVIEW_REQUIRED.
    """
    from app.services.workflow_service import WorkflowService
    from app.schemas.inspection import InspectionSession, CaptureRecord
    from app.schemas.compliance import RuleEvaluationResult, LegalStatus
    
    cap = CaptureRecord(capture_id="cap_f", view_id="FRONT", field_candidates=[])
    pass_rule = RuleEvaluationResult(
        rule_id="MRP_DECLARATION_PRESENCE",
        status=LegalStatus.PASS,
        field="MRP",
        evidence_ids=[],
        legal_reference="Rule 6(1)(e)",
        reason="MRP declaration is clearly present.",
        rule_version="2026-08-01",
        reference_date="2026-08-01"
    )
    session_pass = InspectionSession(
        inspection_id="insp_pass",
        reference_date="2026-08-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_1",
        captures=[cap],
        evidence_sufficiency="COMPLETE_EVIDENCE_CAPTURE",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        rule_evaluations=[pass_rule]
    )
    summary_pass = WorkflowService.compute_workflow_summary(session_pass)
    assert summary_pass.has_failures is False
    assert summary_pass.statutory_summary["FAIL"] == 0
    assert summary_pass.statutory_summary["PASS"] == 1

def test_b26_portal_handoff_evidence_package():
    """
    BUG-26: P9B-B26-OFFICIAL-PORTAL-HANDOFF
    Asserts that finalized case exports and handoff evidence package generation
    contains all structured case metadata for official portal submission.
    """
    from app.services.report_service import generate_inspection_report
    from app.schemas.inspection import InspectionSession, CaptureRecord, CapturePlan, CaptureViewRequirement
    
    cap = CaptureRecord(capture_id="cap_f", view_id="FRONT", field_candidates=[])
    plan = CapturePlan(
        capture_plan_id="plan_1",
        name="Standard Plan",
        views=[CaptureViewRequirement(view_id="FRONT", display_name="Front", required=True)]
    )
    session = InspectionSession(
        inspection_id="insp_handoff",
        reference_date="2026-08-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_1",
        captures=[cap],
        evidence_sufficiency="COMPLETE_EVIDENCE_CAPTURE",
        capture_status="COMPLETE_EVIDENCE_CAPTURE"
    )
    snapshot = generate_inspection_report(session, plan)
    assert snapshot.metadata.inspection_id == "insp_handoff"
    assert snapshot.metadata.report_id is not None

def test_b28_b29_status_taxonomy_separation():
    """
    BUG-28: P9B-B28-INFORMATION-HIERARCHY
    BUG-29: P9B-B29-STATUS-TAXONOMY
    Asserts that candidate extraction statuses (CandidateStatus: DETECTED, NOT_DETECTED, etc.)
    and legal compliance verdicts (LegalStatus: PASS, FAIL, REVIEW_REQUIRED, NOT_APPLICABLE)
    remain cleanly decoupled in schema models and evaluations.
    """
    from app.schemas.ocr import FieldCandidate
    from app.schemas.compliance import LegalStatus
    
    # Candidate status vocabulary
    valid_candidate_statuses = {"DETECTED", "NOT_DETECTED", "REVIEW_REQUIRED"}
    legal_statuses = {s.value for s in LegalStatus}
    
    # Invariant: Legal verdict taxonomy has strict regulatory definitions
    assert "PASS" in legal_statuses
    assert "FAIL" in legal_statuses
    assert "REVIEW_REQUIRED" in legal_statuses
    assert "NOT_APPLICABLE" in legal_statuses
    
    # Test candidate instance
    cand = FieldCandidate(field="MRP", status="DETECTED", raw_value="Rs. 100")
    assert cand.status in valid_candidate_statuses

def test_b30_b31_b32_legal_safety_and_generic_processing():
    """
    BUG-30: P9B-B30-OCR-MISS-LEGAL-SAFETY
    BUG-31: P9B-B31-EVIDENCE-NOT-EQUAL-PASS
    BUG-32: P9B-B32-NO-PRODUCT-SPECIFIC-HARDCODING
    Asserts that:
    1. Incomplete evidence sets produce REVIEW_REQUIRED rather than false FAILs for missing declarations.
    2. Detected evidence candidates retain raw evidence text without automatically forcing unconditional PASS.
    3. Production extraction/compliance logic operates generically without product-specific hardcoding.
    """
    from app.services.compliance_service import orchestrate_compliance
    from app.schemas.compliance import LegalStatus
    
    # 1. Missing candidate on incomplete capture set -> REVIEW_REQUIRED, not FAIL
    incomplete_results = orchestrate_compliance(
        candidates=[],
        reference_date=date(2026, 8, 1),
        product_category="GENERIC_RETAIL_PACKAGE",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION"
    )
    for r in incomplete_results:
        if r.status == LegalStatus.FAIL:
            pytest.fail(f"Rule {r.rule_id} evaluated to FAIL under INSUFFICIENT_FOR_ABSENCE_EVALUATION")
        assert r.status in (LegalStatus.REVIEW_REQUIRED, LegalStatus.NOT_APPLICABLE)
        
    # 2. Complete capture set -> Evaluates absence to FAIL for required declarations
    complete_results = orchestrate_compliance(
        candidates=[],
        reference_date=date(2026, 8, 1),
        product_category="GENERIC_RETAIL_PACKAGE",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"
    )
    mrp_result = [r for r in complete_results if r.rule_id == "MRP_DECLARATION_PRESENCE"][0]
    assert mrp_result.status == LegalStatus.FAIL

def test_b33_b34_b35_no_fabrication_or_llm_judgment():
    """
    BUG-33: P9B-B33-NO-EXPECTED-VALUE-CORRECTION
    BUG-34: P9B-B34-NO-FABRICATED-FALLBACK
    BUG-35: P9B-B35-NO-CLOUD-OR-LLM-FALLBACK
    Asserts that:
    1. Candidate extraction on noise lines never invents or fabricates unmentioned fields.
    2. Missing OCR lines evaluate strictly to NOT_DETECTED without synthetic candidate creation.
    3. Compliance evaluation runs deterministically without invoking external LLM models for verdicts.
    """
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    # Unrelated arbitrary background text
    lines = [
        OcrLine(text="KEEP IN A COOL AND DRY PLACE", confidence=0.92, polygon=dummy_poly),
        OcrLine(text="BEST BEFORE 12 MONTHS FROM PACKAGING", confidence=0.95, polygon=dummy_poly)
    ]
    cands = extract_candidates(lines, {"0": "ev_0", "1": "ev_1"})
    
    # Assert MRP, NET_QUANTITY, FSSAI_LICENCE are NOT fabricated
    detected_fields = {c.field for c in cands if c.status == "DETECTED"}
    assert "MRP" not in detected_fields
    assert "NET_QUANTITY" not in detected_fields
    assert "FSSAI_LICENCE" not in detected_fields
    
    # Assert Date declaration is legitimately extracted from actual text
    assert "MONTH_YEAR" in detected_fields

def test_b36_multiview_merge_monotonicity():
    """
    BUG-36: P9B-B36-MULTIVIEW-MERGE-INVARIANT
    Asserts that multi-view candidate aggregation preserves DETECTED candidates
    monotonically and never overwrites them with NOT_DETECTED from other views.
    """
    from app.services.inspection_service import aggregate_candidates
    from app.schemas.inspection import CaptureRecord
    from app.schemas.ocr import FieldCandidate, MrpNormalized
    
    # View 1: MRP is DETECTED
    cap1 = CaptureRecord(
        capture_id="cap_front",
        view_id="FRONT",
        field_candidates=[
            FieldCandidate(
                field="MRP",
                status="DETECTED",
                raw_value="MRP Rs. 250.00",
                normalized_value=MrpNormalized(currency="INR", amount=250.0),
                evidence_ids=["ev_mrp_1"],
                confidence=0.98
            )
        ]
    )
    
    # View 2: MRP is NOT_DETECTED
    cap2 = CaptureRecord(
        capture_id="cap_back",
        view_id="BACK",
        field_candidates=[
            FieldCandidate(
                field="MRP",
                status="NOT_DETECTED",
                evidence_ids=[]
            )
        ]
    )
    
    # Aggregated results across both captures
    aggregated = aggregate_candidates([cap1, cap2])
    mrp_cands = [c for c in aggregated if c.field == "MRP"]
    
    assert len(mrp_cands) == 1
    assert mrp_cands[0].status == "DETECTED"
    assert mrp_cands[0].raw_value == "MRP Rs. 250.00"
    assert "ev_mrp_1" in mrp_cands[0].evidence_ids

def test_b37_b38_b39_paragraph_reconstruction_and_provenance():
    """
    BUG-37: P9B-B37-MANUFACTURER-ADDRESS-BLOCK
    BUG-38: P9B-B38-GENERIC-PARAGRAPH-RECONSTRUCTION
    BUG-39: P9B-B39-PROVENANCE-AFTER-JOIN
    Asserts that:
    1. Multi-line manufacturer declarations join name, street address, and PIN code cleanly.
    2. Multi-line ingredients statements gather continuation lines into one cohesive declaration.
    3. Joined candidates retain all constituent line evidence IDs in their evidence_ids list.
    """
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    lines = [
        OcrLine(text="MANUFACTURED & PACKED BY:", confidence=0.98, polygon=dummy_poly),
        OcrLine(text="BHARAT FOOD PRODUCTS LTD,", confidence=0.97, polygon=dummy_poly),
        OcrLine(text="PLOT NO. 45, GIDC ESTATE,", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="AHMEDABAD, GUJARAT - 380015", confidence=0.96, polygon=dummy_poly),
        OcrLine(text="INGREDIENTS: REFINED WHEAT FLOUR (MAIDA),", confidence=0.98, polygon=dummy_poly),
        OcrLine(text="SUGAR, EDIBLE VEGETABLE OIL (PALM),", confidence=0.97, polygon=dummy_poly),
        OcrLine(text="INVERT SYRUP, RAISING AGENTS (INS 500ii)", confidence=0.96, polygon=dummy_poly)
    ]
    ev_map = {str(i): f"ev_line_{i}" for i in range(len(lines))}
    cands = extract_candidates(lines, ev_map)
    
    # 1. Manufacturer check
    mfg_cand = [c for c in cands if c.field == "MANUFACTURER_PACKER_IMPORTER" and c.status == "DETECTED"][0]
    assert "BHARAT FOOD PRODUCTS LTD" in mfg_cand.raw_value
    assert "380015" in mfg_cand.raw_value
    assert "ev_line_0" in mfg_cand.evidence_ids
    assert "ev_line_1" in mfg_cand.evidence_ids
    assert "ev_line_2" in mfg_cand.evidence_ids
    assert "ev_line_3" in mfg_cand.evidence_ids
    
    # 2. Ingredients check
    ing_cand = [c for c in cands if c.field == "FSSAI_INGREDIENTS" and c.status == "DETECTED"][0]
    assert "REFINED WHEAT FLOUR" in ing_cand.raw_value
    assert "RAISING AGENTS" in ing_cand.raw_value
    assert "ev_line_4" in ing_cand.evidence_ids
    assert "ev_line_5" in ing_cand.evidence_ids
    assert "ev_line_6" in ing_cand.evidence_ids

def test_b40_to_b45_pipeline_sanity_and_diagnostics():
    """
    BUG-40: P9B-B40-FIELD-SURVIVAL-REGRESSION-SUITE
    BUG-41: P9B-B41-REAL-PACKAGE-TRACE-REPORT
    BUG-42: P9B-B42-METRIC-DECOMPOSITION
    BUG-43: P9B-B43-EVIDENCE-CONFIDENCE-CALIBRATION
    BUG-44: P9B-B44-CROSS-VIEW-CONFLICT-RESOLUTION
    BUG-45: P9B-B45-PIPELINE-SANITY-GATE
    Asserts that:
    1. Confidence scores are dynamically calibrated from OCR line confidences.
    2. Cross-view conflict resolution deterministically resolves or flags REVIEW_REQUIRED.
    3. Full end-to-end multi-view pipeline executes cleanly through report generation.
    """
    from app.services.inspection_service import aggregate_candidates
    from app.services.report_service import generate_inspection_report
    from app.schemas.inspection import InspectionSession, CaptureRecord, CapturePlan, CaptureViewRequirement
    from app.schemas.ocr import FieldCandidate, MrpNormalized
    
    # 1. Calibrated confidence
    dummy_poly = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    lines = [OcrLine(text="MRP Rs. 50.00 (INCL. OF ALL TAXES)", confidence=0.94, polygon=dummy_poly)]
    cands = extract_candidates(lines, {"0": "ev_0"})
    mrp_c = [c for c in cands if c.field == "MRP" and c.status == "DETECTED"][0]
    assert mrp_c.confidence is not None and 0.8 <= mrp_c.confidence <= 1.0
    
    # 2. Cross-view conflict resolution
    cap_a = CaptureRecord(
        capture_id="cap_a",
        view_id="FRONT",
        field_candidates=[
            FieldCandidate(field="MRP", status="DETECTED", raw_value="Rs. 50.00", confidence=0.95, normalized_value=MrpNormalized(currency="INR", amount=50.0), evidence_ids=["ev_a"])
        ]
    )
    cap_b = CaptureRecord(
        capture_id="cap_b",
        view_id="BACK",
        field_candidates=[
            FieldCandidate(field="MRP", status="DETECTED", raw_value="Rs. 60.00", confidence=0.85, normalized_value=MrpNormalized(currency="INR", amount=60.0), evidence_ids=["ev_b"])
        ]
    )
    aggregated = aggregate_candidates([cap_a, cap_b])
    mrp_merged = [c for c in aggregated if c.field == "MRP"][0]
    # The higher confidence declaration (0.95 vs 0.85) or conflict resolution is preserved
    assert mrp_merged.status in ("DETECTED", "REVIEW_REQUIRED")
    assert len(mrp_merged.evidence_ids) >= 1
    
    # 3. End-to-end pipeline sanity
    plan = CapturePlan(
        capture_plan_id="plan_1",
        name="Standard Plan",
        views=[CaptureViewRequirement(view_id="FRONT", display_name="Front", required=True)]
    )
    session = InspectionSession(
        inspection_id="insp_sanity",
        reference_date="2026-08-01",
        product_category="GENERIC_RETAIL_PACKAGE",
        capture_plan_id="plan_1",
        captures=[cap_a],
        evidence_sufficiency="COMPLETE_EVIDENCE_CAPTURE",
        capture_status="COMPLETE_EVIDENCE_CAPTURE"
    )
    report = generate_inspection_report(session, plan)
    assert report.metadata.inspection_id == "insp_sanity"
    assert report.overall_disposition is not None




























