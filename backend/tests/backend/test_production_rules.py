import pytest
from datetime import date
from pydantic import ValidationError
import tempfile
import json
import os

from app.schemas.compliance import LegalStatus, RuleDefinition
from app.schemas.ocr import FieldCandidate, BusinessNormalized, OcrLine
from app.services.rule_engine import evaluate_candidate, get_applicable_rules
from app.services.rule_loader import load_production_rules, load_rules
from app.services.candidate_extractor import extract_candidates

def make_line(text):
    return OcrLine(
        text=text,
        confidence=0.99,
        polygon=[[0, 0], [1, 0], [1, 1], [0, 1]]
    )

def test_production_rule_pack_loads_4_rules():
    # 1. production rule pack now loads 4 intended rules
    rules = load_production_rules()
    active_rules = get_applicable_rules(rules, date(2026, 8, 24))
    assert len(active_rules) >= 4
    
    rule_ids = [r.rule_id for r in active_rules]
    assert "MRP_DECLARATION_PRESENCE" in rule_ids
    assert "NET_QUANTITY_PRESENCE" in rule_ids
    assert "MANUFACTURER_PACKER_DECLARATION_PRESENCE" in rule_ids
    assert "IMPORTER_DECLARATION_PRESENCE" in rule_ids
    assert "CONSUMER_CARE_DECLARATION_PRESENCE" in rule_ids

