import pytest
from datetime import date
from app.schemas.ocr import FieldCandidate, ConsumerCareNormalized, OcrLine, EvidenceItem, OcrEngineInfo
from app.schemas.inspection import CapturePlan, CaptureRecord
from app.services.rule_engine import evaluate_candidate
from app.services.rule_loader import load_production_rules
from app.schemas.compliance import LegalStatus
from app.services.candidate_extractor import extract_candidates
from app.services.declaration_normalizer import parse_consumer_care
from app.services.inspection_service import aggregate_candidates, evaluate_evidence_sufficiency

@pytest.fixture
def rules():
    return load_production_rules()

@pytest.fixture
def cc_phone_rule(rules):
    return next(r for r in rules if r.rule_id == "CONSUMER_CARE_PHONE_PRESENCE")

@pytest.fixture
def cc_email_rule(rules):
    return next(r for r in rules if r.rule_id == "CONSUMER_CARE_EMAIL_PRESENCE")

@pytest.fixture
def cc_general_rule(rules):
    return next(r for r in rules if r.rule_id == "CONSUMER_CARE_DECLARATION_PRESENCE")

def test_1_valid_consumer_care_phone_extraction():
    cc = parse_consumer_care("CONSUMER CARE EXECUTIVE 011-12345678")
    assert cc is not None
    assert cc.phone == "01112345678"

def test_2_valid_toll_free_phone_extraction():
    cc = parse_consumer_care("Toll Free: 1800 123 4567")
    assert cc is not None
    assert cc.phone == "18001234567"

def test_3_valid_mobile_format_extraction():
    cc = parse_consumer_care("Contact: +91 98765 43210")
    assert cc is not None
    assert cc.phone == "+919876543210"

def test_4_pin_code_not_phone():
    cc = parse_consumer_care("Address: Mumbai 400001")
    # Should not pick up 400001 as phone
    assert cc is None or cc.phone is None

def test_5_mrp_batch_date_not_phone():
    cc = parse_consumer_care("MRP Rs 1000.00 Batch No 12345 Mfd 10/2023")
    assert cc is None or cc.phone is None

def test_6_valid_email_extraction():
    cc = parse_consumer_care("Email: care@example.com")
    assert cc is not None
    assert cc.email == "care@example.com"

def test_7_malformed_email():
    cc = parse_consumer_care("Email: care at example com")
    assert cc is None or cc.email is None

def test_8_phone_and_email_rules_pass(cc_phone_rule, cc_email_rule):
    cand = FieldCandidate(
        field="CONSUMER_CARE",
        status="DETECTED",
        normalized_value=ConsumerCareNormalized(phone="18001234567", email="care@example.com")
    )
    res_phone = evaluate_candidate(cand, cc_phone_rule, date(2025,1,1), "GENERIC_RETAIL_PACKAGE")
    assert res_phone.status == LegalStatus.PASS
    res_email = evaluate_candidate(cand, cc_email_rule, date(2025,1,1), "GENERIC_RETAIL_PACKAGE")
    assert res_email.status == LegalStatus.PASS

def test_9_phone_present_email_missing_current_plan(cc_phone_rule, cc_email_rule):
    cand = FieldCandidate(
        field="CONSUMER_CARE",
        status="DETECTED",
        normalized_value=ConsumerCareNormalized(phone="18001234567")
    )
    res_phone = evaluate_candidate(cand, cc_phone_rule, date(2025,1,1), "GENERIC_RETAIL_PACKAGE")
    assert res_phone.status == LegalStatus.PASS
    res_email = evaluate_candidate(cand, cc_email_rule, date(2025,1,1), "GENERIC_RETAIL_PACKAGE", "INSUFFICIENT_FOR_ABSENCE_EVALUATION")
    assert res_email.status == LegalStatus.REVIEW_REQUIRED

def test_10_email_present_phone_missing_current_plan(cc_phone_rule, cc_email_rule):
    cand = FieldCandidate(
        field="CONSUMER_CARE",
        status="DETECTED",
        normalized_value=ConsumerCareNormalized(email="care@example.com")
    )
    res_email = evaluate_candidate(cand, cc_email_rule, date(2025,1,1), "GENERIC_RETAIL_PACKAGE")
    assert res_email.status == LegalStatus.PASS
    res_phone = evaluate_candidate(cand, cc_phone_rule, date(2025,1,1), "GENERIC_RETAIL_PACKAGE", "INSUFFICIENT_FOR_ABSENCE_EVALUATION")
    assert res_phone.status == LegalStatus.REVIEW_REQUIRED

