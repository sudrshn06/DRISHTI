import pytest
from app.schemas.ocr import NetQuantityNormalized, OcrLine
from app.services.candidate_extractor import extract_candidates

def make_line(text):
    return OcrLine(
        text=text,
        confidence=0.99,
        polygon=[[0, 0], [1, 0], [1, 1], [0, 1]]
    )


def test_net_quantity_ignores_nutrition():
    lines = [
        make_line("NUTRITION FACTS"),
        make_line("Protein 0g"),
        make_line("Sodium 65mg"),
        make_line("Total Fat 0g")
    ]
    candidates = extract_candidates(lines, {})
    nq_cands = [c for c in candidates if c.field == "NET_QUANTITY"]
    assert len(nq_cands) == 1
    assert nq_cands[0].status == "NOT_DETECTED"

def test_net_quantity_heading_next_line():
    lines = [
        make_line("NET QUANTITY"),
        make_line("500 ml")
    ]
    candidates = extract_candidates(lines, {})
    nq_cands = [c for c in candidates if c.field == "NET_QUANTITY"]
    assert len(nq_cands) == 1
    assert nq_cands[0].status == "DETECTED"
    assert isinstance(nq_cands[0].normalized_value, NetQuantityNormalized)
    assert nq_cands[0].normalized_value.value == 500
    assert nq_cands[0].normalized_value.unit == "ml"

def test_net_quantity_same_line():
    lines = [
        make_line("NET QUANTITY: 750 g")
    ]
    candidates = extract_candidates(lines, {})
    nq_cands = [c for c in candidates if c.field == "NET_QUANTITY"]
    assert len(nq_cands) == 1
    assert nq_cands[0].status == "DETECTED"
    assert isinstance(nq_cands[0].normalized_value, NetQuantityNormalized)
    assert nq_cands[0].normalized_value.value == 750
    assert nq_cands[0].normalized_value.unit == "g"
