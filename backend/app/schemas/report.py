from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class OverallDisposition(str, Enum):
    VIOLATIONS_FOUND = "VIOLATIONS_FOUND"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE = "NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE"
    INCOMPLETE_INSPECTION = "INCOMPLETE_INSPECTION"

class ReportMetadata(BaseModel):
    report_id: str = Field(..., description="Unique immutable UUID identifier for this report snapshot")
    inspection_id: str = Field(..., description="Session identifier of the inspection")
    report_schema_version: str = Field("1.0", description="Schema version of the inspection report")
    generated_at: str = Field(..., description="ISO 8601 UTC timestamp when the report snapshot was generated")
    reference_date: str = Field(..., description="Statutory reference date used for legal evaluation (YYYY-MM-DD)")
    product_category: str = Field(..., description="Explicit product category provided by the inspector")
    capture_plan_id: str = Field(..., description="ID of the capture plan used during inspection")
    capture_plan_name: Optional[str] = Field(None, description="Human-readable capture plan name")

class CaptureViewSummary(BaseModel):
    view_id: str = Field(..., description="View identifier (e.g. FRONT, BACK)")
    display_name: str = Field(..., description="Human-readable display name")
    required: bool = Field(..., description="Whether this view is required for completeness")
    captured: bool = Field(..., description="Whether this view was captured")
    capture_id: Optional[str] = Field(None, description="Capture ID of the accepted image for this view")
    quality_status: Optional[str] = Field(None, description="Quality evaluation status (e.g. ACCEPTABLE, RETAKE_RECOMMENDED)")
    reasons: List[str] = Field(default_factory=list, description="Quality reasons or warnings")
    image_sha256: Optional[str] = Field(None, description="SHA-256 hash of the captured image")

class CaptureSummary(BaseModel):
    views: List[CaptureViewSummary] = Field(default_factory=list, description="Summary of each view in the capture plan")
    total_views_required: int = Field(..., description="Count of required views")
    captured_required_count: int = Field(..., description="Count of required views successfully captured")
    missing_required_views: List[str] = Field(default_factory=list, description="List of required view IDs not yet captured")
    capture_status: str = Field(..., description="COMPLETE_EVIDENCE_CAPTURE or INCOMPLETE_INSPECTION")
    evidence_sufficiency: str = Field(..., description="SUFFICIENT_FOR_ABSENCE_EVALUATION or INSUFFICIENT_FOR_ABSENCE_EVALUATION")
    overall_quality_status: str = Field(..., description="Overall capture quality (ACCEPTABLE or RETAKE_RECOMMENDED)")

class DeclarationFindingItem(BaseModel):
    rule_id: str = Field(..., description="Statutory rule identifier")
    field: str = Field(..., description="Standard declaration field name")
    status: str = Field(..., description="Legal evaluation status: PASS, FAIL, REVIEW_REQUIRED, NOT_APPLICABLE")
    reason: str = Field(..., description="Defensible legal explanation of the result")
    legal_reference: str = Field(..., description="Statutory source reference (e.g. Legal Metrology Rules, 2011 Rule 6)")
    applicability_status: str = Field(..., description="Applicability status (APPLICABLE, NOT_APPLICABLE, REVIEW_REQUIRED)")
    applicability_reason: Optional[str] = Field(None, description="Reason for applicability decision")
    evaluated_value: Any = Field(None, description="Deterministic value or values evaluated for this finding")
    evidence_ids: List[str] = Field(default_factory=list, description="Contributing OCR evidence IDs")
    capture_ids: List[str] = Field(default_factory=list, description="Contributing capture IDs")

class VisualComplianceFindingItem(BaseModel):
    rule_id: str = Field(..., description="Visual rule identifier (Rule 7, Rule 8, Rule 9)")
    field: Optional[str] = Field(None, description="Associated declaration field if applicable")
    capability: str = Field(..., description="AUTOMATABLE, INSPECTOR_REVIEW_ONLY, NOT_EVALUABLE_FROM_CURRENT_CAPTURE")
    status: str = Field(..., description="Visual assessment status: OBSERVATION_CLEAR, REVIEW_REQUIRED, NEEDS_RECAPTURE, NOT_EVALUABLE")
    reason: str = Field(..., description="Objective visual observation rationale")
    legal_reference: str = Field(..., description="Statutory rule reference")
    limitations: str = Field(..., description="Technical and statutory limitation disclosures")
    evidence_ids: List[str] = Field(default_factory=list, description="Supporting evidence IDs")
    capture_ids: List[str] = Field(default_factory=list, description="Supporting capture IDs")
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Measured image-relative evidence; never a physical-unit inference",
    )

