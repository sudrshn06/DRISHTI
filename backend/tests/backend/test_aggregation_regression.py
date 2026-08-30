import pytest
from app.schemas.ocr import FieldCandidate, NetQuantityNormalized, MrpNormalized, BusinessNormalized, DateNormalized, ConsumerCareNormalized
from app.schemas.inspection import CaptureRecord
from app.services.inspection_service import aggregate_candidates
from app.services.candidate_extractor import extract_candidates
from app.schemas.ocr import OcrLine

def test_aggregation_net_quantity_same_normalized_value():
    """
    1. Net Qty:
       "500 g" (REVIEW_REQUIRED) + "Net Weight: 500 g" (DETECTED)
       normalized identically => DETECTED, no conflict
    """
    c1 = CaptureRecord(
        capture_id="c1", view_id="FRONT",
        field_candidates=[
            FieldCandidate(field="NET_QUANTITY", status="REVIEW_REQUIRED", raw_value="500 G", normalized_value=NetQuantityNormalized(value=500.0, unit="g"))
        ]
    )
    c2 = CaptureRecord(
        capture_id="c2", view_id="BACK",
        field_candidates=[
            FieldCandidate(field="NET_QUANTITY", status="DETECTED", raw_value="NET WEIGHT: 500 G", normalized_value=NetQuantityNormalized(value=500.0, unit="g"))
        ]
    )
    agg = aggregate_candidates([c1, c2])
    assert len(agg) == 1
    assert agg[0].field == "NET_QUANTITY"
    assert agg[0].status == "DETECTED"
    assert agg[0].normalized_value.value == 500.0

def test_aggregation_mrp_detected_wins_over_not_detected():
    """
    2. MRP: NOT_DETECTED + ₹110 DETECTED => ₹110 DETECTED
    """
    c1 = CaptureRecord(
        capture_id="c1", view_id="FRONT",
        field_candidates=[
            FieldCandidate(field="MRP", status="NOT_DETECTED")
        ]
    )
    c2 = CaptureRecord(
        capture_id="c2", view_id="BACK",
        field_candidates=[
            FieldCandidate(field="MRP", status="DETECTED", raw_value="MRP 110", normalized_value=MrpNormalized(currency="INR", amount=110.0))
        ]
    )
    agg = aggregate_candidates([c1, c2])
    assert len(agg) == 1
    assert agg[0].field == "MRP"
    assert agg[0].status == "DETECTED"
    assert agg[0].normalized_value.amount == 110.0

def test_manufacturer_not_ordinary_prose():
    """
    3. ordinary prose containing: "...packed hygienically..."
       must not become MANUFACTURER_PACKER_IMPORTER
    """
    lines = [OcrLine(text="carefully sourced and packed hygienically", confidence=0.99, polygon=[[0,0],[1,0],[1,1],[0,1]])]
    cands = extract_candidates(lines, {})
    mfg = next((c for c in cands if c.field == "MANUFACTURER_PACKER_IMPORTER"), None)
    assert mfg is not None
    assert mfg.status == "NOT_DETECTED"

def test_manufacturer_valid_declaration():
    """
    4. actual: "MARKETED BY: Example Foods" with no LTD/PVT/INC
       => valid business declaration
    """
    lines = [OcrLine(text="MARKETED BY: Example Foods", confidence=0.99, polygon=[[0,0],[1,0],[1,1],[0,1]])]
    cands = extract_candidates(lines, {})
    mfg = next((c for c in cands if c.field == "MANUFACTURER_PACKER_IMPORTER"), None)
    assert mfg is not None
    assert mfg.status == "DETECTED"
    assert mfg.normalized_value.role == "MARKETER"
    assert mfg.normalized_value.name == "EXAMPLE FOODS"

def test_consumer_care_boundary():
    """
    5. Consumer Care does not absorb unrelated following section text using structural boundaries.
    The unrelated text will NOT use hardcoded storage phrases.
    """
    lines = [
        OcrLine(text="contact us at support@example.com", confidence=0.99, polygon=[[0,0],[1,0],[1,1],[0,1]]),
        OcrLine(text="Please dispose of carefully in recycling bin", confidence=0.99, polygon=[[0,0],[1,0],[1,1],[0,1]])
    ]
    cands = extract_candidates(lines, {})
    cc = next((c for c in cands if c.field == "CONSUMER_CARE"), None)
    assert cc is not None
    assert cc.status == "DETECTED"
    assert "dispose" not in cc.raw_value.lower()
    assert cc.normalized_value.email == "SUPPORT@EXAMPLE.COM"

def test_aggregation_date_subtypes():
    """
    6. PACKED_ON + USE_BY => not conflict merely because both are MONTH_YEAR
    """
    c1 = CaptureRecord(
        capture_id="c1", view_id="FRONT",
        field_candidates=[
            FieldCandidate(field="MONTH_YEAR", status="DETECTED", raw_value="Packed: 01/2024", normalized_value=DateNormalized(type="PACKED", month=1, year=2024))
        ]
    )
    c2 = CaptureRecord(
        capture_id="c2", view_id="BACK",
        field_candidates=[
            FieldCandidate(field="MONTH_YEAR", status="DETECTED", raw_value="Use By: 01/2025", normalized_value=DateNormalized(type="USE_BY", month=1, year=2025))
        ]
    )
    agg = aggregate_candidates([c1, c2])
    date_cands = [c for c in agg if c.field == "MONTH_YEAR"]
    assert len(date_cands) == 2
    assert all(c.status == "DETECTED" for c in date_cands)
    types = {c.normalized_value.type for c in date_cands}
    assert "PACKED" in types
    assert "USE_BY" in types

def test_aggregation_conflicting_dates():
    """
    7. conflicting PACKED_ON dates => REVIEW_REQUIRED
    """
    c1 = CaptureRecord(
        capture_id="c1", view_id="FRONT",
        field_candidates=[
            FieldCandidate(field="MONTH_YEAR", status="DETECTED", raw_value="Packed: 01/2024", normalized_value=DateNormalized(type="PACKED", month=1, year=2024))
        ]
    )
    c2 = CaptureRecord(
        capture_id="c2", view_id="BACK",
        field_candidates=[
            FieldCandidate(field="MONTH_YEAR", status="DETECTED", raw_value="Packed: 02/2024", normalized_value=DateNormalized(type="PACKED", month=2, year=2024))
        ]
    )
    agg = aggregate_candidates([c1, c2])
    date_cands = [c for c in agg if c.field == "MONTH_YEAR"]
    assert len(date_cands) == 1
    assert date_cands[0].status == "REVIEW_REQUIRED"
