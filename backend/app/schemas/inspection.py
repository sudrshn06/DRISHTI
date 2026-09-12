from enum import Enum
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator
from app.schemas.ocr import FieldCandidate, is_authoritative_field_candidate
from app.schemas.image_quality import ImageQualityAssessment
from app.schemas.compliance import RuleEvaluationResult
from app.schemas.visual_assessment import CaptureVisualAssessmentSummary, VisualRuleEvaluationResult
from app.schemas.gemini import GeminiPackageAuditRecord, DetectedPackageContext
from app.schemas.officer_review import OfficerDeclarationOverride, PackageInformationReview
from app.schemas.reproducibility import (
    CaptureProcessingProvenance,
    InspectionReproducibilityRecord,
)

class ClarificationOption(BaseModel):
    id: str = Field(..., description="Unique option identifier")
    label: str = Field(..., description="Inspector-friendly label")
    context_updates: dict[str, str] = Field(default_factory=dict, description="Fields to update when selected")

class ClarificationQuestion(BaseModel):
    question_id: str = Field(..., description="Unique identifier for the question")
    title: str = Field(..., description="Human-friendly question text")
    description: Optional[str] = Field(None, description="Optional helpful explanation")
    options: List[ClarificationOption] = Field(default_factory=list, description="Available answers including Not Sure")
    affects_rules: List[str] = Field(default_factory=list, description="Rule IDs that this question helps resolve")

class RequiredContext(BaseModel):
    field: str = Field(..., description="The internal field name, e.g., PRODUCT_ORIGIN")
    affects_rules: List[str] = Field(..., description="List of rule IDs that require this context")

class ProductOrigin(str, Enum):
    DOMESTIC = "DOMESTIC"
    IMPORTED = "IMPORTED"
    UNKNOWN = "UNKNOWN"

class RegulatoryProductClass(str, Enum):
    FOOD = "FOOD"
    NON_FOOD = "NON_FOOD"
    UNKNOWN = "UNKNOWN"

class DateRegulatoryRegime(str, Enum):
    GENERAL = "GENERAL"
    FOOD = "FOOD"
    CERTIFIED_SEED = "CERTIFIED_SEED"
    COSMETIC = "COSMETIC"
    UNKNOWN = "UNKNOWN"

class DatePackageExemptionContext(str, Enum):
    NONE = "NONE"
    BIDI_OR_INCENSE = "BIDI_OR_INCENSE"
    PSU_DOMESTIC_LPG_14_2_OR_5KG = "PSU_DOMESTIC_LPG_14_2_OR_5KG"
    UNKNOWN = "UNKNOWN"

class CaptureViewRequirement(BaseModel):
    view_id: str = Field(..., description="Unique identifier for the view, e.g., FRONT, BACK")
    display_name: str = Field(..., description="Human-readable name for the view")
    required: bool = Field(True, description="Whether this view is required for completeness")

class CapturePlan(BaseModel):
    capture_plan_id: str = Field(..., description="Unique identifier for the capture plan")
    name: str = Field(..., description="Name of the capture plan, e.g., 'Standard Software Inspection'")
    views: List[CaptureViewRequirement] = Field(..., description="List of views in this plan")
    absence_evaluation_eligible: bool = Field(False, description="Whether this plan provides sufficient surface coverage for safe absence evaluation")

class CaptureRecord(BaseModel):
    capture_id: str = Field(..., description="Unique identifier for this specific capture")
    view_id: str = Field(..., description="The view this capture represents, e.g., FRONT")
    evidence_id: Optional[str] = Field(None, description="Identifier for the associated image/evidence")
    image_sha256: Optional[str] = Field(None, description="SHA-256 hash of the image")
    object_key: Optional[str] = Field(
        None,
        exclude=True,
        description="Server-side S3/MinIO object key; never serialized to clients",
    )
    media_type: str = Field("image/jpeg", description="Validated source image media type")
    quality_assessment: Optional[ImageQualityAssessment] = Field(None, description="Image quality results")
    visual_assessment: Optional[CaptureVisualAssessmentSummary] = Field(None, description="Visual compliance evidence assessment summary")
    field_candidates: List[FieldCandidate] = Field(default_factory=list, description="Extracted fields from this capture")
    deterministic_field_candidates: Optional[List[FieldCandidate]] = Field(
        None,
        exclude=True,
        description="Persisted OCR-only candidates used at the deterministic legal boundary",
    )
    processing_provenance: Optional[CaptureProcessingProvenance] = Field(
        None,
        description="OCR and preprocessing versions used for this capture",
    )
    ai_analysis: Optional[GeminiPackageAuditRecord] = Field(None, description="Append-only AI_OBSERVED package-reading audit record, outside compliance inputs")
    status: str = Field("ACCEPTED", description="Status of the capture, e.g., ACCEPTED, RETAKE_RECOMMENDED")
    pipeline_status: str = Field("COMPLETED", description="Status of the processing pipeline, e.g., COMPLETED, OCR_SUCCESS_NO_TEXT, FAILED")

    @field_validator("field_candidates")
    @classmethod
    def field_candidates_must_be_authoritative(cls, candidates: List[FieldCandidate]) -> List[FieldCandidate]:
        """Keep raw AI observations outside the officer-facing candidate stream."""
        if any(not is_authoritative_field_candidate(candidate) for candidate in candidates):
            raise ValueError(
                "AI_OBSERVED/Gemini candidates must remain in the dedicated AI audit boundary"
            )
        return candidates

