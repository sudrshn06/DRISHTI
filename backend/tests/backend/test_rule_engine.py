from datetime import date
from app.schemas.compliance import RuleDefinition, LegalStatus
from app.schemas.ocr import FieldCandidate, NetQuantityNormalized
from app.services.rule_engine import get_applicable_rules, evaluate_candidate

def test_applicable_rule_selection():
    rules = [
        RuleDefinition(
            rule_id="RULE_1",
            rule_version="1.0",
            title="Test Rule",
            description="Test",
            field="NET_QUANTITY",
            effective_from=date(2025, 1, 1),
            effective_to=date(2025, 12, 31),
            evaluation_type="REQUIRED_DECLARATION"
        ),
        RuleDefinition(
            rule_id="RULE_1",
            rule_version="2.0",
            title="Test Rule V2",
            description="Test",
            field="NET_QUANTITY",
            effective_from=date(2026, 1, 1),
            evaluation_type="REQUIRED_DECLARATION"
        ),
        RuleDefinition(
            rule_id="RULE_FUTURE",
            rule_version="1.0",
            title="Future Rule",
            description="Test",
            field="NET_QUANTITY",
            effective_from=date(2027, 1, 1),
            evaluation_type="REQUIRED_DECLARATION"
        ),
        # Overlapping versions for tie-breaking tests
        RuleDefinition(
            rule_id="RULE_OVERLAP",
            rule_version="1.0",
            title="Old Overlap",
            description="Test",
            field="NET_QUANTITY",
            effective_from=date(2026, 1, 1),
            evaluation_type="REQUIRED_DECLARATION"
        ),
        RuleDefinition(
            rule_id="RULE_OVERLAP",
            rule_version="2.0",
            title="New Overlap",
            description="Test",
            field="NET_QUANTITY",
            effective_from=date(2026, 5, 1),
            evaluation_type="REQUIRED_DECLARATION"
        ),
        # Tie break on same effective date
        RuleDefinition(
            rule_id="RULE_TIE",
            rule_version="1.0",
            title="Tie 1",
            description="Test",
            field="NET_QUANTITY",
            effective_from=date(2026, 1, 1),
            evaluation_type="REQUIRED_DECLARATION"
        ),
        RuleDefinition(
            rule_id="RULE_TIE",
            rule_version="2.0",
            title="Tie 2",
            description="Test",
            field="NET_QUANTITY",
            effective_from=date(2026, 1, 1),
            evaluation_type="REQUIRED_DECLARATION"
        )
    ]
    
    # 4. Applicable rule version selected by inspection date
    active = get_applicable_rules(rules, date(2026, 8, 24))
    
    rule1_active = next(r for r in active if r.rule_id == "RULE_1")
    assert rule1_active.rule_version == "2.0"
    
    # F. Expired rule version not selected
    active_past = get_applicable_rules(rules, date(2025, 6, 1))
    rule1_past = next(r for r in active_past if r.rule_id == "RULE_1")
    assert rule1_past.rule_version == "1.0"
    
    # G. Future rule version not selected
    assert not any(r.rule_id == "RULE_FUTURE" for r in active)
    
    # D. overlapping versions of same rule: reference date after newer effective_from => ONLY newer applicable version selected
    rule_overlap = next(r for r in active if r.rule_id == "RULE_OVERLAP")
    assert rule_overlap.rule_version == "2.0"
    
    # E. date before newer version effective_from => older version selected
    active_before_new = get_applicable_rules(rules, date(2026, 4, 1))
    rule_overlap_old = next(r for r in active_before_new if r.rule_id == "RULE_OVERLAP")
    assert rule_overlap_old.rule_version == "1.0"

    # H. version selection gives identical result regardless of input list order (and tie breaks work)
    active_tie = next(r for r in active if r.rule_id == "RULE_TIE")
    assert active_tie.rule_version == "2.0"
    
    rules_reversed = rules[::-1]
    active_reversed = get_applicable_rules(rules_reversed, date(2026, 8, 24))
    active_tie_rev = next(r for r in active_reversed if r.rule_id == "RULE_TIE")
    assert active_tie_rev.rule_version == "2.0"

def test_evaluate_candidate_detected_pass():
    # 1. DETECTED valid evidence + fictional required-field rule -> PASS
    rule = RuleDefinition(
        rule_id="TEST_NET_QTY_PRESENT",
        rule_version="1.0",
        title="Test",
        description="Test",
        field="NET_QUANTITY",
        effective_from=date(2026, 1, 1),
        evaluation_type="REQUIRED_DECLARATION"
    )
    
    candidate = FieldCandidate(
        field="NET_QUANTITY",
        status="DETECTED",
        raw_value="500 ml",
        normalized_value=NetQuantityNormalized(value=500.0, unit="ml"),
        evidence_ids=["ev_1"]
    )
    
    result = evaluate_candidate(candidate, rule, date(2026, 8, 24))
    assert result.status == LegalStatus.PASS

