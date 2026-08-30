"""Durable officer review and declaration-correction contracts.

These records are intentionally separate from machine observations. Only an
authenticated officer action can create them, and they cannot represent legal
absence or a compliance verdict.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.ocr import FieldCandidate


class PackageInformationReview(BaseModel):
    reviewed_by_user_id: str
    reviewed_by_username: str
    reviewed_at: datetime
    # Used server-side to invalidate stale confirmations. It is deliberately
    # omitted from API serialization because it is not officer-facing data.
    basis_fingerprint: str = Field(exclude=True)


class OfficerDeclarationOverride(BaseModel):
    override_id: str
    target_key: str
    field: str
    observed_candidate: FieldCandidate
    confirmed_candidate: FieldCandidate
    supporting_capture_id: str
    reason: str
    officer_user_id: str
    officer_username: str
    confirmed_at: datetime
    source: Literal["OFFICER_CONFIRMED"] = "OFFICER_CONFIRMED"

    @field_validator("confirmed_candidate")
    @classmethod
    def confirmed_candidate_cannot_create_absence_or_ai_authority(
        cls,
        candidate: FieldCandidate,
    ) -> FieldCandidate:
        if candidate.status != "DETECTED":
            raise ValueError("Officer corrections must confirm a visible declaration")
        if candidate.observation_layer != "OFFICER_CONFIRMED":
            raise ValueError("Officer correction must use the officer-confirmed boundary")
        if candidate.extraction_method != "OFFICER_CONFIRMED":
            raise ValueError("Machine observations cannot create officer corrections")
        return candidate


class DeclarationCorrectionRequest(BaseModel):
    candidate_index: int = Field(..., ge=0)
    field: str
    confirmed_value: str = Field(..., min_length=1, max_length=4000)
    reason: str = Field(..., min_length=3, max_length=1000)
    supporting_capture_id: str
    declaration_role: Optional[Literal[
        "MANUFACTURER", "PACKER", "IMPORTER", "MARKETER", "UNKNOWN"
    ]] = None
    date_type: Optional[Literal[
        "MANUFACTURED", "PACKED", "IMPORTED", "USE_BY", "EXPIRY",
        "BEST_BEFORE", "UNKNOWN"
    ]] = None

    @field_validator("confirmed_value", "reason")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("A visible value and reason are required")
        return cleaned

