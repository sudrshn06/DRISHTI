import pytest
from datetime import date
from app.schemas.ocr import OcrLine, FieldCandidate
from app.services.candidate_extractor import extract_candidates
from app.services.fssai_compliance_service import evaluate_fssai_compliance
from app.schemas.compliance import LegalStatus
from app.schemas.inspection import InspectionSession, CaptureRecord
from app.services.report_service import generate_inspection_report
from app.api.routes.inspections import _update_session_compliance

def test_01_fssai_candidate_extraction():
    dummy_poly = [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]
    lines = [
        OcrLine(text="FSSAI Lic. No: 12345678901234", confidence=0.95, polygon=dummy_poly),
        OcrLine(text="INGREDIENTS: Wheat Flour, Sugar, Palm Oil, Milk Solids, Cocoa", confidence=0.98, polygon=dummy_poly),
        OcrLine(text="CONTAINS MILK AND SOY ALLERGENS", confidence=0.90, polygon=dummy_poly),
        OcrLine(text="NUTRITION FACTS panel per 100g Energy 450 kcal Protein 5g Fat 12g", confidence=0.92, polygon=dummy_poly),
        OcrLine(text="VEG product", confidence=0.88, polygon=dummy_poly),
    ]
    evidence_map = {str(i): f"ev_{i}" for i in range(len(lines))}
    
    candidates = extract_candidates(lines, evidence_map)
    
    def find_cand(field: str):
        return next((c for c in candidates if c.field == field), None)

    lic = find_cand("FSSAI_LICENCE")
    assert lic is not None
    assert lic.status == "DETECTED"
    assert lic.raw_value == "12345678901234"

    veg = find_cand("FSSAI_VEG_NONVEG")
    assert veg is not None
    assert veg.status == "DETECTED"

    ing = find_cand("FSSAI_INGREDIENTS")
    assert ing is not None
    assert ing.status == "DETECTED"
    assert "Wheat Flour" in ing.normalized_value.split("; ")

    allg = find_cand("FSSAI_ALLERGENS")
    assert allg is not None

    nut = find_cand("FSSAI_NUTRITION")
    assert nut is not None


def test_02_fssai_rule_evaluation_logic():
    candidates = [
        FieldCandidate(field="FSSAI_LICENCE", status="DETECTED", raw_value="12345678901234", evidence_ids=["ev_lic"]),
        FieldCandidate(field="FSSAI_VEG_NONVEG", status="DETECTED", raw_value="VEG"),
        FieldCandidate(field="FSSAI_INGREDIENTS", status="DETECTED", raw_value="Ingredients list here"),
        FieldCandidate(field="FSSAI_ALLERGENS", status="DETECTED", raw_value="Contains wheat"),
        FieldCandidate(field="FSSAI_NUTRITION", status="DETECTED", raw_value="Nutrition table"),
    ]
    
    results = evaluate_fssai_compliance(
        candidates, 
        date(2026, 8, 27),
        is_single_ingredient=False,
        is_nutrition_exempt=False,
        veg_nonveg_exempt=False,
        package_area_exemption=False
    )
    
    assert len(results) == 7
    
    for r in results:
        if r.rule_id in ("FSSAI_VEG_NONVEG_SYMBOL", "FSSAI_LICENCE_PRESENCE"):
            assert r.status == LegalStatus.REVIEW_REQUIRED
        elif r.rule_id == "FSSAI_COFFEE_CHICORY_PROPORTIONS":
            assert r.status == LegalStatus.NOT_APPLICABLE
        else:
            assert r.status == LegalStatus.PASS

    # Test Exemption
    results_exempt = evaluate_fssai_compliance(
        candidates,
        date(2026, 8, 27),
        is_single_ingredient=True,
        is_nutrition_exempt=True,
        veg_nonveg_exempt=True,
        package_area_exemption=True
    )
    for r in results_exempt:
        if r.rule_id in ("FSSAI_INGREDIENTS_DECLARATION", "FSSAI_NUTRITIONAL_INFO", "FSSAI_VEG_NONVEG_SYMBOL"):
            assert r.status == LegalStatus.NOT_APPLICABLE


