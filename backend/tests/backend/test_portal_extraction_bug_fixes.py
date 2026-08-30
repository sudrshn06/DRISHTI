import pytest
from app.schemas.ocr import OcrLine, EvidenceItem
from app.services.candidate_extractor import extract_candidates
from app.services.declaration_normalizer import parse_consumer_care, parse_mrp, parse_date_declaration

def test_1_phone_extracted_from_separate_consumer_care_line():
    """
    Test 1: Consumer-care phone extracted when split across lines or on contact line.
    """
    lines = [
        OcrLine(text="FOR CONSUMER QUERIES CONTACT EXECUTIVE", confidence=0.95, polygon=[[0,0],[100,0],[100,20],[0,20]]),
        OcrLine(text="Toll Free Helpline: 1800 555 0199", confidence=0.94, polygon=[[0,25],[100,25],[100,45],[0,45]]),
        OcrLine(text="Email: care@example-brand.com", confidence=0.96, polygon=[[0,50],[100,50],[100,70],[0,70]]),
    ]
    evidence_map = {"0": "ev_cc_1", "1": "ev_cc_2", "2": "ev_cc_3"}
    candidates = extract_candidates(lines, evidence_map=evidence_map)
    
    cand = next((c for c in candidates if c.field == "CONSUMER_CARE"), None)
    assert cand is not None
    assert cand.status == "DETECTED"
    assert cand.normalized_value is not None
    assert cand.normalized_value.phone == "18005550199"
    assert cand.normalized_value.email.lower() == "care@example-brand.com"
    assert "ev_cc_1" in cand.evidence_ids
    assert "ev_cc_2" in cand.evidence_ids
    assert "ev_cc_3" in cand.evidence_ids

def test_2_spaced_and_hyphenated_phone_formats():
    """
    Test 2: Spaced, hyphenated, mobile, landline, and +91 phone formats parse correctly.
    """
    # Toll free spaced
    cc1 = parse_consumer_care("Customer Care: 1800 555 0199")
    assert cc1 is not None and cc1.phone == "18005550199"
    
    # +91 mobile spaced
    cc2 = parse_consumer_care("Ph: +91 98765 43210")
    assert cc2 is not None and cc2.phone == "+919876543210"
    
    # STD landline hyphenated
    cc3 = parse_consumer_care("Tel: 022-26851234")
    assert cc3 is not None and cc3.phone == "02226851234"
    
    # 10-digit contiguous mobile
    cc4 = parse_consumer_care("Helpline: 9876543210")
    assert cc4 is not None and cc4.phone == "9876543210"

def test_3_mrp_label_and_nearby_numeric_box_associate():
    """
    Test 3: MRP label in one OCR box and numeric value in next adjacent box associate.
    """
    lines = [
        OcrLine(text="MRP (INCL. OF ALL TAXES):", confidence=0.92, polygon=[[0,0],[100,0],[100,20],[0,20]]),
        OcrLine(text="₹ 245.00", confidence=0.95, polygon=[[0,25],[100,25],[100,45],[0,45]]),
    ]
    evidence_map = {"0": "ev_mrp_label", "1": "ev_mrp_val"}
    candidates = extract_candidates(lines, evidence_map=evidence_map)
    
    cand = next((c for c in candidates if c.field == "MRP"), None)
    assert cand is not None
    assert cand.status == "DETECTED"
    assert cand.normalized_value is not None
    assert cand.normalized_value.currency == "INR"
    assert cand.normalized_value.amount == 245.00
    assert "ev_mrp_label" in cand.evidence_ids
    assert "ev_mrp_val" in cand.evidence_ids