class InspectionSession(BaseModel):
    inspection_id: str = Field(..., description="Unique identifier for the inspection session")
    reference_date: str = Field(..., description="Explicit reference date in YYYY-MM-DD format")
    product_category: str = Field(..., description="Explicit product category, e.g., ELECTRONICS")
    product_origin: str = Field("UNKNOWN", description="DOMESTIC, IMPORTED, or UNKNOWN")
    regulatory_product_class: str = Field("UNKNOWN", description="FOOD, NON_FOOD, or UNKNOWN")
    date_regulatory_regime: str = Field("UNKNOWN", description="GENERAL, FOOD, CERTIFIED_SEED, COSMETIC, or UNKNOWN")
    date_package_exemption: str = Field("UNKNOWN", description="NONE, BIDI_OR_INCENSE, PSU_DOMESTIC_LPG_14_2_OR_5KG, or UNKNOWN")
    is_electronic: str = Field("UNKNOWN", description="ELECTRONIC, NON_ELECTRONIC, or UNKNOWN")
    package_structure: str = Field("UNKNOWN", description="SINGLE, COMBINATION, GROUP, MULTI_PIECE, or UNKNOWN")
    alcohol_context: str = Field("UNKNOWN", description="ALCOHOLIC, NON_ALCOHOLIC, or UNKNOWN")
    capture_plan_id: str = Field(..., description="ID of the associated capture plan")
    capture_status: str = Field(
        "INCOMPLETE_INSPECTION", 
        description="INCOMPLETE_INSPECTION or COMPLETE_EVIDENCE_CAPTURE"
    )
    evidence_sufficiency: str = Field(
        "INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        description="SUFFICIENT_FOR_ABSENCE_EVALUATION or INSUFFICIENT_FOR_ABSENCE_EVALUATION"
    )
    captures: List[CaptureRecord] = Field(default_factory=list, description="All captures taken in this session")
    aggregated_candidates: List[FieldCandidate] = Field(default_factory=list, description="Fields aggregated across all captures")
    deterministic_aggregated_candidates: Optional[List[FieldCandidate]] = Field(
        None,
        exclude=True,
        description="OCR/officer-confirmed candidates used by deterministic legal rules",
    )
    rule_evaluations: Optional[List[RuleEvaluationResult]] = Field(None, description="Final compliance rules evaluated on aggregated fields")
    food_label_evaluations: Optional[List[RuleEvaluationResult]] = Field(default_factory=list, description="Food labelling compliance rules evaluated on aggregated fields")
    visual_rule_evaluations: Optional[List[VisualRuleEvaluationResult]] = Field(default_factory=list, description="Visual compliance evaluations for Rule 7, Rule 8, Rule 9")
    required_context: List[RequiredContext] = Field(default_factory=list, description="Context fields required to complete applicability evaluations")
    active_clarification: Optional[ClarificationQuestion] = Field(None, description="Single highest-value clarification question currently blocking rule resolution")
    dismissed_clarifications: List[str] = Field(default_factory=list, description="Question IDs explicitly dismissed by inspector selecting Not sure")
    detected_package_context: Optional[DetectedPackageContext] = Field(None, description="AI_SUGGESTED context awaiting officer confirmation or edit")
    package_information_review: Optional[PackageInformationReview] = Field(
        None,
        description="Latest durable officer confirmation of the current package information",
    )
    officer_declaration_overrides: List[OfficerDeclarationOverride] = Field(
        default_factory=list,
        description="Append-only officer-confirmed declaration correction audit records",
    )
    lifecycle_status: str = Field(
        "DRAFT",
        description="Lifecycle status: DRAFT, IN_PROGRESS, READY_FOR_REVIEW, FINALIZED"
    )
    created_by_user_id: Optional[str] = Field(None, description="User ID of the inspector who created this inspection session")
    report_snapshot: Optional[Any] = Field(None, description="Immutable snapshot of the generated inspection report")
    overall_disposition: Optional[str] = Field(None, description="Overall inspection disposition e.g. VIOLATIONS_FOUND, NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE, REVIEW_REQUIRED, INCOMPLETE_INSPECTION")
    reproducibility: Optional[InspectionReproducibilityRecord] = Field(
        None,
        description="Canonical deterministic inputs, rule outputs, and stable result fingerprint",
    )
