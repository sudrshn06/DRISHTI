from app.schemas.ocr import OcrLine
from app.services.candidate_extractor import extract_candidates
from app.services.inspection_service import aggregate_candidates
import json
from pydantic.json import pydantic_encoder

front_lines = [
    OcrLine(text="500 g", confidence=0.99, polygon=[[0,0],[1,0],[1,1],[0,1]]),
]

back_lines = [
    OcrLine(text="Net Weight: 500 g", confidence=0.99, polygon=[[0,0],[1,0],[1,1],[0,1]]),
    OcrLine(text="MRP ₹110.00", confidence=0.99, polygon=[[0,0],[1,0],[1,1],[0,1]]),
    OcrLine(text="Marketed By: TATA CONSUMER PRODUCTS LIMITED", confidence=0.99, polygon=[[0,0],[1,0],[1,1],[0,1]]),
    OcrLine(text="contact us at support@tataconsumer.com", confidence=0.99, polygon=[[0,0],[1,0],[1,1],[0,1]]),
    OcrLine(text="INTO AN AIRTIGHT CONTAINER. OTHER", confidence=0.99, polygon=[[0,0],[1,0],[1,1],[0,1]]),
    OcrLine(text="Packed On: 15/05/2024", confidence=0.99, polygon=[[0,0],[1,0],[1,1],[0,1]]),
    OcrLine(text="Use By: 14/05/2025", confidence=0.99, polygon=[[0,0],[1,0],[1,1],[0,1]]),
    OcrLine(text="THE FINEST FARMS AND PACKED", confidence=0.99, polygon=[[0,0],[1,0],[1,1],[0,1]]),
]

front_candidates = extract_candidates(front_lines, {})
back_candidates = extract_candidates(back_lines, {})

print("FRONT CANDIDATES:")
for c in front_candidates:
    print(f"- {c.field}: {c.status} | raw: {c.raw_value} | norm: {c.normalized_value}")

print("\nBACK CANDIDATES:")
for c in back_candidates:
    print(f"- {c.field}: {c.status} | raw: {c.raw_value} | norm: {c.normalized_value}")

print("\nAGGREGATED CANDIDATES:")
from app.schemas.inspection import CaptureRecord
captures = [
    CaptureRecord(capture_id="c1", view_id="FRONT", image_sha256="s1", evidence_id="e1", status="ACCEPTABLE", field_candidates=front_candidates),
    CaptureRecord(capture_id="c2", view_id="BACK", image_sha256="s2", evidence_id="e2", status="ACCEPTABLE", field_candidates=back_candidates),
]
agg = aggregate_candidates(captures)
for c in agg:
    print(f"- {c.field}: {c.status} | raw: {c.raw_value} | norm: {c.normalized_value} | captures: {c.capture_ids}")