def test_4_unrelated_distant_heading_not_associated_with_mrp():
    """
    Test 4: If MRP label is followed by a completely different declaration heading,
    lookahead stops and does not absorb unrelated values.
    """
    lines = [
        OcrLine(text="MRP:", confidence=0.90, polygon=[[0,0],[100,0],[100,20],[0,20]]),
        OcrLine(text="NET WEIGHT: 500 g", confidence=0.95, polygon=[[0,25],[100,25],[100,45],[0,45]]),
    ]
    evidence_map = {"0": "ev_mrp", "1": "ev_nq"}
    candidates = extract_candidates(lines, evidence_map=evidence_map)
    
    mrp_cand = next((c for c in candidates if c.field == "MRP"), None)
    assert mrp_cand is not None
    assert mrp_cand.normalized_value is None
    assert mrp_cand.status == "REVIEW_REQUIRED"
    assert "ev_nq" not in mrp_cand.evidence_ids

def test_5_best_before_does_not_absorb_neighboring_barcode_digits():
    """
    Test 5: BEST BEFORE declaration does not append neighboring barcode digits.
    """
    lines = [
        OcrLine(text="BEST BEFORE 9 MONTHS FROM MANUFACTURE", confidence=0.94, polygon=[[0,0],[100,0],[100,20],[0,20]]),
        OcrLine(text="8 901234 567890", confidence=0.98, polygon=[[0,25],[100,25],[100,45],[0,45]]),  # Barcode EAN-13
    ]
    evidence_map = {"0": "ev_bb", "1": "ev_barcode"}
    candidates = extract_candidates(lines, evidence_map=evidence_map)
    
    cand = next((c for c in candidates if c.field == "MONTH_YEAR"), None)
    assert cand is not None
    assert cand.status == "DETECTED"
    assert cand.normalized_value is not None
    assert cand.normalized_value.duration == 9
    assert cand.normalized_value.duration_unit == "MONTH"
    assert "8 901234 567890" not in cand.raw_value
    assert "ev_barcode" not in cand.evidence_ids

def test_6_legitimate_date_numbers_remain_intact():
    """
    Test 6: Legitimate date numbers (e.g. 05/2026, 12 Months) parse accurately.
    """
    d1 = parse_date_declaration("MFG DATE: 05/2026")
    assert d1 is not None and d1.month == 5 and d1.year == 2026
    
    d2 = parse_date_declaration("Best Before 12 Months from packing")
    assert d2 is not None and d2.duration == 12 and d2.duration_unit == "MONTH"
    
    d3 = parse_date_declaration("USE BY: 15/08/2026")
    assert d3 is not None and d3.day == 15 and d3.month == 8 and d3.year == 2026

def test_7_evidence_ids_and_polygons_remain_traceable():
    """
    Test 7: Multi-line lookahead retains complete list of associated evidence IDs.
    """
    lines = [
        OcrLine(text="CONSUMER CARE CELL", confidence=0.93, polygon=[[0,0],[100,0],[100,20],[0,20]]),
        OcrLine(text="TEL: +91-11-23456789", confidence=0.91, polygon=[[0,25],[100,25],[100,45],[0,45]]),
        OcrLine(text="EMAIL: SUPPORT@GENERIC-EXAMPLE.COM", confidence=0.95, polygon=[[0,50],[100,50],[100,70],[0,70]]),
    ]
    evidence_map = {"0": "ev_0", "1": "ev_1", "2": "ev_2"}
    candidates = extract_candidates(lines, evidence_map=evidence_map)
    
    cand = next((c for c in candidates if c.field == "CONSUMER_CARE"), None)
    assert cand is not None
    assert "ev_0" in cand.evidence_ids
    assert "ev_1" in cand.evidence_ids
    assert "ev_2" in cand.evidence_ids

def test_8_no_expected_value_correction():
    """
    Test 8: System parses exactly what OCR contains and never fabricates or hallucinates numbers.
    """
    cand_empty = parse_mrp("MRP (INCLUSIVE OF ALL TAXES)")
    assert cand_empty is None
    
    cc_empty = parse_consumer_care("FOR QUERIES PLEASE WRITE TO US AT OUR OFFICE")
    assert cc_empty is None
