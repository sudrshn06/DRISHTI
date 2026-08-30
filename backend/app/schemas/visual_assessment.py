from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

class NormalizedBoundingBox(BaseModel):
    x_min: float = Field(..., ge=0.0, le=1.0, description="Normalized minimum X coordinate [0.0, 1.0]")
    y_min: float = Field(..., ge=0.0, le=1.0, description="Normalized minimum Y coordinate [0.0, 1.0]")
    x_max: float = Field(..., ge=0.0, le=1.0, description="Normalized maximum X coordinate [0.0, 1.0]")
    y_max: float = Field(..., ge=0.0, le=1.0, description="Normalized maximum Y coordinate [0.0, 1.0]")

class PixelBoundingBox(BaseModel):
    x_min: float = Field(..., description="Minimum X coordinate in pixels")
    y_min: float = Field(..., description="Minimum Y coordinate in pixels")
    x_max: float = Field(..., description="Maximum X coordinate in pixels")
    y_max: float = Field(..., description="Maximum Y coordinate in pixels")
    width_px: float = Field(..., ge=0.0, description="Width of bounding box in pixels")
    height_px: float = Field(..., ge=0.0, description="Height of bounding box in pixels")
    area_px: float = Field(..., ge=0.0, description="Area of bounding box in square pixels")

class RegionGeometry(BaseModel):
    pixel_box: PixelBoundingBox
    normalized_box: NormalizedBoundingBox
    image_width: int = Field(..., gt=0, description="Source image width in pixels")
    image_height: int = Field(..., gt=0, description="Source image height in pixels")
    width_ratio: float = Field(..., ge=0.0, le=1.0, description="Ratio of bbox width to image width")
    height_ratio: float = Field(..., ge=0.0, le=1.0, description="Ratio of bbox height to image height")
    area_ratio: float = Field(..., ge=0.0, le=1.0, description="Ratio of bbox area to total image area")
    distance_to_edge_px: Dict[str, float] = Field(
        ..., description="Distance in pixels to top, bottom, left, and right image edges"
    )
    touches_edge: bool = Field(
        ..., description="Whether the region is within the edge margin threshold (possible clipping/framing issue)"
    )
    edge_margin_threshold_px: float = Field(
        2.0, description="Threshold in pixels used to evaluate edge contact"
    )

class TextProminenceMetrics(BaseModel):
    height_to_image_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Declaration text-region height relative to total image height"
    )
    area_to_image_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Declaration region area relative to total image area"
    )
    height_to_median_line_height_ratio: Optional[float] = Field(
        None, description="Ratio of declaration text height to median detected OCR line height in the same capture"
    )
    prominence_signal: str = Field(
        "STANDARD", description="Relative visual prominence signal: DOMINANT, STANDARD, or SUB_MEDIAN"
    )

class VisualReadabilitySignal(BaseModel):
    ocr_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="OCR recognition confidence score for the declaration region"
    )
    is_clipped: bool = Field(
        ..., description="Whether declaration text touches image boundaries, indicating incomplete photographic capture"
    )
    capture_quality_status: str = Field(
        ..., description="Quality status from capture image quality assessment (ACCEPTABLE or RETAKE_RECOMMENDED)"
    )
    technical_readability: str = Field(
        ..., description="Technical assessment: EVALUABLE, NEEDS_RECAPTURE, or REVIEW_REQUIRED"
    )
    readability_reasons: List[str] = Field(
        default_factory=list, description="Technical observations regarding framing, sharpness, or clarity"
    )

class DeclarationVisualAssessment(BaseModel):
    field: str = Field(..., description="Field/declaration type (e.g. MRP, NET_QUANTITY, CONSUMER_CARE, etc.)")
    evidence_ids: List[str] = Field(default_factory=list, description="Associated evidence IDs from OCR extraction")
    capture_id: str = Field(..., description="Identifier of the capture where this declaration appears")
    view_id: str = Field(..., description="Capture view role (e.g. FRONT, BACK)")
    raw_text: str = Field(..., description="Raw text of the declaration region")
    polygons: List[List[List[float]]] = Field(
        default_factory=list, description="All OCR polygons contributing to this declaration region"
    )
    geometry: Optional[RegionGeometry] = Field(
        None, description="Geometric metrics and bounding box in image coordinates"
    )
    prominence: Optional[TextProminenceMetrics] = Field(
        None, description="Image-relative text prominence metrics (strictly non-physical)"
    )
    readability: VisualReadabilitySignal = Field(
        ..., description="Technical readability and capture sufficiency signals"
    )
    technical_status: str = Field(
        ..., description="Technical assessment outcome: EVALUABLE, NEEDS_RECAPTURE, or REVIEW_REQUIRED"
    )
    notes: List[str] = Field(
        default_factory=list, description="Inspector-facing technical evidence notes"
    )

