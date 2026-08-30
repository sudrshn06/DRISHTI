from typing import Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field
from app.schemas.compliance import RuleEvaluationResult

class MrpNormalized(BaseModel):
    currency: str
    amount: float

class NetQuantityNormalized(BaseModel):
    value: float
    unit: str

class BusinessNormalized(BaseModel):
    role: str  # MANUFACTURER, PACKER, IMPORTER, MARKETER
    name: Optional[str] = None
    address: Optional[str] = None
    pin_code: Optional[str] = None
    raw_text: str

class DateNormalized(BaseModel):
    type: str
    month: Optional[int] = None
    year: Optional[int] = None
    day: Optional[int] = None
    duration: Optional[int] = None
    duration_unit: Optional[str] = None

class CountryOfOriginNormalized(BaseModel):
    declaration_type: Literal["ORIGIN", "MANUFACTURE", "ASSEMBLY"]
    country_text: str
    raw_text: str

class CommonGenericNameNormalized(BaseModel):
    name_text: str

class ConsumerCareNormalized(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None

class UnitSalePriceNormalized(BaseModel):
    amount: float
    currency: str = "INR"
    per_quantity: float
    per_unit: str

class OcrLine(BaseModel):
    text: str
    confidence: float
    polygon: List[List[float]] # [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]

class OcrEngineInfo(BaseModel):
    engine: str = "PADDLEOCR"
    processing_version: str = "3.7.0"
    lines: List[OcrLine]

class EvidenceItem(BaseModel):
    evidence_id: str
    inspection_id: str
    image_id: str
    raw_detected_text: str
    ocr_confidence: float
    polygon: List[List[float]]
    extraction_method: str = "PADDLEOCR"
    processing_version: str = "3.7.0"
    timestamp: str


class ProviderEvidence(BaseModel):
    """Auditable provider evidence retained by Stage 2C reconciliation."""

    provider: Literal["PADDLEOCR", "GOOGLE_GEMINI"]
    raw_text: Optional[str] = None
    normalized_value: Optional[Any] = None
    evidence_ids: List[str] = Field(default_factory=list)
    capture_id: Optional[str] = None
    view_id: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    uncertain: bool = False
    contradiction: bool = False
    evidence_note: Optional[str] = None

class FieldCandidate(BaseModel):
    field: str
    status: str # "DETECTED", "NOT_DETECTED", "REVIEW_REQUIRED"
    raw_value: Optional[str] = None
    normalized_value: Optional[Union[
        MrpNormalized,
        NetQuantityNormalized,
        BusinessNormalized,
        DateNormalized,
        List[DateNormalized],
        ConsumerCareNormalized,
        CountryOfOriginNormalized,
        CommonGenericNameNormalized,
        UnitSalePriceNormalized,
        str
    ]] = None
    evidence_ids: List[str] = Field(default_factory=list)
    capture_ids: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    observation_layer: Literal[
        "OCR_OBSERVED", "AI_OBSERVED", "RECONCILED", "AGGREGATED", "OFFICER_CONFIRMED"
    ] = "OCR_OBSERVED"
    extraction_method: str = "PADDLEOCR"
    observation_sources: List[str] = Field(default_factory=list)
    reconciliation_reason: Optional[Literal[
        "AGREEMENT",
        "OCR_SUPPORTED_GEMINI_CONTEXT",
        "GEMINI_EXPLICIT_EVIDENCE",
        "PROVIDER_CONFLICT",
        "UNSUPPORTED_INFERENCE",
        "INSUFFICIENT_EVIDENCE",
    ]] = None
    provider_evidence: List[ProviderEvidence] = Field(default_factory=list)


def is_authoritative_field_candidate(candidate: FieldCandidate) -> bool:
    """Return whether a candidate is allowed into the legal aggregation path.

    Stage 1 Gemini output is advisory and is stored in its dedicated audit
    schema. This check is intentionally based on every provenance marker so a
    mislabeled AI candidate cannot enter compliance processing accidentally.
    """
    sources = {source.upper() for source in candidate.observation_sources}
    if candidate.observation_layer == "RECONCILED":
        return (
            candidate.extraction_method.upper() == "HYBRID_RECONCILIATION"
            and candidate.reconciliation_reason
            not in {"UNSUPPORTED_INFERENCE", "INSUFFICIENT_EVIDENCE", None}
            and bool(candidate.provider_evidence)
        )
    return (
        candidate.observation_layer != "AI_OBSERVED"
        and candidate.extraction_method.upper() != "GEMINI"
        and "GEMINI" not in sources
    )

class OcrResponse(BaseModel):
    inspection_id: str
    image_id: str
    image_sha256: str
    processing_status: str = "COMPLETED"
    capture_status: str = "INCOMPLETE_INSPECTION"
    ocr: OcrEngineInfo
    evidence: List[EvidenceItem]
    field_candidates: List[FieldCandidate]
    rule_evaluations: Optional[List[RuleEvaluationResult]] = None

class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None

class ErrorResponse(BaseModel):
    error: ErrorDetail
