from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.history import InspectionSummaryItem

class WorkflowCounts(BaseModel):
    """Counts of inspections by operational lifecycle state."""
    model_config = ConfigDict(extra="forbid")
    
    draft: int = Field(0, description="Number of inspections in DRAFT state")
    in_progress: int = Field(0, description="Number of inspections in IN_PROGRESS state")
    ready_for_review: int = Field(0, description="Number of inspections in READY_FOR_REVIEW state")
    finalized: int = Field(0, description="Number of inspections in FINALIZED state")
    total: int = Field(0, description="Total number of inspections across all lifecycle states")

class AttentionCounts(BaseModel):
    """Categorical counts of inspections requiring inspector attention."""
    model_config = ConfigDict(extra="forbid")
    
    violations_found: int = Field(0, description="Finalized inspections with detected statutory violations")
    review_required: int = Field(0, description="Finalized inspections with visual/manual review required")
    incomplete_inspection: int = Field(0, description="Finalized inspections with incomplete surface coverage")
    total_needing_attention: int = Field(0, description="Total inspections with non-clean statutory findings")

class ReportCounts(BaseModel):
    """Counts of report generation status among finalized inspections."""
    model_config = ConfigDict(extra="forbid")
    
    finalized_with_report: int = Field(0, description="Finalized inspections with a generated report snapshot")
    finalized_without_report: int = Field(0, description="Finalized inspections without a generated report snapshot")

class AdminMetrics(BaseModel):
    """Organization-wide administrative metrics (visible only to ADMIN role)."""
    model_config = ConfigDict(extra="forbid")
    
    total_inspectors: int = Field(0, description="Total registered inspectors in system")
    total_active_inspectors: int = Field(0, description="Active registered inspectors in system")
    total_system_inspections: int = Field(0, description="Total inspections created system-wide across all inspectors")

class DashboardSummary(BaseModel):
    """Comprehensive operational dashboard summary payload."""
    model_config = ConfigDict(extra="forbid")
    
    workflow_counts: WorkflowCounts = Field(..., description="Operational lifecycle breakdown")
    attention_counts: AttentionCounts = Field(..., description="Categorical findings needing inspector attention")
    report_counts: ReportCounts = Field(..., description="Report generation metrics")
    recent_inspections: List[InspectionSummaryItem] = Field(default_factory=list, description="Latest inspections worked on (up to 5)")
    user_role: str = Field(..., description="Current user role (INSPECTOR or ADMIN)")
    user_display_name: str = Field(..., description="Display name / username of current user")
    admin_metrics: Optional[AdminMetrics] = Field(None, description="System-wide metrics for ADMIN role")
