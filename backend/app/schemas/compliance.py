from datetime import date
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class LegalStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class RuleDefinition(BaseModel):
    rule_id: str
    rule_version: str
    title: str
    description: str
    field: str  # e.g., "NET_QUANTITY", "MANUFACTURER_PACKER_IMPORTER"
    jurisdiction: str = "IN"
    product_scope: str = "ALL"
    effective_from: date
    effective_to: Optional[date] = None
    evaluation_type: str  # "REQUIRED_DECLARATION", "ALLOWED_UNIT", "VALUE_PRESENT", etc.
    parameters: Dict[str, Any] = Field(default_factory=dict)
    source_reference: Optional[str] = None
    source_url: Optional[str] = None

class RuleEvaluationResult(BaseModel):
    rule_id: str
    rule_version: str
    field: str
    status: LegalStatus
    reason: str
    evaluated_value: Any = None
    evidence_ids: List[str] = Field(default_factory=list)
    capture_ids: List[str] = Field(default_factory=list)
    reference_date: date
    source_reference: Optional[str] = None
    source_url: Optional[str] = None
    applicability: Optional[Any] = Field(None, description="The applicability decision for this rule")
