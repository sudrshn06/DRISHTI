from datetime import date
from app.schemas.ocr import OcrLine, FieldCandidate
from app.services.candidate_extractor import extract_candidates
from app.services.compliance_service import orchestrate_compliance

def helper_run_evals(
    lines,
    ref_date=date(2024, 1, 1),
    date_regime="GENERAL",
    date_exemp="NONE",
    sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"
):
    cands = extract_candidates(lines, {})
    evals = orchestrate_compliance(
        candidates=cands,
        reference_date=ref_date,
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin="UNKNOWN",
        regulatory_category="UNKNOWN",
        is_electronic="UNKNOWN",
        package_structure="SINGLE",
        alcohol_context="NON_ALCOHOLIC",
        date_regulatory_regime=date_regime,
        date_package_exemption=date_exemp,
        evidence_sufficiency=sufficiency,
        inspection_complete=True
    )
    month_year = next((r for r in evals if r.rule_id == "MONTH_YEAR_DECLARATION_PRESENCE"), None)
    return cands, month_year

# LEGAL VERSION BOUNDARIES
def test_1_before_2011():
    _, r = helper_run_evals([OcrLine(text="MFD 01/2020", confidence=0.9, polygon=[])], ref_date=date(2011, 3, 31))
    assert r is None # Inactive

def test_2_on_2011():
    _, r = helper_run_evals([OcrLine(text="MFD 01/2020", confidence=0.9, polygon=[])], ref_date=date(2011, 4, 1))
    assert r.status.value == "PASS"

def test_3_pre_2024_semantics():
    # Packing is allowed
    _, r = helper_run_evals([OcrLine(text="PKD 01/2023", confidence=0.9, polygon=[])], ref_date=date(2023, 12, 31))
    assert r.status.value == "PASS"

def test_4_2024_semantics():
    # Packing is NOT allowed
    _, r = helper_run_evals([OcrLine(text="PKD 01/2024", confidence=0.9, polygon=[])], ref_date=date(2024, 1, 1))
    assert r.status.value == "FAIL"

# PRE-2024 SUBTYPES
def test_5_pre2024_manufacture():
    _, r = helper_run_evals([OcrLine(text="MFD 01/2020", confidence=0.9, polygon=[])], ref_date=date(2023, 12, 31))
    assert r.status.value == "PASS"

def test_6_pre2024_packing():
    _, r = helper_run_evals([OcrLine(text="PKD 01/2020", confidence=0.9, polygon=[])], ref_date=date(2023, 12, 31))
    assert r.status.value == "PASS"

def test_7_pre2024_import():
    _, r = helper_run_evals([OcrLine(text="IMPORTED 01/2020", confidence=0.9, polygon=[])], ref_date=date(2023, 12, 31))
    assert r.status.value == "PASS"

# 2024+ RESTRICTION
def test_8_2024_manufacture():
    _, r = helper_run_evals([OcrLine(text="MFD 01/2024", confidence=0.9, polygon=[])], ref_date=date(2024, 1, 1))
    assert r.status.value == "PASS"

def test_9_2024_packing_only_fails():
    _, r = helper_run_evals([OcrLine(text="PKD 01/2024", confidence=0.9, polygon=[])], ref_date=date(2024, 1, 1))
    assert r.status.value == "FAIL"

def test_10_2024_import_only_fails():
    _, r = helper_run_evals([OcrLine(text="IMPORT DATE 01/2024", confidence=0.9, polygon=[])], ref_date=date(2024, 1, 1))
    assert r.status.value == "FAIL"

# FORMATS
def test_11_mm_yyyy():
    c, r = helper_run_evals([OcrLine(text="MFD 05/2023", confidence=0.9, polygon=[])])
    cand = next(x for x in c if x.field == "MONTH_YEAR")
    assert cand.normalized_value.month == 5
    assert cand.normalized_value.year == 2023

def test_12_mmm_yyyy():
    c, r = helper_run_evals([OcrLine(text="MFD JAN 2023", confidence=0.9, polygon=[])])
    cand = next(x for x in c if x.field == "MONTH_YEAR")
    assert cand.normalized_value.month == 1
    assert cand.normalized_value.year == 2023

def test_13_dd_mm_yyyy():
    c, r = helper_run_evals([OcrLine(text="MFD 15/05/2023", confidence=0.9, polygon=[])])
    cand = next(x for x in c if x.field == "MONTH_YEAR")
    assert cand.normalized_value.day == 15
    assert cand.normalized_value.month == 5
    assert cand.normalized_value.year == 2023

