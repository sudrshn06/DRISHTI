from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.inspection import ClarificationQuestion

class InspectionLifecycleStatus(str, Enum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    FINALIZED = "FINALIZED"

class WorkflowSummary(BaseModel):
    inspection_id: str = Field(..., description="Unique identifier for the inspection session")
    lifecycle_status: str = Field(..., description="DRAFT, IN_PROGRESS, READY_FOR_REVIEW, or FINALIZED")
    lifecycle_display_name: str = Field(..., description="Inspector-friendly display title for the lifecycle status")
    can_upload_capture: bool = Field(..., description="Whether new captures can be uploaded")
    can_update_context: bool = Field(..., description="Whether inspection context can be modified")
    can_finalize: bool = Field(..., description="Whether the inspection is eligible for finalization")
    active_clarification: Optional[ClarificationQuestion] = Field(None, description="Active blocking clarification question if any")
    capture_status: str = Field(..., description="INCOMPLETE_INSPECTION or COMPLETE_EVIDENCE_CAPTURE")
    evidence_sufficiency: str = Field(..., description="SUFFICIENT_FOR_ABSENCE_EVALUATION or INSUFFICIENT_FOR_ABSENCE_EVALUATION")
    statutory_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of statutory checks categorized by status (PASS, FAIL, REVIEW_REQUIRED, NOT_APPLICABLE)"
    )
    visual_review_count: int = Field(0, description="Count of visual observations requiring inspector review or not evaluable")
    has_failures: bool = Field(False, description="Whether statutory violations were detected")
    has_review_required: bool = Field(False, description="Whether any statutory or visual items require manual review")
    has_incomplete_evidence: bool = Field(False, description="Whether surface coverage or evidence is incomplete")
    report_available: bool = Field(False, description="Whether an immutable report snapshot is available for download")