def test_evaluate_candidate_review_required():
    # 2. extraction REVIEW_REQUIRED -> legal REVIEW_REQUIRED
    rule = RuleDefinition(
        rule_id="TEST_NET_QTY_PRESENT",
        rule_version="1.0",
        title="Test",
        description="Test",
        field="NET_QUANTITY",
        effective_from=date(2026, 1, 1),
        evaluation_type="REQUIRED_DECLARATION"
    )
    
    candidate = FieldCandidate(
        field="NET_QUANTITY",
        status="REVIEW_REQUIRED",
        raw_value=None,
        evidence_ids=["ev_1"]
    )
    
    result = evaluate_candidate(candidate, rule, date(2026, 8, 24))
    assert result.status == LegalStatus.REVIEW_REQUIRED

def test_evaluate_candidate_not_detected():
    # 3. NOT_DETECTED under incomplete/single-image evidence -> must NOT become FAIL
    rule = RuleDefinition(
        rule_id="TEST_NET_QTY_PRESENT",
        rule_version="1.0",
        title="Test",
        description="Test",
        field="NET_QUANTITY",
        effective_from=date(2026, 1, 1),
        evaluation_type="REQUIRED_DECLARATION"
    )
    
    candidate = FieldCandidate(
        field="NET_QUANTITY",
        status="NOT_DETECTED"
    )
    
    result = evaluate_candidate(candidate, rule, date(2026, 8, 24))
    assert result.status == LegalStatus.REVIEW_REQUIRED

def test_evaluate_candidate_allowed_unit_fail():
    rule = RuleDefinition(
        rule_id="TEST_UNIT",
        rule_version="1.0",
        title="Test",
        description="Test",
        field="NET_QUANTITY",
        effective_from=date(2026, 1, 1),
        evaluation_type="ALLOWED_UNIT",
        parameters={"allowed_units": ["ml", "l"]}
    )
    
    candidate = FieldCandidate(
        field="NET_QUANTITY",
        status="DETECTED",
        raw_value="500 g",
        normalized_value=NetQuantityNormalized(value=500.0, unit="g")
    )
    
    result = evaluate_candidate(candidate, rule, date(2026, 8, 24))
    assert result.status == LegalStatus.FAIL

def test_product_scope_matching():
    candidate = FieldCandidate(field="NET_QUANTITY", status="DETECTED")
    
    # A. product_scope ALL -> rule evaluated normally
    rule_all = RuleDefinition(
        rule_id="TEST_ALL", rule_version="1.0", title="Test", description="Test", field="NET_QUANTITY",
        effective_from=date(2026, 1, 1), evaluation_type="REQUIRED_DECLARATION", product_scope="ALL"
    )
    result_all = evaluate_candidate(candidate, rule_all, date(2026, 8, 24), product_category="COSMETIC")
    assert result_all.status == LegalStatus.PASS
    
    # B. matching fictional product scope -> rule evaluated normally
    rule_match = RuleDefinition(
        rule_id="TEST_MATCH", rule_version="1.0", title="Test", description="Test", field="NET_QUANTITY",
        effective_from=date(2026, 1, 1), evaluation_type="REQUIRED_DECLARATION", product_scope="COSMETIC"
    )
    result_match = evaluate_candidate(candidate, rule_match, date(2026, 8, 24), product_category="COSMETIC")
    assert result_match.status == LegalStatus.PASS
    
    # C. non-matching fictional product scope -> NOT_APPLICABLE
    rule_mismatch = RuleDefinition(
        rule_id="TEST_MISMATCH", rule_version="1.0", title="Test", description="Test", field="NET_QUANTITY",
        effective_from=date(2026, 1, 1), evaluation_type="REQUIRED_DECLARATION", product_scope="COSMETIC"
    )
    result_mismatch = evaluate_candidate(candidate, rule_mismatch, date(2026, 8, 24), product_category="FOOD")
    assert result_mismatch.status == LegalStatus.NOT_APPLICABLE

def test_deterministic_repeatability():
    # 8. deterministic repeatability
    rule = RuleDefinition(
        rule_id="TEST_REPEAT",
        rule_version="1.0",
        title="Test",
        description="Test",
        field="NET_QUANTITY",
        effective_from=date(2026, 1, 1),
        evaluation_type="REQUIRED_DECLARATION"
    )
    candidate = FieldCandidate(field="NET_QUANTITY", status="DETECTED")
    
    result1 = evaluate_candidate(candidate, rule, date(2026, 8, 24))
    result2 = evaluate_candidate(candidate, rule, date(2026, 8, 24))
    
    assert result1.status == result2.status
    assert result1.reason == result2.reason
