"""Public provenance records for reproducible deterministic evaluations."""

from typing import Any

from pydantic import BaseModel, Field


class CaptureProcessingProvenance(BaseModel):
    ocr_engine: str = "PADDLEOCR"
    ocr_engine_version: str = "UNKNOWN"
    preprocessing_config_id: str = "UNKNOWN"


class ReproducibleCaptureInput(BaseModel):
    image_sha256: str
    surface_view: str
    ocr_engine: str
    ocr_engine_version: str
    preprocessing_config_id: str
    normalized_declarations: list[dict[str, Any]] = Field(default_factory=list)


class InspectionReproducibilityRecord(BaseModel):
    evaluation_algorithm: str
    ruleset_identifier: str
    reference_date: str
    confirmed_package_context: dict[str, str]
    captures: list[ReproducibleCaptureInput] = Field(default_factory=list)
    deterministic_rule_results: list[dict[str, Any]] = Field(default_factory=list)
    result_fingerprint: str
