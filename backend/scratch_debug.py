from app.schemas.ocr import BusinessNormalized, FieldCandidate
from app.services.inspection_service import aggregate_candidates, CaptureRecord

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
print("biz.status =", biz.status)
print("biz.normalized_value =", biz.normalized_value)