def test_11_synthetic_absence_eligible_plan_missing_phone(cc_phone_rule):
    cand = FieldCandidate(
        field="CONSUMER_CARE",
        status="DETECTED",
        normalized_value=ConsumerCareNormalized(email="care@example.com")
    )
    res_phone = evaluate_candidate(cand, cc_phone_rule, date(2025,1,1), "GENERIC_RETAIL_PACKAGE", "SUFFICIENT_FOR_ABSENCE_EVALUATION")
    assert res_phone.status == LegalStatus.FAIL

def test_12_synthetic_absence_eligible_plan_missing_email(cc_email_rule):
    cand = FieldCandidate(
        field="CONSUMER_CARE",
        status="DETECTED",
        normalized_value=ConsumerCareNormalized(phone="18001234567")
    )
    res_email = evaluate_candidate(cand, cc_email_rule, date(2025,1,1), "GENERIC_RETAIL_PACKAGE", "SUFFICIENT_FOR_ABSENCE_EVALUATION")
    assert res_email.status == LegalStatus.FAIL

def test_13_phone_in_one_capture_email_in_another():
    c1 = CaptureRecord(
        capture_id="cap1", view_id="FRONT", pipeline_status="COMPLETED", status="OK",
        field_candidates=[FieldCandidate(field="CONSUMER_CARE", status="DETECTED", normalized_value=ConsumerCareNormalized(phone="18001234567"))]
    )
    c2 = CaptureRecord(
        capture_id="cap2", view_id="BACK", pipeline_status="COMPLETED", status="OK",
        field_candidates=[FieldCandidate(field="CONSUMER_CARE", status="DETECTED", normalized_value=ConsumerCareNormalized(email="care@example.com"))]
    )
    aggregated = aggregate_candidates([c1, c2])
    cc_cand = next(c for c in aggregated if c.field == "CONSUMER_CARE")
    assert cc_cand.status == "DETECTED"
    assert cc_cand.normalized_value.phone == "18001234567"
    assert cc_cand.normalized_value.email == "care@example.com"

def test_14_unrelated_manufacturer_does_not_satisfy():
    cc = parse_consumer_care("Manufactured by ACME Corp, Mumbai 400001")
    assert cc is None or (cc.phone is None and cc.email is None)

def test_15_exact_source_survives(cc_phone_rule):
    cand = FieldCandidate(
        field="CONSUMER_CARE",
        status="DETECTED",
        normalized_value=ConsumerCareNormalized(phone="18001234567")
    )
    res = evaluate_candidate(cand, cc_phone_rule, date(2025,1,1), "GENERIC_RETAIL_PACKAGE")
    assert res.source_reference == "LMPC (Amendment) Rules, 2015, Rule 6(2) (G.S.R. 385(E))"

def test_16_existing_general_consumer_care_unchanged(cc_general_rule):
    cand = FieldCandidate(
        field="CONSUMER_CARE",
        status="DETECTED",
        normalized_value=ConsumerCareNormalized(phone="18001234567")
    )
    res = evaluate_candidate(cand, cc_general_rule, date(2025,1,1), "GENERIC_RETAIL_PACKAGE")
    assert res.status == LegalStatus.PASS

def test_17_existing_mrp_rules_unchanged(rules):
    mrp_rule = next(r for r in rules if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_rule.evaluation_type == "REQUIRED_DECLARATION"

def test_18_single_image_absence_remains_review_required(cc_phone_rule):
    cand = FieldCandidate(
        field="CONSUMER_CARE",
        status="NOT_DETECTED"
    )
    res = evaluate_candidate(cand, cc_phone_rule, date(2025,1,1), "GENERIC_RETAIL_PACKAGE", "INSUFFICIENT_FOR_ABSENCE_EVALUATION")
    assert res.status == LegalStatus.REVIEW_REQUIRED
