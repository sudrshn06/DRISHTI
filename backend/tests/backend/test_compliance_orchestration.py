import pytest
from datetime import date
from app.schemas.ocr import FieldCandidate
from app.schemas.compliance import LegalStatus
from app.services.compliance_service import orchestrate_compliance
from app.services.rule_loader import load_production_rules

def test_mrp_detected():
    # 1. MRP detected -> production MRP presence result PASS
    candidates = [
        FieldCandidate(field="MRP", status="DETECTED", raw_value="Rs 100")
    ]
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE")
    
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == LegalStatus.PASS

def test_net_quantity_detected():
    # 2. NET_QUANTITY detected -> production net-quantity presence result PASS
    candidates = [
        FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value="500ml")
    ]
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE")
    
    net_qty_result = next(r for r in results if r.rule_id == "NET_QUANTITY_PRESENCE")
    assert net_qty_result.status == LegalStatus.PASS

def test_both_detected():
    # 3. both detected -> two independent PASS results
    candidates = [
        FieldCandidate(field="MRP", status="DETECTED", raw_value="Rs 100"),
        FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value="500ml")
    ]
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE")
    
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    net_qty_result = next(r for r in results if r.rule_id == "NET_QUANTITY_PRESENCE")
    
    assert mrp_result.status == LegalStatus.PASS
    assert net_qty_result.status == LegalStatus.PASS

def test_mrp_not_detected_incomplete():
    # 4. MRP NOT_DETECTED during incomplete inspection -> REVIEW_REQUIRED
    candidates = [
        FieldCandidate(field="MRP", status="NOT_DETECTED")
    ]
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE")
    
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == LegalStatus.REVIEW_REQUIRED

def test_candidate_review_required():
    # 5. candidate REVIEW_REQUIRED -> legal REVIEW_REQUIRED
    candidates = [
        FieldCandidate(field="MRP", status="REVIEW_REQUIRED")
    ]
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE")
    
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == LegalStatus.REVIEW_REQUIRED

def test_missing_field_candidate():
    # 6. missing FieldCandidate object -> REVIEW_REQUIRED, never FAIL
    candidates = [
        FieldCandidate(field="SOME_OTHER_FIELD", status="DETECTED")
    ]
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE")
    
    # We should still get a result for MRP and NET_QUANTITY because the rule is applicable
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == LegalStatus.REVIEW_REQUIRED
    assert "Insufficient evidence" in mrp_result.reason

def test_wrong_product_category():
    # 7. wrong product_category -> NOT_APPLICABLE
    candidates = [
        FieldCandidate(field="MRP", status="DETECTED", raw_value="Rs 100")
    ]
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "WRONG_CATEGORY")
    
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == LegalStatus.NOT_APPLICABLE

def test_explicit_reference_date_controls_selection():
    # 8. explicit reference_date controls applicable rule selection
    candidates = [
        FieldCandidate(field="MRP", status="DETECTED", raw_value="Rs 100"),
        FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value="500ml")
    ]
    # 2021 date: MRP rule (2022) is not active, NET_QUANTITY (2011) is active
    results = orchestrate_compliance(candidates, date(2021, 1, 1), "GENERIC_RETAIL_PACKAGE")
    
    assert not any(r.rule_id == "MRP_DECLARATION_PRESENCE" for r in results)
    assert any(r.rule_id == "NET_QUANTITY_PRESENCE" for r in results)

def test_multiple_conflicting_candidates():
    # 9. multiple conflicting candidates for same field -> REVIEW_REQUIRED
    candidates = [
        FieldCandidate(field="MRP", status="DETECTED", raw_value="Rs 100", confidence=0.9),
        FieldCandidate(field="MRP", status="DETECTED", raw_value="Rs 200", confidence=0.99)
    ]
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE")
    
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == LegalStatus.REVIEW_REQUIRED
    assert "Conflicting declaration evidence" in mrp_result.reason

def test_repeated_identical_input():
    # 10. repeated identical input -> identical ordered evaluations
    candidates = [
        FieldCandidate(field="MRP", status="DETECTED", raw_value="Rs 100")
    ]
    res1 = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE")
    res2 = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE")
    
    assert [r.model_dump() for r in res1] == [r.model_dump() for r in res2]

def test_source_survives_orchestration():
    # 11. source_reference/source_url survive orchestration
    candidates = [
        FieldCandidate(field="MRP", status="DETECTED", raw_value="Rs 100")
    ]
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE")
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    
    assert mrp_result.source_reference is not None
    assert mrp_result.source_url is not None

def test_not_detected_sufficient_fail():
    # 12. NOT_DETECTED + SUFFICIENT_FOR_ABSENCE_EVALUATION -> FAIL
    candidates = [
        FieldCandidate(field="MRP", status="NOT_DETECTED")
    ]
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE", evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION")
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == LegalStatus.FAIL
    assert "Required declaration was not detected" in mrp_result.reason

def test_not_detected_insufficient_review():
    # 13. NOT_DETECTED + INSUFFICIENT_FOR_ABSENCE_EVALUATION -> REVIEW_REQUIRED
    candidates = [
        FieldCandidate(field="MRP", status="NOT_DETECTED")
    ]
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE", evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION")
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == LegalStatus.REVIEW_REQUIRED
    assert "Inspection plan is not sufficient for absence" in mrp_result.reason

def test_missing_field_candidate_sufficient_fail():
    # 14. missing candidate + SUFFICIENT_FOR_ABSENCE_EVALUATION -> FAIL
    candidates = []
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE", evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION")
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == LegalStatus.FAIL
    assert "Required declaration was not detected" in mrp_result.reason

def test_missing_field_candidate_insufficient_review():
    # 15. missing candidate + INSUFFICIENT_FOR_ABSENCE_EVALUATION -> REVIEW_REQUIRED
    candidates = []
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE", evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION")
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == LegalStatus.REVIEW_REQUIRED
    assert "Insufficient evidence" in mrp_result.reason

def test_capture_ids_preserved():
    # 16. capture_ids provenance is preserved in evaluation result
    candidates = [
        FieldCandidate(field="MRP", status="DETECTED", raw_value="Rs 100", evidence_ids=["ev_1"], capture_ids=["cap_1"])
    ]
    results = orchestrate_compliance(candidates, date(2026, 8, 24), "GENERIC_RETAIL_PACKAGE", evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION")
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == LegalStatus.PASS
    assert mrp_result.evidence_ids == ["ev_1"]
    assert mrp_result.capture_ids == ["cap_1"]

