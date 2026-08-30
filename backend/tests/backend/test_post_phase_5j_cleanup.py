import pytest
from app.schemas.ocr import FieldCandidate
from app.schemas.ocr import DateNormalized, BusinessNormalized, MrpNormalized
import datetime
from app.services.candidate_extractor import extract_candidates
from app.services.compliance_service import orchestrate_compliance
from app.schemas.ocr import OcrLine

def test_redundant_unknown_month_year():
    # FIX A
    # If an UNKNOWN MONTH_YEAR candidate comes from the same underlying token
    # already represented by a strong specific subtype, suppress it.
    
    # Simulate extraction on "MFD 12/2023" over two lines
    lines = [
        OcrLine(text="MFD", confidence=0.99, polygon=[]),
        OcrLine(text="12/2023", confidence=0.99, polygon=[])
    ]
    evidence_map = {"0": "ev_1", "1": "ev_2"}
    
    candidates = extract_candidates(lines, evidence_map)
    
    date_cands = [c for c in candidates if c.field == "MONTH_YEAR" and c.status != "NOT_DETECTED"]
    assert len(date_cands) == 1
    assert date_cands[0].normalized_value.type == "MANUFACTURED"

def test_separate_unknown_date_preserved():
    # Separate unknown date remains preserved
    lines = [
        OcrLine(text="MFD 10/2023", confidence=0.99, polygon=[]),
        OcrLine(text="11/2024", confidence=0.99, polygon=[])
    ]
    evidence_map = {"0": "ev_1", "1": "ev_2"}
    
    candidates = extract_candidates(lines, evidence_map)
    
    date_cands = [c for c in candidates if c.field == "MONTH_YEAR" and c.status != "NOT_DETECTED"]
    # We should have MANUFACTURED and UNKNOWN
    assert len(date_cands) == 2
    types = {c.normalized_value.type for c in date_cands}
    assert "MANUFACTURED" in types
    assert "UNKNOWN" in types


def test_mrp_weak_candidate_false_conflict():
    # FIX B
    # Valid parsed MRP DETECTED + weaker unparsed REVIEW_REQUIRED MRP
    candidates = [
        FieldCandidate(
            field="MRP",
            status="DETECTED",
            normalized_value=MrpNormalized(currency="INR", amount=50.0),
            raw_value="MRP Rs. 50",
            evidence_ids=["ev_1", "ev_2"]
        ),
        FieldCandidate(
            field="MRP",
            status="REVIEW_REQUIRED",
            raw_value="INCLUSIVE OF ALL TAXES",
            evidence_ids=["ev_2"]
        )
    ]
    
    results = orchestrate_compliance(candidates, datetime.date(2023, 1, 1), "GENERIC_RETAIL_PACKAGE")
    
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == "PASS"

def test_mrp_weak_candidate_separate_region():
    # FIX B
    # Valid parsed MRP DETECTED in region A + weaker unparsed REVIEW_REQUIRED MRP in region B
    candidates = [
        FieldCandidate(
            field="MRP",
            status="DETECTED",
            normalized_value=MrpNormalized(currency="INR", amount=50.0),
            raw_value="MRP Rs. 50",
            evidence_ids=["ev_1"]
        ),
        FieldCandidate(
            field="MRP",
            status="REVIEW_REQUIRED",
            raw_value="INCLUSIVE OF ALL TAXES",
            evidence_ids=["ev_99"]
        )
    ]
    
    results = orchestrate_compliance(candidates, datetime.date(2023, 1, 1), "GENERIC_RETAIL_PACKAGE")
    
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == "REVIEW_REQUIRED"
    assert "Conflicting declaration evidence" in mrp_result.reason

def test_malformed_anchored_mrp_only():
    candidates = [
        FieldCandidate(
            field="MRP",
            status="REVIEW_REQUIRED",
            raw_value="INCLUSIVE OF ALL TAXES"
        )
    ]
    results = orchestrate_compliance(candidates, datetime.date(2023, 1, 1), "GENERIC_RETAIL_PACKAGE")
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == "REVIEW_REQUIRED"

def test_genuinely_conflicting_strong_mrp():
    candidates = [
        FieldCandidate(
            field="MRP",
            status="DETECTED",
            normalized_value=MrpNormalized(currency="INR", amount=50.0),
            raw_value="MRP Rs. 50"
        ),
        FieldCandidate(
            field="MRP",
            status="DETECTED",
            normalized_value=MrpNormalized(currency="INR", amount=60.0),
            raw_value="MRP Rs. 60"
        )
    ]
    results = orchestrate_compliance(candidates, datetime.date(2023, 1, 1), "GENERIC_RETAIL_PACKAGE")
    mrp_result = next(r for r in results if r.rule_id == "MRP_DECLARATION_PRESENCE")
    assert mrp_result.status == "REVIEW_REQUIRED"
    assert "Conflicting declaration evidence" in mrp_result.reason


def test_business_role_aware_conflict_handling():
    # FIX C
    # Manufacturer + Packer coexist
    candidates = [
        FieldCandidate(
            field="MANUFACTURER_PACKER_IMPORTER",
            status="DETECTED",
            normalized_value=BusinessNormalized(role="MANUFACTURER", name="A", raw_text="MFD BY A"),
            raw_value="MFD BY A"
        ),
        FieldCandidate(
            field="MANUFACTURER_PACKER_IMPORTER",
            status="DETECTED",
            normalized_value=BusinessNormalized(role="PACKER", name="B", raw_text="PACKED BY B"),
            raw_value="PACKED BY B"
        )
    ]
    results = orchestrate_compliance(candidates, datetime.date(2023, 1, 1), "GENERIC_RETAIL_PACKAGE", regulatory_category="NON_FOOD")
    biz_result = next(r for r in results if r.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE")
    assert biz_result.status == "PASS"

def test_marketer_does_not_satisfy():
    candidates = [
        FieldCandidate(
            field="MANUFACTURER_PACKER_IMPORTER",
            status="DETECTED",
            normalized_value=BusinessNormalized(role="MARKETER", name="Z", raw_text="MARKETED BY Z"),
            raw_value="MARKETED BY Z"
        )
    ]
    results = orchestrate_compliance(candidates, datetime.date(2023, 1, 1), "GENERIC_RETAIL_PACKAGE", regulatory_category="NON_FOOD", evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION")
    biz_result = next(r for r in results if r.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE")
    assert biz_result.status == "FAIL"

def test_conflicting_same_role_strong_evidence():
    candidates = [
        FieldCandidate(
            field="MANUFACTURER_PACKER_IMPORTER",
            status="DETECTED",
            normalized_value=BusinessNormalized(role="MANUFACTURER", name="A", raw_text="MFD BY A"),
            raw_value="MFD BY A"
        ),
        FieldCandidate(
            field="MANUFACTURER_PACKER_IMPORTER",
            status="DETECTED",
            normalized_value=BusinessNormalized(role="MANUFACTURER", name="B", raw_text="MFD BY B"),
            raw_value="MFD BY B"
        )
    ]
    results = orchestrate_compliance(candidates, datetime.date(2023, 1, 1), "GENERIC_RETAIL_PACKAGE", regulatory_category="NON_FOOD")
    biz_result = next(r for r in results if r.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE")
    assert biz_result.status == "REVIEW_REQUIRED"
    assert "Conflicting declaration evidence" in biz_result.reason
