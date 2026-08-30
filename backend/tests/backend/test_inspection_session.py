import pytest
from typing import List
from app.schemas.inspection import CapturePlan, CaptureViewRequirement, CaptureRecord
from app.schemas.ocr import FieldCandidate, MrpNormalized, NetQuantityNormalized
from app.services.inspection_service import evaluate_completeness, aggregate_candidates

@pytest.fixture
def plan() -> CapturePlan:
    return CapturePlan(
        capture_plan_id="plan_1",
        name="Software Inspection",
        views=[
            CaptureViewRequirement(view_id="FRONT", display_name="Front", required=True),
            CaptureViewRequirement(view_id="BACK", display_name="Back", required=True),
            CaptureViewRequirement(view_id="SIDE", display_name="Side", required=False),
        ]
    )

def test_1_required_views_missing(plan):
    # Only FRONT captured, BACK is missing
    captures = [
        CaptureRecord(capture_id="c1", view_id="FRONT", field_candidates=[])
    ]
    assert evaluate_completeness(plan, captures) == "INCOMPLETE_INSPECTION"

def test_2_all_required_views_present(plan):
    captures = [
        CaptureRecord(capture_id="c1", view_id="FRONT", field_candidates=[]),
        CaptureRecord(capture_id="c2", view_id="BACK", field_candidates=[])
    ]
    assert evaluate_completeness(plan, captures) == "COMPLETE_EVIDENCE_CAPTURE"

def test_3_optional_view_missing(plan):
    # FRONT and BACK present, SIDE (optional) missing -> COMPLETE
    captures = [
        CaptureRecord(capture_id="c1", view_id="FRONT", field_candidates=[]),
        CaptureRecord(capture_id="c2", view_id="BACK", field_candidates=[])
    ]
    assert evaluate_completeness(plan, captures) == "COMPLETE_EVIDENCE_CAPTURE"

def test_4_duplicate_view_handling_deterministic(plan):
    # Multiple FRONT and multiple BACK captures should still be COMPLETE
    captures = [
        CaptureRecord(capture_id="c1", view_id="FRONT", field_candidates=[]),
        CaptureRecord(capture_id="c2", view_id="FRONT", field_candidates=[]),
        CaptureRecord(capture_id="c3", view_id="BACK", field_candidates=[]),
        CaptureRecord(capture_id="c4", view_id="BACK", field_candidates=[])
    ]
    assert evaluate_completeness(plan, captures) == "COMPLETE_EVIDENCE_CAPTURE"

def test_5_not_detected_plus_detected_yields_detected():
    # FRONT MRP NOT_DETECTED + BACK MRP ₹149 DETECTED => aggregated MRP ₹149 DETECTED
    c1 = CaptureRecord(
        capture_id="c1", 
        view_id="FRONT", 
        field_candidates=[
            FieldCandidate(field="MRP", status="NOT_DETECTED", evidence_ids=["e1"])
        ]
    )
    c2 = CaptureRecord(
        capture_id="c2", 
        view_id="BACK", 
        field_candidates=[
            FieldCandidate(
                field="MRP", 
                status="DETECTED", 
                normalized_value=MrpNormalized(currency="INR", amount=149.0),
                evidence_ids=["e2"]
            )
        ]
    )
    
    result = aggregate_candidates([c1, c2])
    assert len(result) == 1
    agg_mrp = result[0]
    assert agg_mrp.field == "MRP"
    assert agg_mrp.status == "DETECTED"
    assert agg_mrp.normalized_value.amount == 149.0
    assert set(agg_mrp.capture_ids) == {"c1", "c2"}
    assert set(agg_mrp.evidence_ids) == {"e1", "e2"}

def test_6_same_value_from_multiple_captures_deduplicated():
    # Same MRP ₹149 from multiple captures => deterministic deduplication
    c1 = CaptureRecord(
        capture_id="c1", 
        view_id="FRONT", 
        field_candidates=[
            FieldCandidate(
                field="MRP", 
                status="DETECTED", 
                normalized_value=MrpNormalized(currency="INR", amount=149.0),
                evidence_ids=["e1"]
            )
        ]
    )
    c2 = CaptureRecord(
        capture_id="c2", 
        view_id="BACK", 
        field_candidates=[
            FieldCandidate(
                field="MRP", 
                status="DETECTED", 
                normalized_value=MrpNormalized(currency="INR", amount=149.0),
                evidence_ids=["e2"]
            )
        ]
    )
    
    result = aggregate_candidates([c1, c2])
    assert len(result) == 1
    agg_mrp = result[0]
    assert agg_mrp.status == "DETECTED"
    assert agg_mrp.normalized_value.amount == 149.0
    assert set(agg_mrp.capture_ids) == {"c1", "c2"}
    assert set(agg_mrp.evidence_ids) == {"e1", "e2"}

