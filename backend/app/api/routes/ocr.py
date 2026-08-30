from datetime import datetime, timezone, date
import uuid
from typing import Optional
from fastapi import APIRouter, File, UploadFile, Depends, Form
from app.core.rate_limit import check_ocr_rate_limit
from app.services.image_validator import validate_and_decode_image
from app.services.ocr_engine import analyze_image
from app.services.candidate_extractor import extract_candidates
from app.services.compliance_service import orchestrate_compliance
from app.api.deps import get_current_user
from app.models.user import UserModel
from app.schemas.ocr import OcrResponse, OcrEngineInfo, EvidenceItem

router = APIRouter()

@router.post("/analyze", response_model=OcrResponse, dependencies=[Depends(check_ocr_rate_limit)])
async def analyze_ocr(
    image: UploadFile = File(...),
    reference_date: Optional[date] = Form(None),
    product_category: Optional[str] = Form(None),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Phase 1 Minimal OCR Slice Endpoint.
    1. Validates the uploaded file.
    2. Runs PaddleOCR on it.
    3. Extracts structured candidates.
    4. Evaluates production compliance rules if date & category are provided.
    5. Returns a single-image result without claiming complete compliance.
    """
    # 1. Validation & Decoding
    decoded_image, sha256_hash = validate_and_decode_image(image)

    # 2. OCR Execution
    ocr_lines = analyze_image(decoded_image)

    # 3. Generate Request-specific Identifiers
    inspection_id = str(uuid.uuid4())
    image_id = str(uuid.uuid4())
    now_str = datetime.now(timezone.utc).isoformat()

    # 4. Map OCR lines to Evidence
    evidence_list = []
    evidence_map = {}
    for i, line in enumerate(ocr_lines):
        evidence_id = str(uuid.uuid4())
        evidence_map[str(i)] = evidence_id
        
        evidence_list.append(EvidenceItem(
            evidence_id=evidence_id,
            inspection_id=inspection_id,
            image_id=image_id,
            raw_detected_text=line.text,
            ocr_confidence=line.confidence,
            polygon=line.polygon,
            extraction_method="PADDLEOCR",
            processing_version="3.7.0",
            timestamp=now_str
        ))

    # 5. Extract Candidates
    candidates = extract_candidates(ocr_lines, evidence_map)

    # 5.5 Orchestrate Compliance (if explicit inputs provided)
    rule_evaluations = None
    if reference_date and product_category:
        rule_evaluations = orchestrate_compliance(
            candidates=candidates,
            reference_date=reference_date,
            product_category=product_category,
            inspection_complete=False  # Always false for single-image API
        )

    # 6. Construct Response
    engine_info = OcrEngineInfo(
        engine="PADDLEOCR",
        processing_version="3.7.0",
        lines=ocr_lines
    )

    return OcrResponse(
        inspection_id=inspection_id,
        image_id=image_id,
        image_sha256=sha256_hash,
        processing_status="COMPLETED",
        capture_status="INCOMPLETE_INSPECTION",
        ocr=engine_info,
        evidence=evidence_list,
        field_candidates=candidates,
        rule_evaluations=rule_evaluations
    )
