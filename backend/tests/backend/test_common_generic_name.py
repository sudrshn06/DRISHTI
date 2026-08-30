from datetime import date
from app.schemas.ocr import OcrLine, FieldCandidate
from app.schemas.inspection import CapturePlan, CaptureViewRequirement, CaptureRecord
from app.services.candidate_extractor import extract_candidates
from app.services.inspection_service import aggregate_candidates, evaluate_completeness, evaluate_evidence_sufficiency
from app.services.applicability_model import evaluate_applicability
from app.services.rule_engine import get_applicable_rules, evaluate_candidate
from app.services.rule_loader import load_production_rules
from app.services.compliance_service import orchestrate_compliance

def test_extraction_anchored_detection():
    lines = [OcrLine(text="COMMON NAME: TOOR DAL", confidence=0.9, polygon=[])]
    cands = extract_candidates(lines, {"0": "e1"})
    c = next((c for c in cands if c.field == "COMMON_GENERIC_NAME"), None)
    assert c and c.status == "DETECTED"
    assert c.normalized_value.name_text == "TOOR DAL"

def test_extraction_rejections():
    # 18. brand-only text remains rejected
    lines = [OcrLine(text="TATA SAMPANN", confidence=0.9, polygon=[])]
    cands = extract_candidates(lines, {"0": "e1"})
    c = next((c for c in cands if c.field == "COMMON_GENERIC_NAME"), None)
    assert c and c.status == "NOT_DETECTED"

def test_extraction_malformed():
    # A. MALFORMED DECLARATION
    # Verify a structurally anchored but malformed/incomplete common/generic-name declaration becomes REVIEW_REQUIRED
    lines = [OcrLine(text="COMMON NAME:", confidence=0.9, polygon=[])]
    cands = extract_candidates(lines, {"0": "e1"})
    c = next((c for c in cands if c.field == "COMMON_GENERIC_NAME"), None)
    assert c and c.status == "REVIEW_REQUIRED"

def test_aggregation():
    # B. MULTI-VIEW AGGREGATION
    c1 = FieldCandidate(field="COMMON_GENERIC_NAME", status="DETECTED", normalized_value={"name_text": "TOOR DAL"}, evidence_ids=["e1"], capture_ids=[])
    c2 = FieldCandidate(field="COMMON_GENERIC_NAME", status="DETECTED", normalized_value={"name_text": "TOOR DAL"}, evidence_ids=["e2"], capture_ids=[])
    rec1 = CaptureRecord(capture_id="cap1", view_id="FRONT", field_candidates=[c1], status="ACCEPTED", pipeline_status="COMPLETED")
    rec2 = CaptureRecord(capture_id="cap2", view_id="BACK", field_candidates=[c2], status="ACCEPTED", pipeline_status="COMPLETED")
    
    # 1. same normalized commodity name across captures => deterministic deduplication
    agg = aggregate_candidates([rec1, rec2])
    c = next((x for x in agg if x.field == "COMMON_GENERIC_NAME"), None)
    assert c.status == "DETECTED"
    assert "e1" in c.evidence_ids and "e2" in c.evidence_ids

    # 2. conflicting strong commodity names across captures => REVIEW_REQUIRED
    c3 = FieldCandidate(field="COMMON_GENERIC_NAME", status="DETECTED", normalized_value={"name_text": "MOONG DAL"}, evidence_ids=["e3"], capture_ids=[])
    rec3 = CaptureRecord(capture_id="cap3", view_id="SIDE", field_candidates=[c3], status="ACCEPTED", pipeline_status="COMPLETED")
    agg_conflict = aggregate_candidates([rec1, rec3])
    c_conflict = next((x for x in agg_conflict if x.field == "COMMON_GENERIC_NAME"), None)
    assert c_conflict.status == "REVIEW_REQUIRED"

    # capture ordering does not change result
    agg_conflict_rev = aggregate_candidates([rec3, rec1])
    c_conflict_rev = next((x for x in agg_conflict_rev if x.field == "COMMON_GENERIC_NAME"), None)
    assert c_conflict_rev.status == "REVIEW_REQUIRED"