def test_7_conflicting_mrp_yields_review_required():
    # conflicting MRP ₹149 / ₹159 => REVIEW_REQUIRED
    c1 = CaptureRecord(
        capture_id="c1", 
        view_id="FRONT", 
        field_candidates=[
            FieldCandidate(
                field="MRP", 
                status="DETECTED", 
                normalized_value=MrpNormalized(currency="INR", amount=149.0),
                evidence_ids=["e1"]
            )
        ]
    )
    c2 = CaptureRecord(
        capture_id="c2", 
        view_id="BACK", 
        field_candidates=[
            FieldCandidate(
                field="MRP", 
                status="DETECTED", 
                normalized_value=MrpNormalized(currency="INR", amount=159.0),
                evidence_ids=["e2"]
            )
        ]
    )
    
    result = aggregate_candidates([c1, c2])
    assert len(result) == 1
    agg_mrp = result[0]
    assert agg_mrp.status == "REVIEW_REQUIRED"
    assert set(agg_mrp.capture_ids) == {"c1", "c2"}
    assert set(agg_mrp.evidence_ids) == {"e1", "e2"}

def test_8_conflicting_net_quantity_yields_review_required():
    c1 = CaptureRecord(
        capture_id="c1", 
        view_id="FRONT", 
        field_candidates=[
            FieldCandidate(
                field="NET_QUANTITY", 
                status="DETECTED", 
                normalized_value=NetQuantityNormalized(value=500.0, unit="g"),
                evidence_ids=["e1"]
            )
        ]
    )
    c2 = CaptureRecord(
        capture_id="c2", 
        view_id="BACK", 
        field_candidates=[
            FieldCandidate(
                field="NET_QUANTITY", 
                status="DETECTED", 
                normalized_value=NetQuantityNormalized(value=1.0, unit="kg"),
                evidence_ids=["e2"]
            )
        ]
    )
    
    result = aggregate_candidates([c1, c2])
    assert len(result) == 1
    agg_nq = result[0]
    assert agg_nq.status == "REVIEW_REQUIRED"

def test_9_10_capture_and_evidence_ids_preserved():
    c1 = CaptureRecord(
        capture_id="c1", 
        view_id="FRONT", 
        field_candidates=[
            FieldCandidate(
                field="MRP", 
                status="DETECTED", 
                normalized_value=MrpNormalized(currency="INR", amount=149.0),
                evidence_ids=["e1"]
            )
        ]
    )
    c2 = CaptureRecord(
        capture_id="c2", 
        view_id="BACK", 
        field_candidates=[
            FieldCandidate(field="MRP", status="NOT_DETECTED", evidence_ids=["e2"])
        ]
    )
    c3 = CaptureRecord(
        capture_id="c3", 
        view_id="SIDE", 
        field_candidates=[
            FieldCandidate(field="MRP", status="NOT_DETECTED", evidence_ids=["e3"])
        ]
    )
    
    result = aggregate_candidates([c1, c2, c3])
    assert len(result) == 1
    agg = result[0]
    assert agg.status == "DETECTED"
    assert set(agg.capture_ids) == {"c1", "c2", "c3"}
    assert set(agg.evidence_ids) == {"e1", "e2", "e3"}

def test_12_confidence_alone_never_resolves_conflict():
    c1 = CaptureRecord(
        capture_id="c1", 
        view_id="FRONT", 
        field_candidates=[
            FieldCandidate(
                field="MRP", 
                status="DETECTED", 
                normalized_value=MrpNormalized(currency="INR", amount=149.0),
                evidence_ids=["e1"],
                confidence=0.99
            )
        ]
    )
    c2 = CaptureRecord(
        capture_id="c2", 
        view_id="BACK", 
        field_candidates=[
            FieldCandidate(
                field="MRP", 
                status="DETECTED", 
                normalized_value=MrpNormalized(currency="INR", amount=159.0),
                evidence_ids=["e2"],
                confidence=0.10
            )
        ]
    )
    
    result = aggregate_candidates([c1, c2])
    # Even though c1 confidence is 0.99 and c2 is 0.10, they conflict -> REVIEW_REQUIRED
    assert result[0].status == "REVIEW_REQUIRED"

def test_13_reversing_capture_order_produces_same_aggregation_result():
    c1 = CaptureRecord(
        capture_id="c1", 
        view_id="FRONT", 
        field_candidates=[
            FieldCandidate(field="MRP", status="NOT_DETECTED", evidence_ids=["e1"])
        ]
    )
    c2 = CaptureRecord(
        capture_id="c2", 
        view_id="BACK", 
        field_candidates=[
            FieldCandidate(
                field="MRP", 
                status="DETECTED", 
                normalized_value=MrpNormalized(currency="INR", amount=149.0),
                evidence_ids=["e2"]
            )
        ]
    )
    
    result_forward = aggregate_candidates([c1, c2])
    result_backward = aggregate_candidates([c2, c1])
    
    assert result_forward[0].status == result_backward[0].status == "DETECTED"
    assert result_forward[0].evidence_ids == result_backward[0].evidence_ids
    assert result_forward[0].capture_ids == result_backward[0].capture_ids
    assert result_forward[0].normalized_value.amount == result_backward[0].normalized_value.amount