def test_14_dd_mm_yy():
    c, r = helper_run_evals([OcrLine(text="MFD 15/05/23", confidence=0.9, polygon=[])])
    cand = next(x for x in c if x.field == "MONTH_YEAR")
    assert cand.normalized_value.year == 2023

# CONFLICTS (same subtype)
def test_15_conflict_same_subtype_different_values():
    _, r = helper_run_evals([
        OcrLine(text="MFD 01/2024", confidence=0.9, polygon=[]),
        OcrLine(text="MFD 02/2024", confidence=0.9, polygon=[])
    ], ref_date=date(2024, 1, 1))
    assert r.status.value == "REVIEW_REQUIRED"

def test_16_conflict_same_subtype_same_values():
    _, r = helper_run_evals([
        OcrLine(text="MFD 01/2024", confidence=0.9, polygon=[]),
        OcrLine(text="MFD 01/2024", confidence=0.9, polygon=[])
    ], ref_date=date(2024, 1, 1))
    assert r.status.value == "PASS"

# NON-CONFLICTS (different subtypes)
def test_17_no_conflict_mfd_pkd():
    _, r = helper_run_evals([
        OcrLine(text="MFD 01/2023", confidence=0.9, polygon=[]),
        OcrLine(text="PKD 02/2023", confidence=0.9, polygon=[])
    ], ref_date=date(2023, 1, 1))
    assert r.status.value == "PASS"

def test_18_no_conflict_mfd_imp():
    _, r = helper_run_evals([
        OcrLine(text="MFD 01/2023", confidence=0.9, polygon=[]),
        OcrLine(text="IMPORTED 02/2023", confidence=0.9, polygon=[])
    ], ref_date=date(2023, 1, 1))
    assert r.status.value == "PASS"

def test_19_best_before_duration():
    c, _ = helper_run_evals([OcrLine(text="BEST BEFORE 6 MONTHS", confidence=0.9, polygon=[])])
    cand = next(x for x in c if x.field == "MONTH_YEAR")
    assert cand.normalized_value.type == "BEST_BEFORE"
    assert cand.normalized_value.duration == 6
    assert cand.normalized_value.duration_unit == "MONTH"

def test_20_use_by_date():
    c, _ = helper_run_evals([OcrLine(text="USE BY 10/2024", confidence=0.9, polygon=[])])
    cand = next(x for x in c if x.field == "MONTH_YEAR")
    assert cand.normalized_value.type == "USE_BY"
    assert cand.normalized_value.month == 10

def test_21_expiry_date():
    c, _ = helper_run_evals([OcrLine(text="EXP 12/2024", confidence=0.9, polygon=[])])
    cand = next(x for x in c if x.field == "MONTH_YEAR")
    assert cand.normalized_value.type == "EXPIRY"
    assert cand.normalized_value.month == 12

def test_22_use_by_does_not_pass_presence():
    _, r = helper_run_evals([OcrLine(text="USE BY 10/2024", confidence=0.9, polygon=[])], ref_date=date(2024, 1, 1))
    assert r.status.value == "FAIL"

# DEFERRED REGIMES
def test_23_food_deferred():
    _, r = helper_run_evals([], date_regime="FOOD")
    assert r.status.value == "NOT_APPLICABLE"

def test_24_seed_deferred():
    _, r = helper_run_evals([], date_regime="CERTIFIED_SEED")
    assert r.status.value == "NOT_APPLICABLE"

def test_25_cosmetic_deferred():
    _, r = helper_run_evals([], date_regime="COSMETIC")
    assert r.status.value == "NOT_APPLICABLE"

# EXEMPTIONS
def test_26_bidi_exemption():
    _, r = helper_run_evals([], date_exemp="BIDI_OR_INCENSE")
    assert r.status.value == "NOT_APPLICABLE"

def test_27_lpg_exemption():
    _, r = helper_run_evals([], date_exemp="PSU_DOMESTIC_LPG_14_2_OR_5KG")
    assert r.status.value == "NOT_APPLICABLE"

def test_28_unknown_regime_fails_safe():
    _, r = helper_run_evals([], date_regime="UNKNOWN")
    assert r.status.value == "REVIEW_REQUIRED"