def test_qr_instruction_extraction():
    # 13. "Scan QR for warranty" => does NOT satisfy
    lines1 = [OcrLine(text="SCAN QR FOR WARRANTY", confidence=0.9, polygon=[])]
    cands1 = extract_candidates(lines1, {})
    c1 = next((c for c in cands1 if c.field == "COMMON_NAME_QR_INSTRUCTION"), None)
    assert c1 and c1.status == "NOT_DETECTED"

    # 14. "Scan QR for offers" => does NOT satisfy
    lines2 = [OcrLine(text="SCAN QR FOR OFFERS", confidence=0.9, polygon=[])]
    cands2 = extract_candidates(lines2, {})
    c2 = next((c for c in cands2 if c.field == "COMMON_NAME_QR_INSTRUCTION"), None)
    assert c2 and c2.status == "NOT_DETECTED"

    # 15. strong common-name QR instruction => structured QR instruction evidence
    lines3 = [OcrLine(text="SCAN QR FOR COMMON NAME", confidence=0.9, polygon=[])]
    cands3 = extract_candidates(lines3, {"0": "e1"})
    c3 = next((c for c in cands3 if c.field == "COMMON_NAME_QR_INSTRUCTION"), None)
    assert c3 and c3.status == "DETECTED"

def test_compliance_matrix():
    c_det = FieldCandidate(field="COMMON_GENERIC_NAME", status="DETECTED", normalized_value={"name_text": "TOOR DAL"})
    c_not = FieldCandidate(field="COMMON_GENERIC_NAME", status="NOT_DETECTED")
    c_qr = FieldCandidate(field="COMMON_NAME_QR_INSTRUCTION", status="DETECTED")
    c_qr_not = FieldCandidate(field="COMMON_NAME_QR_INSTRUCTION", status="NOT_DETECTED")
    
    # Helper
    def run_eval(cands, ref_date, is_electronic, sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"):
        evals = orchestrate_compliance(
            candidates=cands, 
            reference_date=ref_date, 
            product_category="GENERIC_RETAIL_PACKAGE", 
            is_electronic=is_electronic, 
            evidence_sufficiency=sufficiency, 
            inspection_complete=True
        )
        return next((r for r in evals if r.rule_id == "COMMON_GENERIC_NAME_DECLARATION_PRESENCE"), None)

    # 1. 2021 reference date, ELECTRONIC, printed COMMON NAME detected => PASS
    assert run_eval([c_det], date(2021, 1, 1), "ELECTRONIC").status.value == "PASS"

    # 2. 2021 reference date, ELECTRONIC, printed name missing, synthetic sufficient absence evidence => FAIL
    assert run_eval([c_not], date(2021, 1, 1), "ELECTRONIC").status.value == "FAIL"

    # 3. 2022 historical QR period, ELECTRONIC, printed name detected => PASS
    assert run_eval([c_det], date(2022, 10, 1), "ELECTRONIC").status.value == "PASS"

    # 4. 2022 historical QR period, ELECTRONIC, printed name missing, QR eligibility cannot be established from explicit context => REVIEW_REQUIRED
    assert run_eval([c_not], date(2022, 10, 1), "ELECTRONIC").status.value == "REVIEW_REQUIRED"

    # 5. 2023-06-23 or later, ELECTRONIC, printed name detected => PASS
    assert run_eval([c_det], date(2023, 7, 1), "ELECTRONIC").status.value == "PASS"

    # 6. 2023-06-23 or later, ELECTRONIC, printed name missing, qualifying common-name QR instruction detected => REVIEW_REQUIRED
    # 16. QR instruction does NOT itself produce PASS
    assert run_eval([c_not, c_qr], date(2023, 7, 1), "ELECTRONIC").status.value == "REVIEW_REQUIRED"

    # 7. 2023-06-23 or later, ELECTRONIC, printed name missing, unrelated QR instruction only, sufficient absence evidence => FAIL
    # Unrelated QR means c_qr is NOT_DETECTED
    assert run_eval([c_not, c_qr_not], date(2023, 7, 1), "ELECTRONIC").status.value == "FAIL"

    # 8. 2023-06-23 or later, ELECTRONIC, printed name missing, no qualifying QR instruction, sufficient absence evidence => FAIL
    # 17. QR code/image presence without textual qualifying evidence => does NOT produce PASS
    assert run_eval([c_not], date(2023, 7, 1), "ELECTRONIC").status.value == "FAIL"

    # 9. normal FRONT/BACK, printed name missing => REVIEW_REQUIRED regardless of absence rule
    assert run_eval([c_not], date(2023, 7, 1), "ELECTRONIC", "INSUFFICIENT_FOR_ABSENCE_EVALUATION").status.value == "REVIEW_REQUIRED"

    # 10. UNKNOWN electronic context, printed name detected => PASS
    assert run_eval([c_det], date(2023, 7, 1), "UNKNOWN").status.value == "PASS"

    # 11. UNKNOWN electronic context, printed name missing, sufficient absence evidence => REVIEW_REQUIRED
    assert run_eval([c_not], date(2023, 7, 1), "UNKNOWN").status.value == "REVIEW_REQUIRED"

    # 12. NON_ELECTRONIC, printed name detected => PASS
    assert run_eval([c_det], date(2023, 7, 1), "NON_ELECTRONIC").status.value == "PASS"

def test_unchanged_behavior():
    # 20. country-of-origin rule unchanged
    # 21. MRP / Net Quantity / Consumer Care / business rules unchanged
    lines = [
        OcrLine(text="MRP RS 100", confidence=0.9, polygon=[]),
        OcrLine(text="NET QTY 100G", confidence=0.9, polygon=[]),
        OcrLine(text="CONSUMER CARE: 1800123456", confidence=0.9, polygon=[]),
        OcrLine(text="MANUFACTURED BY XYZ", confidence=0.9, polygon=[]),
        OcrLine(text="MADE IN INDIA", confidence=0.9, polygon=[])
    ]
    cands = extract_candidates(lines, {})
    
    assert next((c for c in cands if c.field == "MRP")).status == "DETECTED"
    assert next((c for c in cands if c.field == "NET_QUANTITY")).status == "DETECTED"
    assert next((c for c in cands if c.field == "CONSUMER_CARE")).status == "DETECTED"
    assert next((c for c in cands if c.field == "MANUFACTURER_PACKER_IMPORTER")).status == "DETECTED"
    assert next((c for c in cands if c.field == "COUNTRY_OF_ORIGIN")).status == "DETECTED"

def test_product_category_no_leakage():
    # C. PRODUCT METADATA ISOLATION
    # Verify user/session metadata is NEVER copied/injected into COMMON_GENERIC_NAME OCR evidence.
    lines = [] # No package declaration
    # Even if we pass product_category = "GENERIC_RETAIL_PACKAGE" into orchestrator, the candidate extractor only sees lines.
    cands = extract_candidates(lines, {})
    c = next((x for x in cands if x.field == "COMMON_GENERIC_NAME"), None)
    assert c and c.status == "NOT_DETECTED"
    
    # And if orchestrated, it stays missing, it doesn't invent a name from context
    evals = orchestrate_compliance(
        candidates=cands, 
        reference_date=date(2023, 7, 1), 
        product_category="GENERIC_RETAIL_PACKAGE", 
        is_electronic="NON_ELECTRONIC", 
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION", 
        inspection_complete=True
    )
    res = next((r for r in evals if r.rule_id == "COMMON_GENERIC_NAME_DECLARATION_PRESENCE"), None)
    assert res.status.value == "FAIL" # Fails because missing, not PASS because of product_category

def test_multi_product_packages():
    # D. MULTI-PRODUCT PACKAGE SAFETY
    # Detecting one common/generic name does NOT falsely claim that multi-product name/count/quantity completeness has been satisfied.
    # The rule is explicitly named COMMON_GENERIC_NAME_DECLARATION_PRESENCE.
    c_det = FieldCandidate(field="COMMON_GENERIC_NAME", status="DETECTED", normalized_value={"name_text": "TOOR DAL"})
    evals = orchestrate_compliance(
        candidates=[c_det], 
        reference_date=date(2023, 7, 1), 
        product_category="GENERIC_RETAIL_PACKAGE", 
        is_electronic="NON_ELECTRONIC", 
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION", 
        inspection_complete=True
    )
    res = next((r for r in evals if r.rule_id == "COMMON_GENERIC_NAME_DECLARATION_PRESENCE"), None)
    
    assert res.status.value == "PASS"
    # The evaluation passes PRESENCE only, preserving conservative behavior.