class VisualCheckType(str, Enum):
    READABILITY = "READABILITY"
    RELATIVE_PROMINENCE = "RELATIVE_PROMINENCE"
    CLIPPING_AND_FRAMING = "CLIPPING_AND_FRAMING"
    NET_QUANTITY_CLEARANCE = "NET_QUANTITY_CLEARANCE"
    PHYSICAL_FONT_SIZE_RULE_7 = "PHYSICAL_FONT_SIZE_RULE_7"
    CONTRAST_RULE_9 = "CONTRAST_RULE_9"
    PRINCIPAL_DISPLAY_PANEL_RULE_8 = "PRINCIPAL_DISPLAY_PANEL_RULE_8"

class VisualObservationStatus(str, Enum):
    OBSERVATION_CLEAR = "OBSERVATION_CLEAR"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NEEDS_RECAPTURE = "NEEDS_RECAPTURE"
    NOT_EVALUABLE = "NOT_EVALUABLE"

class InterferingEvidence(BaseModel):
    text: str
    confidence: float
    polygon: List[List[float]]
    evidence_id: Optional[str] = None
    intersection_area_px: Optional[float] = None

class VisualFinding(BaseModel):
    finding_id: str = Field(..., description="Unique identifier for this observation finding")
    check_type: VisualCheckType = Field(..., description="Type of visual check performed")
    field: Optional[str] = Field(None, description="Associated declaration field (e.g. NET_QUANTITY, MRP)")
    capture_id: str = Field(..., description="Identifier of the capture evaluated")
    view_id: str = Field(..., description="Capture view role (e.g. FRONT, BACK)")
    evidence_ids: List[str] = Field(default_factory=list, description="Associated evidence IDs")
    status: VisualObservationStatus = Field(..., description="Observation outcome status")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Quantitative metrics used in the observation")
    reason: str = Field(..., description="Inspector-facing explanation of the observation")
    legal_reference: Optional[str] = Field(None, description="Statutory reference (e.g. Rule 8, Rule 9(1)(a))")
    limitations: Optional[str] = Field(None, description="Explicit technical limitations statement")
    interfering_evidence: List[InterferingEvidence] = Field(
        default_factory=list, description="Details of interfering OCR text elements"
    )

class CaptureVisualAssessmentSummary(BaseModel):
    capture_id: str = Field(..., description="Unique identifier for the capture")
    view_id: str = Field(..., description="Capture view role (e.g. FRONT, BACK)")
    image_width: int = Field(..., gt=0, description="Image width in pixels")
    image_height: int = Field(..., gt=0, description="Image height in pixels")
    total_detected_lines: int = Field(0, description="Total number of OCR text lines detected in this capture")
    median_line_height_px: Optional[float] = Field(
        None, description="Median height in pixels across all detected text lines"
    )
    assessments: List[DeclarationVisualAssessment] = Field(
        default_factory=list, description="Visual assessments for all detected/reviewed declarations"
    )
    findings: List[VisualFinding] = Field(
        default_factory=list, description="Structured visual observation findings for placement, readability, and clearance"
    )
    has_clipped_declarations: bool = Field(
        False, description="Whether any declaration in this capture appears clipped by the image boundary"
    )
    overall_visual_status: str = Field(
        "EVALUABLE", description="Aggregate capture visual assessment status: EVALUABLE, NEEDS_RECAPTURE, or REVIEW_REQUIRED"
    )

class VisualCheckCapability(str, Enum):
    AUTOMATABLE = "AUTOMATABLE"
    INSPECTOR_REVIEW_ONLY = "INSPECTOR_REVIEW_ONLY"
    NOT_EVALUABLE_FROM_CURRENT_CAPTURE = "NOT_EVALUABLE_FROM_CURRENT_CAPTURE"

class VisualRuleEvaluationResult(BaseModel):
    rule_id: str = Field(..., description="Unique visual rule/check identifier, e.g. RULE_7_MINIMUM_NUMERAL_HEIGHT")
    legal_reference: str = Field(..., description="Statutory reference (e.g. Rule 7, Rule 8, Rule 9(1)(a))")
    field: Optional[str] = Field(None, description="Associated field (e.g. NET_QUANTITY, ALL_DECLARATIONS)")
    capability: VisualCheckCapability = Field(..., description="Capability classification of this visual check")
    status: str = Field(..., description="Legal evaluation status: REVIEW_REQUIRED, NOT_EVALUABLE, or NOT_APPLICABLE")
    requires_inspector_review: bool = Field(True, description="Whether this visual check requires inspector physical confirmation")
    evidence_ids: List[str] = Field(default_factory=list, description="Associated evidence IDs from OCR extraction")
    capture_ids: List[str] = Field(default_factory=list, description="Associated capture IDs contributing to this evaluation")
    supporting_visual_findings: List[str] = Field(default_factory=list, description="Finding IDs that support this evaluation")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Underlying quantitative metrics")
    reason: str = Field(..., description="Detailed explanation of the visual-to-legal decision boundary")
    limitations: str = Field(..., description="Explicit disclosure of technical and statutory measurement limitations")

