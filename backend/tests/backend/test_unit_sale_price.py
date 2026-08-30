from datetime import date
from decimal import Decimal
from app.schemas.ocr import OcrLine, FieldCandidate
from app.services.candidate_extractor import extract_candidates
from app.services.compliance_service import orchestrate_compliance

def helper_run_evals(lines, ref_date=date(2024, 1, 1), package="SINGLE", alcohol="NON_ALCOHOLIC", sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"):
    cands = extract_candidates(lines, {})
    evals = orchestrate_compliance(
        candidates=cands,
        reference_date=ref_date,
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin="UNKNOWN",
        regulatory_category="UNKNOWN",
        is_electronic="NON_ELECTRONIC",
        package_structure=package,
        alcohol_context=alcohol,
        evidence_sufficiency=sufficiency,
        inspection_complete=True
    )
    presence = next((r for r in evals if r.rule_id == "UNIT_SALE_PRICE_DECLARATION_PRESENCE"), None)
    consistency = next((r for r in evals if r.rule_id == "UNIT_SALE_PRICE_DENOMINATOR_CONSISTENCY"), None)
    return presence, consistency

# A. WEIGHT
def test_weight_boundaries():
    # 1. 500 g + USP ₹.../g => denominator compatible
    p, c = helper_run_evals([OcrLine(text="NET QUANTITY 500 g", confidence=1, polygon=[]), OcrLine(text="USP Rs 1/g", confidence=1, polygon=[]), OcrLine(text="MRP Rs 500", confidence=1, polygon=[])])
    assert c.status.value == "PASS"

    # 2. 500 g + USP ₹.../kg => incompatible
    p, c = helper_run_evals([OcrLine(text="NET QTY 500g", confidence=1, polygon=[]), OcrLine(text="USP Rs 1000/kg", confidence=1, polygon=[]), OcrLine(text="MRP Rs 500", confidence=1, polygon=[])])
    assert c.status.value == "FAIL"

    # 3. 2 kg + USP ₹.../kg => compatible
    p, c = helper_run_evals([OcrLine(text="NET QTY 2kg", confidence=1, polygon=[]), OcrLine(text="USP Rs 100/kg", confidence=1, polygon=[]), OcrLine(text="MRP Rs 200", confidence=1, polygon=[])])
    assert c.status.value == "PASS"

    # 4. 2 kg + USP ₹.../g => incompatible
    p, c = helper_run_evals([OcrLine(text="NET QTY 2kg", confidence=1, polygon=[]), OcrLine(text="USP Rs 0.1/g", confidence=1, polygon=[]), OcrLine(text="MRP Rs 200", confidence=1, polygon=[])])
    assert c.status.value == "FAIL"

# B. VOLUME
def test_volume_boundaries():
    # 5. 500 ml + USP ₹.../ml => compatible
    p, c = helper_run_evals([OcrLine(text="NET QTY 500ml", confidence=1, polygon=[]), OcrLine(text="USP Rs 1/ml", confidence=1, polygon=[]), OcrLine(text="MRP Rs 500", confidence=1, polygon=[])])
    assert c.status.value == "PASS"

    # 6. 500 ml + USP ₹.../L => incompatible
    p, c = helper_run_evals([OcrLine(text="NET QTY 500ml", confidence=1, polygon=[]), OcrLine(text="USP Rs 1000/L", confidence=1, polygon=[]), OcrLine(text="MRP Rs 500", confidence=1, polygon=[])])
    assert c.status.value == "FAIL"

    # 7. 2 L + USP ₹.../L => compatible
    p, c = helper_run_evals([OcrLine(text="NET QTY 2L", confidence=1, polygon=[]), OcrLine(text="USP Rs 100/L", confidence=1, polygon=[]), OcrLine(text="MRP Rs 200", confidence=1, polygon=[])])
    assert c.status.value == "PASS"

    # 8. 2 L + USP ₹.../ml => incompatible
    p, c = helper_run_evals([OcrLine(text="NET QTY 2L", confidence=1, polygon=[]), OcrLine(text="USP Rs 0.1/ml", confidence=1, polygon=[]), OcrLine(text="MRP Rs 200", confidence=1, polygon=[])])
    assert c.status.value == "FAIL"

# C. LENGTH
def test_length_boundaries():
    # 9. 50 cm + USP ₹.../cm => compatible
    p, c = helper_run_evals([OcrLine(text="NET QTY 50cm", confidence=1, polygon=[]), OcrLine(text="USP Rs 1/cm", confidence=1, polygon=[]), OcrLine(text="MRP Rs 50", confidence=1, polygon=[])])
    assert c.status.value == "PASS"

    # 10. 50 cm + USP ₹.../m => incompatible
    p, c = helper_run_evals([OcrLine(text="NET QTY 50cm", confidence=1, polygon=[]), OcrLine(text="USP Rs 100/m", confidence=1, polygon=[]), OcrLine(text="MRP Rs 50", confidence=1, polygon=[])])
    assert c.status.value == "FAIL"

    # 11. 2 m + USP ₹.../m => compatible
    p, c = helper_run_evals([OcrLine(text="NET QTY 2m", confidence=1, polygon=[]), OcrLine(text="USP Rs 100/m", confidence=1, polygon=[]), OcrLine(text="MRP Rs 200", confidence=1, polygon=[])])
    assert c.status.value == "PASS"

    # 12. 2 m + USP ₹.../cm => incompatible
    p, c = helper_run_evals([OcrLine(text="NET QTY 2m", confidence=1, polygon=[]), OcrLine(text="USP Rs 1/cm", confidence=1, polygon=[]), OcrLine(text="MRP Rs 200", confidence=1, polygon=[])])
    assert c.status.value == "FAIL"

# D. NUMBER / UNIT
def test_number_unit_boundaries():
    # 13. sold-by-number quantity + per-number USP => compatible
    p, c = helper_run_evals([OcrLine(text="NET QTY 10 u", confidence=1, polygon=[]), OcrLine(text="USP Rs 10/u", confidence=1, polygon=[]), OcrLine(text="MRP Rs 100", confidence=1, polygon=[])])
    assert c.status.value == "PASS"

# E. EXACT BOUNDARIES
def test_exact_boundaries():
    # 14. exactly 1 kg => ambiguous denominator, REVIEW_REQUIRED
    p, c = helper_run_evals([OcrLine(text="NET QTY 1 kg", confidence=1, polygon=[]), OcrLine(text="USP Rs 100/kg", confidence=1, polygon=[]), OcrLine(text="MRP Rs 100", confidence=1, polygon=[])])
    # For exactly 1kg, denominator consistency is REVIEW_REQUIRED
    # But wait, exactly 1kg also triggers RSP == USP exemption! 
    # Because qty is 1, so RSP (100) == USP (100 / 1 == 100).
    # If it is exempt, PRESENCE is NOT_APPLICABLE.
    # Therefore, consistency rule shouldn't even evaluate or might also be NOT_APPLICABLE if we short-circuit.
    # Wait, in compliance_service.py: we only evaluate consistency if it's APPLICABLE.
    # If applicability of USP PRESENCE is NOT_APPLICABLE, consistency is NOT_APPLICABLE.
    assert p.status.value == "REVIEW_REQUIRED" # Wait, exactly 1kg -> denom_qty is None!
    # Let's check my applicability logic:
    # denom_qty = get_legal_denominator_quantity(qty_val, qty_unit)
    # if denom_qty is None -> REVIEW_REQUIRED!
    # So PRESENCE applicability is REVIEW_REQUIRED, which means consistency is also REVIEW_REQUIRED.
    assert p.status.value == "REVIEW_REQUIRED"
    assert c.status.value == "REVIEW_REQUIRED"

    # 15. exactly 1 L => ambiguous
    p, c = helper_run_evals([OcrLine(text="NET QTY 1 L", confidence=1, polygon=[]), OcrLine(text="USP Rs 100/L", confidence=1, polygon=[]), OcrLine(text="MRP Rs 100", confidence=1, polygon=[])])
    assert p.status.value == "REVIEW_REQUIRED"

    # 16. exactly 1 m => ambiguous
    p, c = helper_run_evals([OcrLine(text="NET QTY 1 m", confidence=1, polygon=[]), OcrLine(text="USP Rs 100/m", confidence=1, polygon=[]), OcrLine(text="MRP Rs 100", confidence=1, polygon=[])])
    assert p.status.value == "REVIEW_REQUIRED"

# F. EVIDENCE SAFETY
def test_evidence_safety():
    # 17. missing Net Quantity => denominator evaluation REVIEW_REQUIRED
    p, c = helper_run_evals([OcrLine(text="USP Rs 100/kg", confidence=1, polygon=[]), OcrLine(text="MRP Rs 100", confidence=1, polygon=[])])
    assert p.status.value == "REVIEW_REQUIRED"
    assert c.status.value == "REVIEW_REQUIRED"

    # 18. conflicting Net Quantity => REVIEW_REQUIRED
    p, c = helper_run_evals([OcrLine(text="NET QTY 2 kg", confidence=1, polygon=[]), OcrLine(text="NET QTY 500 g", confidence=1, polygon=[]), OcrLine(text="USP Rs 100/kg", confidence=1, polygon=[]), OcrLine(text="MRP Rs 200", confidence=1, polygon=[])])
    assert p.status.value == "REVIEW_REQUIRED"

    # 19. malformed USP unit => REVIEW_REQUIRED
    # If USP is malformed, it won't be parsed as USP or it will be missing the per_unit.
    # Currently parse_unit_sale_price requires a per_unit to match. If it doesn't match, USP is missing.
    # If USP is missing, PRESENCE is FAIL, CONSISTENCY is FAIL or REVIEW_REQUIRED.
    p, c = helper_run_evals([OcrLine(text="NET QTY 2 kg", confidence=1, polygon=[]), OcrLine(text="USP Rs 100", confidence=1, polygon=[]), OcrLine(text="MRP Rs 200", confidence=1, polygon=[])])
    assert p.status.value == "REVIEW_REQUIRED"
    
    # 20. USP does not alter Net Quantity
    lines = [OcrLine(text="NET QTY 2 kg", confidence=1, polygon=[]), OcrLine(text="USP Rs 100/g", confidence=1, polygon=[])]
    cands = extract_candidates(lines, {})
    net_cand = next(x for x in cands if x.field == "NET_QUANTITY")
    assert net_cand.normalized_value.unit == "kg"

# G. RSP == USP EXEMPTION
def test_rsp_usp_exemption():
    # 21. deterministically established equality => USP declaration requirement NOT_APPLICABLE
    # If net qty is 1 unit, USP = MRP/1 = MRP. Wait, 1 unit means denom_qty = 1.
    p, c = helper_run_evals([OcrLine(text="NET QTY 1 u", confidence=1, polygon=[]), OcrLine(text="MRP Rs 50", confidence=1, polygon=[])])
    assert p.status.value == "NOT_APPLICABLE"

    # 22. equality cannot be established => REVIEW_REQUIRED
    p, c = helper_run_evals([OcrLine(text="NET QTY 500 g", confidence=1, polygon=[])]) # Missing MRP
    assert p.status.value == "REVIEW_REQUIRED"

    # 23. non-equal case => ordinary USP requirement applies (so if USP is missing, FAIL)
    p, c = helper_run_evals([OcrLine(text="NET QTY 500 g", confidence=1, polygon=[]), OcrLine(text="MRP Rs 50", confidence=1, polygon=[])])
    assert p.status.value == "FAIL"

# H. EXISTING APPLICABILITY
def test_existing_applicability():
    # 24. COMBINATION remains NOT_APPLICABLE
    p, c = helper_run_evals([], package="COMBINATION")
    assert p.status.value == "NOT_APPLICABLE"

    # 25. GROUP remains NOT_APPLICABLE
    p, c = helper_run_evals([], package="GROUP")
    assert p.status.value == "NOT_APPLICABLE"

    # 26. MULTI_PIECE remains NOT_APPLICABLE
    p, c = helper_run_evals([], package="MULTI_PIECE")
    assert p.status.value == "NOT_APPLICABLE"

    # 27. UNKNOWN package structure remains REVIEW_REQUIRED
    p, c = helper_run_evals([], package="UNKNOWN")
    assert p.status.value == "REVIEW_REQUIRED"

    # 28. ALCOHOLIC has precise State Excise deferral reason
    p, c = helper_run_evals([], alcohol="ALCOHOLIC")
    assert p.status.value == "NOT_APPLICABLE"
    assert "State Excise" in p.reason

# I. VERSIONING
def test_versioning():
    # 29. 2023-12-31 => production rule inactive
    p, c = helper_run_evals([], ref_date=date(2023, 12, 31))
    assert p is None
    assert c is None

    # 30. 2024-01-01 => active
    p, c = helper_run_evals([], ref_date=date(2024, 1, 1))
    assert p is not None
    assert c is not None

# J. REGRESSIONS
def test_regressions():
    lines = [
        OcrLine(text="MRP RS 100", confidence=0.9, polygon=[]),
        OcrLine(text="NET QTY 100G", confidence=0.9, polygon=[]),
        OcrLine(text="CONSUMER CARE: 1800123456", confidence=0.9, polygon=[]),
        OcrLine(text="MANUFACTURED BY XYZ", confidence=0.9, polygon=[]),
        OcrLine(text="MADE IN INDIA", confidence=0.9, polygon=[]),
        OcrLine(text="COMMON NAME: WHEAT", confidence=0.9, polygon=[])
    ]
    cands = extract_candidates(lines, {})
    
    # 31. MRP unchanged
    assert next((cand for cand in cands if cand.field == "MRP")).status == "DETECTED"
    # 32. NET_QUANTITY unchanged
    assert next((cand for cand in cands if cand.field == "NET_QUANTITY")).status == "DETECTED"
    # 33. Consumer Care unchanged
    assert next((cand for cand in cands if cand.field == "CONSUMER_CARE")).status == "DETECTED"
    # 34. Business rules unchanged
    assert next((cand for cand in cands if cand.field == "MANUFACTURER_PACKER_IMPORTER")).status == "DETECTED"
    # 35. Country of Origin unchanged
    assert next((cand for cand in cands if cand.field == "COUNTRY_OF_ORIGIN")).status == "DETECTED"
    # 36. Common/Generic Name unchanged
    assert next((cand for cand in cands if cand.field == "COMMON_GENERIC_NAME")).status == "DETECTED"
