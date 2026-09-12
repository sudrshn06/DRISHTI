"""Canonical provenance and hashing for deterministic inspection results."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from app.schemas.inspection import CaptureRecord, InspectionSession
from app.schemas.ocr import FieldCandidate
from app.schemas.reproducibility import (
    CaptureProcessingProvenance,
    InspectionReproducibilityRecord,
    ReproducibleCaptureInput,
)
from app.services.ocr_engine import OCR_PREPROCESSING_CONFIG_ID, get_ocr_engine_version
from app.services.rule_engine import get_applicable_rules
from app.services.rule_loader import load_production_rules


DETERMINISTIC_EVALUATION_ALGORITHM = "drishti-deterministic-evaluation-v1"


def default_capture_processing_provenance() -> CaptureProcessingProvenance:
    return CaptureProcessingProvenance(
        ocr_engine="PADDLEOCR",
        ocr_engine_version=get_ocr_engine_version(),
        preprocessing_config_id=OCR_PREPROCESSING_CONFIG_ID,
    )


def deterministic_candidates_for_capture(capture: CaptureRecord) -> list[FieldCandidate]:
    """Return persisted OCR candidates, with a conservative legacy fallback."""
    if capture.deterministic_field_candidates is not None:
        return [candidate.model_copy(deep=True) for candidate in capture.deterministic_field_candidates]

    # Legacy captures predate the separate deterministic stream. Preserve direct
    # OCR candidates, and recover only explicit Paddle evidence from hybrid rows.
    recovered: list[FieldCandidate] = []
    for candidate in capture.field_candidates:
        if candidate.observation_layer != "RECONCILED":
            recovered.append(candidate.model_copy(deep=True))
            continue
        for evidence in candidate.provider_evidence:
            if evidence.provider != "PADDLEOCR":
                continue
            status = "DETECTED" if evidence.normalized_value is not None else "REVIEW_REQUIRED"
            recovered.append(FieldCandidate.model_validate({
                "field": candidate.field,
                "status": status,
                "raw_value": evidence.raw_text,
                "normalized_value": evidence.normalized_value,
                "evidence_ids": evidence.evidence_ids,
                "capture_ids": [capture.capture_id],
                "confidence": evidence.confidence,
                "observation_layer": "OCR_OBSERVED",
                "extraction_method": "PADDLEOCR",
                "observation_sources": ["PADDLEOCR"],
            }))
    return recovered


def _canonical_declaration(candidate: FieldCandidate) -> dict[str, Any]:
    value = candidate.normalized_value
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in value]
    return {
        "field": candidate.field,
        "status": candidate.status,
        "normalized_value": value,
    }


def _canonical_rule_result(result: Any, *, family: str) -> dict[str, Any]:
    dumped = result.model_dump(mode="json") if hasattr(result, "model_dump") else dict(result)
    return {
        "family": family,
        "rule_id": dumped.get("rule_id"),
        "rule_version": dumped.get("rule_version"),
        "field": dumped.get("field"),
        "status": dumped.get("status"),
        "reason": dumped.get("reason"),
        "evaluated_value": dumped.get("evaluated_value"),
        "source_reference": dumped.get("source_reference") or dumped.get("legal_reference"),
    }


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_reproducibility_record(session: InspectionSession) -> InspectionReproducibilityRecord:
    captures: list[ReproducibleCaptureInput] = []
    for capture in session.captures:
        provenance = capture.processing_provenance or CaptureProcessingProvenance()
        declarations = sorted(
            (_canonical_declaration(candidate) for candidate in deterministic_candidates_for_capture(capture)),
            key=_json_key,
        )
        captures.append(ReproducibleCaptureInput(
            image_sha256=capture.image_sha256 or "",
            surface_view=capture.view_id,
            ocr_engine=provenance.ocr_engine,
            ocr_engine_version=provenance.ocr_engine_version,
            preprocessing_config_id=provenance.preprocessing_config_id,
            normalized_declarations=declarations,
        ))
    captures.sort(key=lambda item: _json_key(item.model_dump(mode="json")))

    rule_results = []
    for family, results in (
        ("LEGAL_METROLOGY", session.rule_evaluations or []),
        ("FSSAI", session.food_label_evaluations or []),
        ("VISUAL", session.visual_rule_evaluations or []),
    ):
        rule_results.extend(_canonical_rule_result(result, family=family) for result in results)
    rule_results.sort(key=_json_key)

    rule_identity = sorted({
        (item["family"], item["rule_id"], item["rule_version"] or "UNVERSIONED")
        for item in rule_results
    })
    active_rule_definitions = [
        rule.model_dump(mode="json")
        for rule in get_applicable_rules(
            load_production_rules(),
            date.fromisoformat(session.reference_date),
        )
    ]
    active_rule_definitions.sort(key=_json_key)
    ruleset_manifest = {
        "evaluation_algorithm": DETERMINISTIC_EVALUATION_ALGORITHM,
        "legal_metrology_rule_definitions": active_rule_definitions,
        "evaluated_rule_versions": rule_identity,
    }
    ruleset_identifier = hashlib.sha256(
        _json_key(ruleset_manifest).encode("utf-8")
    ).hexdigest()

    context = {
        "product_category": session.product_category,
        "product_origin": session.product_origin,
        "regulatory_product_class": session.regulatory_product_class,
        "date_regulatory_regime": session.date_regulatory_regime,
        "date_package_exemption": session.date_package_exemption,
        "is_electronic": session.is_electronic,
        "package_structure": session.package_structure,
        "alcohol_context": session.alcohol_context,
        "capture_plan_id": session.capture_plan_id,
        "capture_status": session.capture_status,
        "evidence_sufficiency": session.evidence_sufficiency,
    }
    payload = {
        "evaluation_algorithm": DETERMINISTIC_EVALUATION_ALGORITHM,
        "ruleset_identifier": ruleset_identifier,
        "reference_date": session.reference_date,
        "confirmed_package_context": context,
        "captures": [capture.model_dump(mode="json") for capture in captures],
        "deterministic_rule_results": rule_results,
    }
    fingerprint = hashlib.sha256(_json_key(payload).encode("utf-8")).hexdigest()
    return InspectionReproducibilityRecord(**payload, result_fingerprint=fingerprint)
