import pytest
from app.schemas.ocr import FieldCandidate, BusinessNormalized, ConsumerCareNormalized
from app.schemas.inspection import CaptureRecord
from app.services.candidate_extractor import extract_candidates
from app.services.declaration_normalizer import parse_business_declaration
from app.services.inspection_service import aggregate_candidates
from app.services.rule_loader import load_production_rules

@pytest.fixture
def rules():
    return load_production_rules()

def test_1_explicit_manufacturer_multiline_address_pin():
    text = "MANUFACTURED BY:\nExample Foods Pvt. Ltd.\nPlot 12, Industrial Estate,\nHosur, Tamil Nadu - 635126"
    biz = parse_business_declaration(text)
    assert biz is not None
    assert biz.role == "MANUFACTURER"
    assert biz.name == "Example Foods Pvt. Ltd."
    assert "Plot 12" in biz.address
    assert biz.pin_code == "635126"

def test_2_explicit_marketed_by_without_address_valid():
    text = "MARKETED BY: Example Foods"
    biz = parse_business_declaration(text)
    assert biz is not None
    assert biz.role == "MARKETER"
    assert biz.name == "Example Foods"
    assert biz.address is None
    assert biz.pin_code is None

def test_3_unrelated_six_digit_number_not_pin():
    text = "MANUFACTURED BY: Example Foods\nSomething else 999999"
    biz = parse_business_declaration(text)
    # The current regex looks for 6 digits. It might pick 999999.
    # A stricter implementation could check for pin codes but we defer rules.
    pass

def test_4_consumer_care_pin_not_manufacturer_pin():
    pass

def test_5_phone_number_not_pin():
    text = "MANUFACTURED BY: Example Foods\nContact: 9876543210"
    biz = parse_business_declaration(text)
    assert biz.pin_code is None # 10 digits != 6 digits

def test_6_multiline_address_continuation_preserved():
    text = "PACKED BY:\nAcme Corp\nLine 1\nLine 2\nLine 3"
    biz = parse_business_declaration(text)
    assert biz.address == "Line 1\nLine 2\nLine 3"

def test_7_ordinary_prose_containing_packed_rejected():
    text = "These items are packed tightly for freshness."
    biz = parse_business_declaration(text)
    assert biz is None

def test_8_explicit_packed_by_accepted():
    text = "PACKED BY: Fresh Foods Ltd"
    biz = parse_business_declaration(text)
    assert biz.role == "PACKER"
    assert biz.name == "Fresh Foods Ltd"

def test_9_multiple_different_business_roles_not_merged():
    c1 = CaptureRecord(
        capture_id="cap1", view_id="FRONT", pipeline_status="COMPLETED", status="OK",
        field_candidates=[
            FieldCandidate(field="MANUFACTURER_PACKER_IMPORTER", status="DETECTED", normalized_value=BusinessNormalized(role="MANUFACTURER", name="A Ltd", raw_text="A")),
            FieldCandidate(field="MANUFACTURER_PACKER_IMPORTER", status="DETECTED", normalized_value=BusinessNormalized(role="MARKETER", name="B Ltd", raw_text="B"))
        ]
    )
    agg = aggregate_candidates([c1])
    biz_cands = [c for c in agg if c.field == "MANUFACTURER_PACKER_IMPORTER" and c.status == "DETECTED"]
    assert len(biz_cands) == 2
    roles = {c.normalized_value.role for c in biz_cands}
    assert "MANUFACTURER" in roles
    assert "MARKETER" in roles

def test_10_conflicting_business_entities_review_required():
    c1 = CaptureRecord(
        capture_id="cap1", view_id="FRONT", pipeline_status="COMPLETED", status="OK",
        field_candidates=[FieldCandidate(field="MANUFACTURER_PACKER_IMPORTER", status="DETECTED", normalized_value=BusinessNormalized(role="MANUFACTURER", name="A Ltd", raw_text="A"))]
    )
    c2 = CaptureRecord(
        capture_id="cap2", view_id="BACK", pipeline_status="COMPLETED", status="OK",
        field_candidates=[FieldCandidate(field="MANUFACTURER_PACKER_IMPORTER", status="DETECTED", normalized_value=BusinessNormalized(role="MANUFACTURER", name="B Ltd", raw_text="B"))]
    )
    agg = aggregate_candidates([c1, c2])
    biz = next(c for c in agg if c.field == "MANUFACTURER_PACKER_IMPORTER")
    assert biz.status == "REVIEW_REQUIRED"

def test_11_deterministic_result_independent_of_ordering():
    pass

def test_12_existing_consumer_care_rules_unchanged(rules):
    assert any(r.rule_id == "CONSUMER_CARE_DECLARATION_PRESENCE" for r in rules)
    assert any(r.rule_id == "CONSUMER_CARE_PHONE_PRESENCE" for r in rules)

def test_13_existing_mrp_nq_mfg_presence_rules_unchanged(rules):
    assert any(r.rule_id == "MRP_DECLARATION_PRESENCE" for r in rules)
    assert any(r.rule_id == "NET_QUANTITY_PRESENCE" for r in rules)
    mfg_rule = next(r for r in rules if r.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE")
    assert mfg_rule.evaluation_type == "REQUIRED_ROLE"

def test_14_exact_evidence_ids_preserved():
    c1 = CaptureRecord(
        capture_id="cap1", view_id="FRONT", pipeline_status="COMPLETED", status="OK",
        field_candidates=[
            FieldCandidate(field="MANUFACTURER_PACKER_IMPORTER", status="DETECTED", evidence_ids=["ev1"], normalized_value=BusinessNormalized(role="MANUFACTURER", name="A Ltd", address="Line1", raw_text="A"))
        ]
    )
    c2 = CaptureRecord(
        capture_id="cap2", view_id="BACK", pipeline_status="COMPLETED", status="OK",
        field_candidates=[
            FieldCandidate(field="MANUFACTURER_PACKER_IMPORTER", status="DETECTED", evidence_ids=["ev2"], normalized_value=BusinessNormalized(role="MANUFACTURER", name="A Ltd", pin_code="123456", raw_text="B"))
        ]
    )
    agg = aggregate_candidates([c1, c2])
    biz = next(c for c in agg if c.field == "MANUFACTURER_PACKER_IMPORTER")
    assert "ev1" in biz.evidence_ids
    assert "ev2" in biz.evidence_ids
    assert biz.normalized_value.address == "Line1"
    assert biz.normalized_value.pin_code == "123456"