def test_29_unknown_exemption_fails_safe():
    _, r = helper_run_evals([], date_regime="GENERAL", date_exemp="UNKNOWN")
    assert r.status.value == "REVIEW_REQUIRED"

# ADDITIONAL DATE TESTS
def test_30_only_packing_pre2024():
    _, r = helper_run_evals([OcrLine(text="PKD 05/2022", confidence=0.9, polygon=[])], ref_date=date(2022, 1, 1))
    assert r.status.value == "PASS"

def test_31_multiple_dates_2024_fails_if_only_pkd():
    _, r = helper_run_evals([
        OcrLine(text="PKD 05/2024", confidence=0.9, polygon=[]),
        OcrLine(text="EXP 05/2025", confidence=0.9, polygon=[])
    ], ref_date=date(2024, 6, 1))
    assert r.status.value == "FAIL"

def test_32_multiple_dates_2024_passes_if_mfd():
    _, r = helper_run_evals([
        OcrLine(text="MFD 05/2024", confidence=0.9, polygon=[]),
        OcrLine(text="EXP 05/2025", confidence=0.9, polygon=[])
    ], ref_date=date(2024, 6, 1))
    assert r.status.value == "PASS"

def test_33_pre2024_imported_and_packed():
    _, r = helper_run_evals([
        OcrLine(text="IMPORTED 05/2022", confidence=0.9, polygon=[]),
        OcrLine(text="PKD 06/2022", confidence=0.9, polygon=[])
    ], ref_date=date(2022, 1, 1))
    assert r.status.value == "PASS"

def test_34_2024_imported_and_packed():
    _, r = helper_run_evals([
        OcrLine(text="IMPORTED 05/2024", confidence=0.9, polygon=[]),
        OcrLine(text="PKD 06/2024", confidence=0.9, polygon=[])
    ], ref_date=date(2024, 1, 1))
    assert r.status.value == "FAIL"

def test_35_malformed_date_causes_review():
    _, r = helper_run_evals([OcrLine(text="MFD XX/2024", confidence=0.9, polygon=[])], ref_date=date(2024, 1, 1))
    assert r.status.value == "REVIEW_REQUIRED"

def test_36_review_required_on_low_confidence():
    _, r = helper_run_evals([OcrLine(text="MFD 05/2024", confidence=0.5, polygon=[])], ref_date=date(2024, 1, 1))
    assert r.status.value == "REVIEW_REQUIRED"

def test_37_insufficient_evidence():
    _, r = helper_run_evals([], ref_date=date(2024, 1, 1), sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION")
    assert r.status.value == "REVIEW_REQUIRED"

def test_38_sufficient_evidence_fails():
    _, r = helper_run_evals([], ref_date=date(2024, 1, 1), sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION")
    assert r.status.value == "FAIL"

def test_39_best_before_days():
    c, _ = helper_run_evals([OcrLine(text="BEST BEFORE 45 DAYS", confidence=0.9, polygon=[])])
    cand = next(x for x in c if x.field == "MONTH_YEAR")
    assert cand.normalized_value.duration == 45
    assert cand.normalized_value.duration_unit == "DAY"

def test_40_best_before_years():
    c, _ = helper_run_evals([OcrLine(text="BEST BEFORE 2 YEARS", confidence=0.9, polygon=[])])
    cand = next(x for x in c if x.field == "MONTH_YEAR")
    assert cand.normalized_value.duration == 2
    assert cand.normalized_value.duration_unit == "YEAR"

def test_41_best_before_does_not_pass_mfd():
    _, r = helper_run_evals([OcrLine(text="BEST BEFORE 6 MONTHS", confidence=0.9, polygon=[])], ref_date=date(2024, 1, 1))
    assert r.status.value == "FAIL"

def test_42_mfd_date_and_best_before():
    _, r = helper_run_evals([
        OcrLine(text="MFD 01/2024", confidence=0.9, polygon=[]),
        OcrLine(text="BEST BEFORE 6 MONTHS", confidence=0.9, polygon=[])
    ], ref_date=date(2024, 1, 1))
    assert r.status.value == "PASS"

def test_43_mfd_date_and_use_by():
    _, r = helper_run_evals([
        OcrLine(text="MFD 01/2024", confidence=0.9, polygon=[]),
        OcrLine(text="USE BY 07/2024", confidence=0.9, polygon=[])
    ], ref_date=date(2024, 1, 1))
    assert r.status.value == "PASS"