class ReportEvidenceAsset(BaseModel):
    capture_id: str = Field(..., description="Unique capture identifier")
    view_id: str = Field(..., description="View role e.g. FRONT, BACK")
    image_sha256: str = Field(..., description="Immutable SHA-256 hash of the original captured image")
    media_type: str = Field("image/jpeg", description="MIME type of the source image")
    image_width: Optional[int] = Field(None, description="Original image width in pixels")
    image_height: Optional[int] = Field(None, description="Original image height in pixels")
    evidence_ids: List[str] = Field(default_factory=list, description="Evidence IDs associated with this capture")
    image_b64: Optional[str] = Field(None, description="Base64-encoded original capture image bytes for self-contained report snapshot immutability")

class ExtractedEvidenceItem(BaseModel):
    field: str = Field(..., description="Declaration field identifier")
    status: str = Field(..., description="Extraction status: DETECTED, REVIEW_REQUIRED, NOT_DETECTED")
    raw_value: Optional[str] = Field(None, description="Raw OCR detected text string")
    normalized_value: Optional[Dict[str, Any]] = Field(None, description="Normalized structured data representation")
    confidence: Optional[float] = Field(None, description="OCR confidence score [0.0 - 1.0]")
    evidence_ids: List[str] = Field(default_factory=list, description="Associated evidence IDs")
    capture_ids: List[str] = Field(default_factory=list, description="Contributing capture IDs")
    view_ids: List[str] = Field(default_factory=list, description="Contributing view IDs")
    has_geometry: bool = Field(False, description="Whether visual bounding coordinates are available")
    pixel_box: Optional[Dict[str, float]] = Field(None, description="Pixel bounding box if available")
    normalized_box: Optional[Dict[str, float]] = Field(None, description="Normalized bounding box [0.0 - 1.0] if available")
    polygons: List[List[List[float]]] = Field(default_factory=list, description="Polygon vertices [[x, y], ...] if available")

class InspectorContextSnapshot(BaseModel):
    product_origin: str = Field(..., description="Explicit product origin (DOMESTIC, IMPORTED, UNKNOWN)")
    regulatory_product_class: str = Field(..., description="Explicit product class (FOOD, NON_FOOD, UNKNOWN)")
    date_regulatory_regime: str = Field(..., description="Date regime (GENERAL, FOOD, CERTIFIED_SEED, COSMETIC, UNKNOWN)")
    date_package_exemption: str = Field(..., description="Date exemption (NONE, BIDI_OR_INCENSE, PSU_DOMESTIC_LPG_14_2_OR_5KG, UNKNOWN)")
    is_electronic: str = Field(..., description="Electronic status (ELECTRONIC, NON_ELECTRONIC, UNKNOWN)")
    package_structure: str = Field(..., description="Package structure (SINGLE, COMBINATION, GROUP, MULTI_PIECE, UNKNOWN)")
    alcohol_context: str = Field(..., description="Alcohol context (ALCOHOLIC, NON_ALCOHOLIC, UNKNOWN)")

class ReportSummaryCounts(BaseModel):
    total_statutory_checks: int = Field(..., description="Total statutory declaration rules evaluated")
    statutory_pass_count: int = Field(..., description="Count of PASS statutory checks")
    statutory_fail_count: int = Field(..., description="Count of FAIL statutory checks")
    statutory_review_required_count: int = Field(..., description="Count of REVIEW_REQUIRED statutory checks")
    statutory_not_applicable_count: int = Field(..., description="Count of NOT_APPLICABLE statutory checks")
    total_visual_checks: int = Field(..., description="Total visual compliance checks evaluated")
    visual_review_required_count: int = Field(..., description="Count of visual checks requiring inspector review")
    visual_not_evaluable_count: int = Field(..., description="Count of visual checks not evaluable from 2D photos")
    visual_observation_clear_count: int = Field(..., description="Count of visual checks with clear observation")

class InspectionReportSnapshot(BaseModel):
    metadata: ReportMetadata = Field(..., description="Immutable report metadata")
    overall_disposition: OverallDisposition = Field(..., description="Conservative overall legal disposition")
    disposition_reason: str = Field(..., description="Comprehensive explanation of the overall disposition")
    summary_counts: ReportSummaryCounts = Field(..., description="Granular categorical counts (no arbitrary compliance score)")
    inspector_context: InspectorContextSnapshot = Field(..., description="Snapshot of explicit inspector context answers")
    capture_summary: CaptureSummary = Field(..., description="Summary of multi-view capture completeness and quality")
    declaration_findings: List[DeclarationFindingItem] = Field(default_factory=list, description="Statutory declaration findings")
    food_label_findings: List[DeclarationFindingItem] = Field(default_factory=list, description="FSSAI statutory food labelling findings")
    visual_compliance_findings: List[VisualComplianceFindingItem] = Field(default_factory=list, description="Visual compliance boundary findings")
    extracted_evidence: List[ExtractedEvidenceItem] = Field(default_factory=list, description="Extracted OCR declarations with provenance")
    evidence_assets: List[ReportEvidenceAsset] = Field(default_factory=list, description="Immutable evidence assets associated with captures")