def test_03_compliance_orchestration_domain_separation():
    session = InspectionSession(
        inspection_id="test_10c_inspection",
        capture_plan_id="plan_generic_retail_package",
        reference_date="2026-08-27",
        product_category="GENERIC_RETAIL_PACKAGE",
        regulatory_product_class="FOOD",
        evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        captures=[],
        aggregated_candidates=[
            FieldCandidate(field="FSSAI_LICENCE", status="DETECTED", raw_value="12345678901234")
        ]
    )
    
    _update_session_compliance(session)
    
    assert session.food_label_evaluations is not None
    assert len(session.food_label_evaluations) == 7
    
    lic_rule = next(r for r in session.food_label_evaluations if r.rule_id == "FSSAI_LICENCE_PRESENCE")
    assert lic_rule.status == LegalStatus.REVIEW_REQUIRED
    assert "Regulation 5(7)" in lic_rule.source_reference

    report = generate_inspection_report(session)
    assert report.food_label_findings is not None
    assert all("FSSAI" in f.rule_id for f in report.food_label_findings)
    assert all("FSSAI" not in f.rule_id for f in report.declaration_findings)


def test_04_date_version_boundaries():
    candidates = [
        FieldCandidate(field="FSSAI_LICENCE", status="DETECTED", raw_value="12345678901234")
    ]

    # 1. reference_date 2026-08-27 (Future 2026 amendment not active)
    res_2026 = evaluate_fssai_compliance(candidates, date(2026, 8, 27))
    for r in res_2026:
        if r.rule_id in ("FSSAI_INGREDIENTS_DECLARATION", "FSSAI_NUTRITIONAL_INFO"):
            assert r.rule_version == "1.0"
            assert "not yet effective" in r.reason

    # 2. reference_date 2027-06-30 (Just before effective date)
    res_2027_pre = evaluate_fssai_compliance(candidates, date(2027, 6, 30))
    for r in res_2027_pre:
        if r.rule_id in ("FSSAI_INGREDIENTS_DECLARATION", "FSSAI_NUTRITIONAL_INFO"):
            assert r.rule_version == "1.0"
            assert "not yet effective" in r.reason

    # 3. reference_date 2027-07-01 (Effective date reached)
    res_2027_post = evaluate_fssai_compliance(candidates, date(2027, 7, 1))
    for r in res_2027_post:
        if r.rule_id in ("FSSAI_INGREDIENTS_DECLARATION", "FSSAI_NUTRITIONAL_INFO"):
            assert r.rule_version == "1.1"
            assert "active" in r.reason

    # 4. Coffee-Chicory Proportions 2025 Amendment Date Checks
    # Final Gazette Notification: 8 August 2025 | Effective: 1 July 2026
    chicory_cands = [
        FieldCandidate(field="COMMON_GENERIC_NAME", status="DETECTED", raw_value="Coffee-Chicory Mixture"),
        FieldCandidate(field="FSSAI_INGREDIENTS", status="DETECTED", raw_value="Contains Coffee 70% and Chicory 30%")
    ]
    
    # 4a. Prior to Notification (Pre 2025-08-08) -> NOT_APPLICABLE
    res_pre_notify = evaluate_fssai_compliance(chicory_cands, date(2025, 8, 7))
    mix_rule_pre = next(r for r in res_pre_notify if r.rule_id == "FSSAI_COFFEE_CHICORY_PROPORTIONS")
    assert mix_rule_pre.status == LegalStatus.NOT_APPLICABLE

    # 4b. Prior to Effective Date (Pre 2026-07-01) -> NOT_APPLICABLE
    res_pre_effective = evaluate_fssai_compliance(chicory_cands, date(2026, 6, 30))
    mix_rule_eff = next(r for r in res_pre_effective if r.rule_id == "FSSAI_COFFEE_CHICORY_PROPORTIONS")
    assert mix_rule_eff.status == LegalStatus.NOT_APPLICABLE

    # 4c. Active under FSSAI 22 July 2026 Direction (2026-08-27) -> PASS with interim PDP text declaration
    res_active_dir = evaluate_fssai_compliance(chicory_cands, date(2026, 8, 27))
    mix_rule_dir = next(r for r in res_active_dir if r.rule_id == "FSSAI_COFFEE_CHICORY_PROPORTIONS")
    assert mix_rule_dir.status == LegalStatus.PASS
    assert "abeyance" in mix_rule_dir.reason
    assert "PDP" in mix_rule_dir.reason

    # 4d. Unrelated generic food -> NOT_APPLICABLE
    generic_cands = [
        FieldCandidate(field="COMMON_GENERIC_NAME", status="DETECTED", raw_value="Chocolate Bar")
    ]
    res_generic = evaluate_fssai_compliance(generic_cands, date(2026, 8, 27))
    mix_rule_gen = next(r for r in res_generic if r.rule_id == "FSSAI_COFFEE_CHICORY_PROPORTIONS")
    assert mix_rule_gen.status == LegalStatus.NOT_APPLICABLE