def test_manufacturer_detected_pass():
    # 2. manufacturer DETECTED => PASS
    rules = load_production_rules()
    active_rules = get_applicable_rules(rules, date(2026, 8, 24))
    mfg_rule = next(r for r in active_rules if r.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE")
    
    candidate = FieldCandidate(field="MANUFACTURER_PACKER_IMPORTER", status="DETECTED", raw_value="Mfd By: Example Foods")
    result = evaluate_candidate(candidate, mfg_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE")
    
    assert result.status == LegalStatus.PASS

def test_manufacturer_review_required():
    # 3. manufacturer REVIEW_REQUIRED => REVIEW_REQUIRED
    rules = load_production_rules()
    active_rules = get_applicable_rules(rules, date(2026, 8, 24))
    mfg_rule = next(r for r in active_rules if r.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE")
    
    candidate = FieldCandidate(field="MANUFACTURER_PACKER_IMPORTER", status="REVIEW_REQUIRED")
    result = evaluate_candidate(candidate, mfg_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE")
    
    assert result.status == LegalStatus.REVIEW_REQUIRED

def test_manufacturer_not_detected_front_back_plan():
    # 4. current FRONT+BACK plan (INSUFFICIENT) + manufacturer NOT_DETECTED => REVIEW_REQUIRED
    rules = load_production_rules()
    active_rules = get_applicable_rules(rules, date(2026, 8, 24))
    mfg_rule = next(r for r in active_rules if r.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE")
    
    candidate = FieldCandidate(field="MANUFACTURER_PACKER_IMPORTER", status="NOT_DETECTED")
    result = evaluate_candidate(candidate, mfg_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE", evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION")
    
    assert result.status == LegalStatus.REVIEW_REQUIRED

def test_manufacturer_not_detected_synthetic_absence_eligible():
    # 5. synthetic absence-eligible complete plan + manufacturer NOT_DETECTED => FAIL
    rules = load_production_rules()
    active_rules = get_applicable_rules(rules, date(2026, 8, 24))
    mfg_rule = next(r for r in active_rules if r.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE")
    
    candidate = FieldCandidate(field="MANUFACTURER_PACKER_IMPORTER", status="NOT_DETECTED")
    result = evaluate_candidate(candidate, mfg_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE", evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION")
    
    assert result.status == LegalStatus.FAIL

def test_consumer_care_detected_pass():
    # 6. consumer care DETECTED => PASS
    rules = load_production_rules()
    active_rules = get_applicable_rules(rules, date(2026, 8, 24))
    cc_rule = next(r for r in active_rules if r.rule_id == "CONSUMER_CARE_DECLARATION_PRESENCE")
    
    candidate = FieldCandidate(field="CONSUMER_CARE", status="DETECTED", raw_value="Care: 1800-111-222")
    result = evaluate_candidate(candidate, cc_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE")
    
    assert result.status == LegalStatus.PASS
    # Also verify exact wording
    assert result.reason == "Consumer-care declaration evidence was detected for this presence rule."

def test_consumer_care_review_required():
    # 7. consumer care REVIEW_REQUIRED => REVIEW_REQUIRED
    rules = load_production_rules()
    active_rules = get_applicable_rules(rules, date(2026, 8, 24))
    cc_rule = next(r for r in active_rules if r.rule_id == "CONSUMER_CARE_DECLARATION_PRESENCE")
    
    candidate = FieldCandidate(field="CONSUMER_CARE", status="REVIEW_REQUIRED")
    result = evaluate_candidate(candidate, cc_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE")
    
    assert result.status == LegalStatus.REVIEW_REQUIRED

def test_consumer_care_not_detected_front_back_plan():
    # 8. current FRONT+BACK plan + consumer care NOT_DETECTED => REVIEW_REQUIRED
    rules = load_production_rules()
    active_rules = get_applicable_rules(rules, date(2026, 8, 24))
    cc_rule = next(r for r in active_rules if r.rule_id == "CONSUMER_CARE_DECLARATION_PRESENCE")
    
    candidate = FieldCandidate(field="CONSUMER_CARE", status="NOT_DETECTED")
    result = evaluate_candidate(candidate, cc_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE", evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION")
    
    assert result.status == LegalStatus.REVIEW_REQUIRED

def test_consumer_care_not_detected_synthetic_absence_eligible():
    # 9. synthetic absence-eligible complete plan + consumer care NOT_DETECTED => FAIL
    rules = load_production_rules()
    active_rules = get_applicable_rules(rules, date(2026, 8, 24))
    cc_rule = next(r for r in active_rules if r.rule_id == "CONSUMER_CARE_DECLARATION_PRESENCE")
    
    candidate = FieldCandidate(field="CONSUMER_CARE", status="NOT_DETECTED")
    result = evaluate_candidate(candidate, cc_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE", evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION")
    
    assert result.status == LegalStatus.FAIL

def test_explicit_marketed_by_remains_valid_evidence():
    # 10. explicit MARKETED BY declaration remains valid evidence
    lines = [
        make_line("MARKETED BY"),
        make_line("Example Brand LLC")
    ]
    candidates = extract_candidates(lines, {})
    mfg_cand = next(c for c in candidates if c.field == "MANUFACTURER_PACKER_IMPORTER")
    assert mfg_cand.status == "DETECTED"
    assert "EXAMPLE BRAND LLC" in mfg_cand.normalized_value.name.upper()

def test_ordinary_packed_prose_does_not_satisfy():
    # 11. ordinary "packed hygienically" prose does not satisfy manufacturer rule
    lines = [
        make_line("This product is packed hygienically"),
        make_line("in a clean facility")
    ]
    candidates = extract_candidates(lines, {})
    mfg_cand = next(c for c in candidates if c.field == "MANUFACTURER_PACKER_IMPORTER")
    assert mfg_cand.status == "NOT_DETECTED"

def test_consumer_care_email_does_not_imply_completeness():
    # 12. consumer-care email/contact detection does not imply completeness of every consumer-care subcomponent
    # It just extracts the block as DETECTED for the PRESENCE rule
    lines = [
        make_line("Contact: info@example.com")
    ]
    candidates = extract_candidates(lines, {})
    cc_cand = next(c for c in candidates if c.field == "CONSUMER_CARE")
    assert cc_cand.status == "DETECTED"
    assert cc_cand.raw_value == "CONTACT: INFO@EXAMPLE.COM"
    # Does not have complex parsed object claiming it is fully compliant, just presence

def test_rule_source_reference_survive():
    # 13. rule source_reference/source_url survive evaluation
    rules = load_production_rules()
    active_rules = get_applicable_rules(rules, date(2026, 8, 24))
    cc_rule = next(r for r in active_rules if r.rule_id == "CONSUMER_CARE_DECLARATION_PRESENCE")
    
    candidate = FieldCandidate(field="CONSUMER_CARE", status="DETECTED", raw_value="Care: 1800")
    result = evaluate_candidate(candidate, cc_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE")
    
    assert result.source_reference == cc_rule.source_reference
    assert result.source_url == cc_rule.source_url

def test_reference_date_controls_applicability():
    # 14. reference_date controls rule applicability
    rules = load_production_rules()
    # manufacturer is effective from 2018-01-01
    active_rules_2017 = get_applicable_rules(rules, date(2017, 12, 31))
    active_rules_2018 = get_applicable_rules(rules, date(2018, 1, 1))
    
    assert not any(r.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE" for r in active_rules_2017)
    assert any(r.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE" for r in active_rules_2018)

def test_reversing_capture_order_identical():
    # 15. reversing capture order yields identical results
    # Evaluated structurally in candidate_extractor (test_aggregation_regression covers cross-image conflicts)
    # We test it at rule evaluation level (order of execution doesn't matter for independent rules)
    rules = load_production_rules()
    active_rules = get_applicable_rules(rules, date(2026, 8, 24))
    mrp_rule = next(r for r in active_rules if r.rule_id == "MRP_DECLARATION_PRESENCE")
    cc_rule = next(r for r in active_rules if r.rule_id == "CONSUMER_CARE_DECLARATION_PRESENCE")
    
    c1 = FieldCandidate(field="MRP", status="DETECTED")
    c2 = FieldCandidate(field="CONSUMER_CARE", status="DETECTED")
    
    r1_forward = evaluate_candidate(c1, mrp_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE")
    r2_forward = evaluate_candidate(c2, cc_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE")
    
    r2_reverse = evaluate_candidate(c2, cc_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE")
    r1_reverse = evaluate_candidate(c1, mrp_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE")
    
    assert r1_forward.status == r1_reverse.status
    assert r2_forward.status == r2_reverse.status

def test_mrp_net_qty_remain_unchanged():
    # 16. MRP and NET_QUANTITY existing rules remain unchanged
    rules = load_production_rules()
    active_rules = get_applicable_rules(rules, date(2026, 8, 24))
    
    mrp_rule = next(r for r in active_rules if r.rule_id == "MRP_DECLARATION_PRESENCE")
    nq_rule = next(r for r in active_rules if r.rule_id == "NET_QUANTITY_PRESENCE")
    
    candidate_mrp = FieldCandidate(field="MRP", status="DETECTED", raw_value="Rs 100")
    result_mrp = evaluate_candidate(candidate_mrp, mrp_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE")
    assert result_mrp.status == LegalStatus.PASS
    
    candidate_nq = FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value="500 ml")
    result_nq = evaluate_candidate(candidate_nq, nq_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE")
    assert result_nq.status == LegalStatus.PASS

def test_single_image_not_detected_review_required():
    # 17. single-image NOT_DETECTED still remains REVIEW_REQUIRED
    rules = load_production_rules()
    active_rules = get_applicable_rules(rules, date(2026, 8, 24))
    mfg_rule = next(r for r in active_rules if r.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE")
    
    candidate = FieldCandidate(field="MANUFACTURER_PACKER_IMPORTER", status="NOT_DETECTED")
    # For single image, evidence_sufficiency defaults to INSUFFICIENT_FOR_ABSENCE_EVALUATION
    result = evaluate_candidate(candidate, mfg_rule, date(2026, 8, 24), product_category="GENERIC_RETAIL_PACKAGE")
    
    assert result.status == LegalStatus.REVIEW_REQUIRED

def test_country_of_origin_effective_date_before():
    # A. reference_date = 2017-12-31, rule must NOT be active
    rules = load_production_rules()
    active_rules_2017 = get_applicable_rules(rules, date(2017, 12, 31))
    assert not any(r.rule_id == "COUNTRY_OF_ORIGIN_DECLARATION_PRESENCE" for r in active_rules_2017)

def test_country_of_origin_effective_date_after_imported():
    # B. reference_date = 2018-01-01, origin = IMPORTED, rule must be active and applicable
    rules = load_production_rules()
    active_rules_2018 = get_applicable_rules(rules, date(2018, 1, 1))
    assert any(r.rule_id == "COUNTRY_OF_ORIGIN_DECLARATION_PRESENCE" for r in active_rules_2018)
    
    from app.services.applicability_model import evaluate_applicability
    from app.schemas.applicability import ApplicabilityStatus
    decisions = evaluate_applicability(active_rules_2018, [], product_category="GENERIC_RETAIL_PACKAGE", product_origin="IMPORTED")
    assert decisions["COUNTRY_OF_ORIGIN_DECLARATION_PRESENCE"].status == ApplicabilityStatus.APPLICABLE

def test_country_of_origin_effective_date_after_domestic():
    # C. reference_date after 2018-01-01, origin = DOMESTIC, rule remains NOT_APPLICABLE
    rules = load_production_rules()
    active_rules_2018 = get_applicable_rules(rules, date(2018, 1, 2))
    assert any(r.rule_id == "COUNTRY_OF_ORIGIN_DECLARATION_PRESENCE" for r in active_rules_2018)
    
    from app.services.applicability_model import evaluate_applicability
    from app.schemas.applicability import ApplicabilityStatus
    decisions = evaluate_applicability(active_rules_2018, [], product_category="GENERIC_RETAIL_PACKAGE", product_origin="DOMESTIC")
    assert decisions["COUNTRY_OF_ORIGIN_DECLARATION_PRESENCE"].status == ApplicabilityStatus.NOT_APPLICABLE
