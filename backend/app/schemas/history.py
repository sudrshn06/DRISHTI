from typing import List, Optional
from pydantic import BaseModel, Field

LIFECYCLE_DISPLAY_NAMES = {
    "DRAFT": "New inspection",
    "IN_PROGRESS": "Inspection in progress",
    "READY_FOR_REVIEW": "Ready for review",
    "FINALIZED": "Inspection finalized"
}

DISPOSITION_DISPLAY_NAMES = {
    "VIOLATIONS_FOUND": "Violations Detected",
    "REVIEW_REQUIRED": "Review Required",
    "NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE": "No Violations Detected",
    "INCOMPLETE_INSPECTION": "Incomplete Inspection"
}

class InspectionSummaryItem(BaseModel):
    """
    Lightweight metadata summary for an inspection session.
    Omits large OCR payloads, evidence bounding boxes, and base64 images.
    """
    inspection_id: str = Field(..., description="Unique UUID for the inspection session")
    lifecycle_status: str = Field(..., description="DRAFT, IN_PROGRESS, READY_FOR_REVIEW, or FINALIZED")
    lifecycle_display_name: str = Field(..., description="Human-readable title for the lifecycle state")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    updated_at: str = Field(..., description="ISO 8601 last update timestamp")
    capture_count: int = Field(0, description="Total number of package surface captures")
    overall_disposition: Optional[str] = Field(None, description="Overall legal disposition if evaluated or finalized")
    disposition_display_name: Optional[str] = Field(None, description="Human-readable title for the disposition")
    has_report: bool = Field(False, description="Whether an immutable report snapshot exists")
    reference_date: str = Field(..., description="Statutory reference date (YYYY-MM-DD)")
    product_category: str = Field(..., description="Product category description")
    created_by_user_id: Optional[str] = Field(None, description="User ID of the creating inspector")
    created_by_username: Optional[str] = Field(None, description="Username of the creating inspector")

class PaginatedInspectionHistory(BaseModel):
    """
    Paginated collection of inspection summary items with metadata.
    """
    items: List[InspectionSummaryItem] = Field(default_factory=list, description="List of inspection summaries for the requested page")
    page: int = Field(..., description="1-indexed current page number")
    page_size: int = Field(..., description="Number of items per page")
    total: int = Field(..., description="Total count of matching inspections")
    total_pages: int = Field(..., description="Total number of available pages")
