from enum import Enum
from typing import List
from pydantic import BaseModel, Field

class ApplicabilityStatus(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"

class ApplicabilityDecision(BaseModel):
    rule_id: str
    status: ApplicabilityStatus
    reason: str
    evidence_used: List[str] = Field(default_factory=list)
    missing_context: List[str] = Field(default_factory=list, description="List of context enum fields missing")
