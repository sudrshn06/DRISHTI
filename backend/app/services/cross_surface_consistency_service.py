"""Deterministic cross-surface declaration consistency findings.

The consistency layer reports reliable normalized contradictions for officer
review. It does not turn disagreement into a statutory FAIL and does not alter
immutable capture observations.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from typing import Any, Iterable

from app.schemas.compliance import LegalStatus, RuleEvaluationResult
from app.schemas.inspection import CaptureRecord
from app.schemas.ocr import (
    BusinessNormalized,
    ConsumerCareNormalized,
    DateNormalized,
    FieldCandidate,
    MrpNormalized,
    NetQuantityNormalized,
)
from app.schemas.officer_review import OfficerDeclarationOverride
from app.services.reproducibility_service import deterministic_candidates_for_capture


CROSS_SURFACE_RULE_VERSION = "1.0"

_UNIT_ALIASES = {
    "mg": "mg", "mgs": "mg", "milligram": "mg", "milligrams": "mg",
    "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g",
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
    "ml": "ml", "mls": "ml", "milliliter": "ml", "milliliters": "ml",
    "millilitre": "ml", "millilitres": "ml",
    "l": "l", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "mm": "mm", "mms": "mm", "millimeter": "mm", "millimeters": "mm",
    "millimetre": "mm", "millimetres": "mm",
    "cm": "cm", "cms": "cm", "centimeter": "cm", "centimeters": "cm",
    "centimetre": "cm", "centimetres": "cm",
    "m": "m", "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "u": "unit", "n": "unit", "unit": "unit", "units": "unit",
    "number": "unit", "numbers": "unit", "piece": "unit", "pieces": "unit",
    "pc": "unit", "pcs": "unit",
}


def _text(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.split()).casefold()


def _normalized_value(candidate: FieldCandidate) -> Any:
    value = candidate.normalized_value
    if isinstance(value, MrpNormalized):
        return {"currency": value.currency.upper(), "amount": value.amount}
    if isinstance(value, NetQuantityNormalized):
        unit = value.unit.strip().casefold()
        return {"value": value.value, "unit": _UNIT_ALIASES.get(unit, unit)}
    if isinstance(value, DateNormalized):
        return value.model_dump(mode="json")
    if isinstance(value, BusinessNormalized):
        return {
            "role": value.role.upper(),
            "name": _text(value.name),
            "address": _text(value.address),
            "pin_code": value.pin_code,
        }
    if isinstance(value, ConsumerCareNormalized):
        return {
            "email": _text(value.email),
            "phone": re.sub(r"\D", "", value.phone or "") or None,
        }
    if candidate.field == "FSSAI_LICENCE":
        return re.sub(r"\D", "", str(value or candidate.raw_value or ""))
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in value]
    if isinstance(value, str):
        return _text(value)
    return value


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _group(candidate: FieldCandidate) -> tuple[str, str | None] | None:
    if candidate.field in {"MRP", "NET_QUANTITY", "CONSUMER_CARE", "FSSAI_LICENCE"}:
        return candidate.field, None
    if candidate.field == "MONTH_YEAR" and isinstance(candidate.normalized_value, DateNormalized):
        return candidate.field, candidate.normalized_value.type.upper()
    if (
        candidate.field == "MANUFACTURER_PACKER_IMPORTER"
        and isinstance(candidate.normalized_value, BusinessNormalized)
    ):
        return candidate.field, candidate.normalized_value.role.upper()
    return None


def _rule_identity(field: str, subtype: str | None) -> tuple[str, str]:
    if field == "MRP":
        return "CROSS_SURFACE_MRP_CONSISTENCY", "MRP_DECLARATION_PRESENCE"
    if field == "NET_QUANTITY":
        return "CROSS_SURFACE_NET_QUANTITY_CONSISTENCY", "NET_QUANTITY_PRESENCE"
    if field == "CONSUMER_CARE":
        return "CROSS_SURFACE_CONSUMER_CARE_CONSISTENCY", "CONSUMER_CARE_DECLARATION_PRESENCE"
    if field == "FSSAI_LICENCE":
        return "CROSS_SURFACE_FSSAI_LICENCE_CONSISTENCY", "FSSAI_LICENCE_PRESENCE"
    if field == "MONTH_YEAR":
        return f"CROSS_SURFACE_DATE_{subtype}_CONSISTENCY", "MONTH_YEAR_DECLARATION_PRESENCE"
    source = "IMPORTER_DECLARATION_PRESENCE" if subtype == "IMPORTER" else "MANUFACTURER_PACKER_DECLARATION_PRESENCE"
    return f"CROSS_SURFACE_BUSINESS_{subtype}_CONSISTENCY", source


def _target_key(field: str, subtype: str | None) -> str:
    if subtype and field in {"MONTH_YEAR", "MANUFACTURER_PACKER_IMPORTER"}:
        return f"{field}:{subtype}"
    return field


def _is_resolved_by_officer(
    field: str,
    subtype: str | None,
    overrides: Iterable[OfficerDeclarationOverride],
) -> bool:
    latest_by_target: dict[str, OfficerDeclarationOverride] = {}
    for override in overrides:
        latest_by_target[override.target_key] = override
    qualified = _target_key(field, subtype)
    return field in latest_by_target or qualified in latest_by_target


def evaluate_cross_surface_consistency(
    *,
    captures: Iterable[CaptureRecord],
    officer_overrides: Iterable[OfficerDeclarationOverride],
    legal_metrology_results: list[RuleEvaluationResult],
    food_results: list[RuleEvaluationResult],
    reference_date: date,
) -> tuple[list[RuleEvaluationResult], list[RuleEvaluationResult]]:
    """Return LMPC and FSSAI conflict findings in stable logical order."""
    observations: dict[
        tuple[str, str | None],
        list[tuple[FieldCandidate, CaptureRecord, Any]],
    ] = defaultdict(list)
    for capture in captures:
        for candidate in deterministic_candidates_for_capture(capture):
            if candidate.status != "DETECTED" or candidate.normalized_value is None:
                continue
            group = _group(candidate)
            if group:
                observations[group].append((candidate, capture, _normalized_value(candidate)))

    lm_sources = {result.rule_id: result for result in legal_metrology_results}
    food_sources = {result.rule_id: result for result in food_results}
    lm_findings: list[RuleEvaluationResult] = []
    food_findings: list[RuleEvaluationResult] = []

    for (field, subtype), items in sorted(observations.items()):
        source_views = sorted({capture.view_id for _, capture, _ in items})
        if len(source_views) < 2:
            continue
        values: dict[str, dict[str, Any]] = {}
        for candidate, capture, normalized in items:
            key = _json_key(normalized)
            entry = values.setdefault(key, {
                "normalized_value": normalized,
                "raw_values": set(),
                "source_views": set(),
            })
            if candidate.raw_value:
                entry["raw_values"].add(candidate.raw_value)
            entry["source_views"].add(capture.view_id)
        if len(values) < 2 or _is_resolved_by_officer(field, subtype, officer_overrides):
            continue

        rule_id, source_rule_id = _rule_identity(field, subtype)
        source_map = food_sources if field == "FSSAI_LICENCE" else lm_sources
        source = source_map.get(source_rule_id)
        if not source or source.status == LegalStatus.NOT_APPLICABLE:
            continue
        observed_values = [
            {
                "normalized_value": entry["normalized_value"],
                "raw_values": sorted(entry["raw_values"]),
                "source_views": sorted(entry["source_views"]),
            }
            for _, entry in sorted(values.items())
        ]
        evidence_ids = sorted({evidence for candidate, _, _ in items for evidence in candidate.evidence_ids})
        capture_ids = sorted({capture.capture_id for _, capture, _ in items})
        label = field.replace("_", " ").title()
        if subtype:
            label = f"{label} ({subtype.replace('_', ' ').title()})"
        finding = RuleEvaluationResult(
            rule_id=rule_id,
            rule_version=CROSS_SURFACE_RULE_VERSION,
            field=field,
            status=LegalStatus.REVIEW_REQUIRED,
            reason=(
                f"Reliable normalized {label} declarations conflict across captured views. "
                "The disagreement is preserved for officer review and is not automatically classified as a statutory FAIL."
            ),
            evaluated_value={
                "observed_values": observed_values,
                "source_views": source_views,
                "expected_condition": "Reliable normalized declarations should agree across captured views.",
            },
            evidence_ids=evidence_ids,
            capture_ids=capture_ids,
            reference_date=reference_date,
            source_reference=source.source_reference,
            source_url=source.source_url,
            applicability=source.applicability,
        )
        (food_findings if field == "FSSAI_LICENCE" else lm_findings).append(finding)

    return lm_findings, food_findings
