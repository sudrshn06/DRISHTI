"""Deterministic semantic validation for declarations already evaluated for presence.

Presence and validity are deliberately separate. These validators reuse the
active production rule's applicability and legal citation; they never infer a
missing declaration from a single image and never consume advisory-only AI data.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date
from typing import Callable, Iterable

from app.schemas.applicability import ApplicabilityDecision, ApplicabilityStatus
from app.schemas.compliance import LegalStatus, RuleDefinition, RuleEvaluationResult
from app.schemas.ocr import (
    BusinessNormalized,
    ConsumerCareNormalized,
    DateNormalized,
    FieldCandidate,
    MrpNormalized,
    NetQuantityNormalized,
)


VALIDITY_RULE_VERSION = "1.0"

_QUANTITY_UNITS = {
    "mg", "milligram", "milligrams",
    "g", "gm", "gms", "gram", "grams",
    "kg", "kgs", "kilogram", "kilograms",
    "ml", "mls", "milliliter", "milliliters", "millilitre", "millilitres",
    "l", "liter", "liters", "litre", "litres",
    "mm", "mms", "millimeter", "millimeters", "millimetre", "millimetres",
    "cm", "cms", "centimeter", "centimeters", "centimetre", "centimetres",
    "m", "meter", "meters", "metre", "metres",
    "u", "n", "unit", "units", "number", "numbers", "piece", "pieces", "pc", "pcs",
}
_BASE_DATE_TYPES = {"MANUFACTURED", "PACKED", "IMPORTED"}
_TERMINAL_DATE_TYPES = {"BEST_BEFORE", "USE_BY", "EXPIRY"}


def _candidate_key(candidate: FieldCandidate) -> str:
    value = candidate.normalized_value
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps({
        "field": candidate.field,
        "status": candidate.status,
        "normalized_value": value,
        "raw_value": candidate.raw_value,
        "observation_layer": candidate.observation_layer,
        "extraction_method": candidate.extraction_method,
    }, sort_keys=True, separators=(",", ":"))


def _sorted_candidates(
    candidates: Iterable[FieldCandidate],
    field: str,
    predicate: Callable[[FieldCandidate], bool] | None = None,
) -> list[FieldCandidate]:
    selected = [candidate for candidate in candidates if candidate.field == field]
    if predicate:
        selected = [candidate for candidate in selected if predicate(candidate)]
    return sorted(selected, key=_candidate_key)


def _provenance(candidates: Iterable[FieldCandidate]) -> tuple[list[str], list[str]]:
    evidence_ids = sorted({item for candidate in candidates for item in candidate.evidence_ids})
    capture_ids = sorted({item for candidate in candidates for item in candidate.capture_ids})
    return evidence_ids, capture_ids


def _result(
    *,
    rule_id: str,
    field: str,
    status: LegalStatus,
    reason: str,
    source_rule: RuleDefinition,
    decision: ApplicabilityDecision,
    reference_date: date,
    candidates: Iterable[FieldCandidate] = (),
    evaluated_value=None,
) -> RuleEvaluationResult:
    candidate_list = list(candidates)
    evidence_ids, capture_ids = _provenance(candidate_list)
    return RuleEvaluationResult(
        rule_id=rule_id,
        rule_version=VALIDITY_RULE_VERSION,
        field=field,
        status=status,
        reason=reason,
        evaluated_value=evaluated_value,
        evidence_ids=evidence_ids,
        capture_ids=capture_ids,
        reference_date=reference_date,
        source_reference=source_rule.source_reference,
        source_url=source_rule.source_url,
        applicability=decision,
    )


def _applicability_result(
    rule_id: str,
    source_rule: RuleDefinition,
    decision: ApplicabilityDecision,
    reference_date: date,
) -> RuleEvaluationResult | None:
    if decision.status == ApplicabilityStatus.APPLICABLE:
        return None
    status = (
        LegalStatus.NOT_APPLICABLE
        if decision.status == ApplicabilityStatus.NOT_APPLICABLE
        else LegalStatus.REVIEW_REQUIRED
    )
    reason = decision.reason if status == LegalStatus.NOT_APPLICABLE else f"Applicability requires review: {decision.reason}"
    return _result(
        rule_id=rule_id,
        field=source_rule.field,
        status=status,
        reason=reason,
        source_rule=source_rule,
        decision=decision,
        reference_date=reference_date,
    )


def _uncertain_or_missing(
    rule_id: str,
    source_rule: RuleDefinition,
    decision: ApplicabilityDecision,
    reference_date: date,
    candidates: list[FieldCandidate],
    reason: str,
) -> RuleEvaluationResult:
    return _result(
        rule_id=rule_id,
        field=source_rule.field,
        status=LegalStatus.REVIEW_REQUIRED,
        reason=reason,
        source_rule=source_rule,
        decision=decision,
        reference_date=reference_date,
        candidates=candidates,
    )


def _single_reliable_candidate(
    rule_id: str,
    source_rule: RuleDefinition,
    decision: ApplicabilityDecision,
    reference_date: date,
    candidates: list[FieldCandidate],
) -> tuple[FieldCandidate | None, RuleEvaluationResult | None]:
    detected = [candidate for candidate in candidates if candidate.status == "DETECTED"]
    if not detected:
        return None, _uncertain_or_missing(
            rule_id, source_rule, decision, reference_date, candidates,
            "Declaration validity cannot be determined from missing, unparsed, or uncertain evidence.",
        )
    representations = {
        json.dumps(candidate.normalized_value.model_dump(mode="json"), sort_keys=True)
        if hasattr(candidate.normalized_value, "model_dump")
        else json.dumps(candidate.normalized_value, sort_keys=True)
        for candidate in detected
    }
    if len(representations) > 1:
        return None, _uncertain_or_missing(
            rule_id, source_rule, decision, reference_date, candidates,
            "Conflicting declaration values require officer review before validity can be determined.",
        )
    return detected[0], None


def _validate_mrp(
    candidates: list[FieldCandidate],
    source_rule: RuleDefinition,
    decision: ApplicabilityDecision,
    reference_date: date,
) -> list[RuleEvaluationResult]:
    selected = _sorted_candidates(candidates, "MRP")
    detected = [candidate for candidate in selected if candidate.status == "DETECTED"]
    if not detected:
        unresolved = _uncertain_or_missing(
            "MRP_VALUE_FORMAT_VALIDITY", source_rule, decision, reference_date, selected,
            "Declaration validity cannot be determined from missing, unparsed, or uncertain evidence.",
        )
        return [unresolved, unresolved.model_copy(update={"rule_id": "MRP_TAX_WORDING_CONSISTENCY"})]

    values = [candidate.normalized_value for candidate in detected]
    reliable_raw_values = sorted({item.raw_value or "" for item in selected if item.status == "DETECTED"})
    raw = "\n".join(reliable_raw_values)
    has_retail_label = bool(re.search(r"\bM\.?R\.?P\.?\b|MAXIMUM\s+RETAIL\s+PRICE", raw, re.IGNORECASE))
    has_inr_marker = bool(re.search(r"(?:₹|\bRS\.?\b|\bINR\b)", raw, re.IGNORECASE))
    invalid_values = [value for value in values if isinstance(value, MrpNormalized) and (
        value.currency.upper() != "INR" or not math.isfinite(value.amount) or value.amount < 0
    )]
    unparsed_values = [value for value in values if not isinstance(value, MrpNormalized)]
    if invalid_values:
        format_status = LegalStatus.FAIL
        format_reason = "At least one reliable MRP declaration contains an invalid currency or numeric value."
    elif unparsed_values:
        format_status = LegalStatus.REVIEW_REQUIRED
        format_reason = "At least one reliable MRP declaration is structurally ambiguous; officer review is required."
    elif values and (has_retail_label or has_inr_marker):
        format_status = LegalStatus.PASS
        format_reason = "All reliable parsed MRP declarations contain finite non-negative INR values with a recognizable retail-price or currency marker."
    else:
        format_status = LegalStatus.REVIEW_REQUIRED
        format_reason = "MRP evidence is incomplete or structurally ambiguous; officer review is required."

    format_result = _result(
        rule_id="MRP_VALUE_FORMAT_VALIDITY", field="MRP", status=format_status,
        reason=format_reason, source_rule=source_rule, decision=decision,
        reference_date=reference_date, candidates=selected,
        evaluated_value=[value if value is not None else candidate.raw_value for candidate, value in zip(detected, values)],
    )

    inclusive = bool(re.search(r"\bINCLUS(?:IVE|ION)\b.{0,18}\b(?:ALL\s+)?(?:TAX(?:ES)?|GST)\b", raw, re.IGNORECASE))
    contradiction = bool(re.search(
        r"(?:\b(?:TAX(?:ES)?|GST)\b\s*(?:IS\s*)?(?:EXTRA|ADDITIONAL)|"
        r"\b(?:PLUS|\+)\s*(?:APPLICABLE\s*)?(?:TAX(?:ES)?|GST)\b|"
        r"\bEXCLUD(?:ING|ES?)\b.{0,18}\b(?:TAX(?:ES)?|GST)\b|"
        r"\bEXCLUSIVE\s+OF\b.{0,18}\b(?:TAX(?:ES)?|GST)\b)",
        raw,
        re.IGNORECASE,
    ))
    mentions_tax = bool(re.search(r"\b(?:TAX(?:ES)?|GST)\b", raw, re.IGNORECASE))
    if contradiction:
        tax_status = LegalStatus.FAIL
        tax_reason = "At least one reliable declaration states that tax/GST is extra or excluded, contradicting the retail sale price requirement that it be inclusive of all taxes."
    elif inclusive:
        tax_status = LegalStatus.PASS
        tax_reason = "MRP tax wording explicitly states that the retail sale price is inclusive of all taxes."
    elif mentions_tax:
        tax_status = LegalStatus.REVIEW_REQUIRED
        tax_reason = "Tax wording is present but incomplete or ambiguous; officer review is required."
    else:
        tax_status = LegalStatus.NOT_APPLICABLE
        tax_reason = "No separate tax wording was observed; this consistency check does not require a particular optional phrase."

    tax_result = _result(
        rule_id="MRP_TAX_WORDING_CONSISTENCY", field="MRP", status=tax_status,
        reason=tax_reason, source_rule=source_rule, decision=decision,
        reference_date=reference_date, candidates=selected, evaluated_value=reliable_raw_values,
    )
    return [format_result, tax_result]


def _validate_net_quantity(
    candidates: list[FieldCandidate],
    source_rule: RuleDefinition,
    decision: ApplicabilityDecision,
    reference_date: date,
) -> list[RuleEvaluationResult]:
    selected = _sorted_candidates(candidates, "NET_QUANTITY")
    detected = [candidate for candidate in selected if candidate.status == "DETECTED"]
    if not detected:
        unresolved = _uncertain_or_missing(
            "NET_QUANTITY_FORMAT_VALIDITY", source_rule, decision, reference_date, selected,
            "Declaration validity cannot be determined from missing, unparsed, or uncertain evidence.",
        )
        return [
            unresolved,
            unresolved.model_copy(update={"rule_id": "NET_QUANTITY_UNIT_VALIDITY"}),
        ]
    values = [candidate.normalized_value for candidate in detected]
    typed_values = [value for value in values if isinstance(value, NetQuantityNormalized)]
    if any(not math.isfinite(value.value) or value.value <= 0 for value in typed_values):
        format_status, format_reason = LegalStatus.FAIL, "At least one reliable net quantity declaration contains a non-positive or non-finite numeric value."
    elif len(typed_values) != len(values):
        format_status, format_reason = LegalStatus.REVIEW_REQUIRED, "At least one net quantity declaration could not be parsed into a numeric value and unit."
    else:
        format_status, format_reason = LegalStatus.PASS, "All reliable parsed net quantity declarations contain finite positive numeric values."
    invalid_units = sorted({value.unit for value in typed_values if value.unit.strip().lower() not in _QUANTITY_UNITS})
    if invalid_units:
        unit_status, unit_reason = LegalStatus.FAIL, f"At least one reliable net quantity declaration uses an unrecognized unit: {', '.join(repr(unit) for unit in invalid_units)}."
    elif len(typed_values) != len(values):
        unit_status, unit_reason = LegalStatus.REVIEW_REQUIRED, "At least one net quantity unit could not be parsed reliably."
    else:
        unit_status, unit_reason = LegalStatus.PASS, "All reliable parsed net quantity declarations use recognized mass, volume, length, or count units."
    return [
        _result(rule_id="NET_QUANTITY_FORMAT_VALIDITY", field="NET_QUANTITY", status=format_status,
                reason=format_reason, source_rule=source_rule, decision=decision,
                reference_date=reference_date, candidates=selected, evaluated_value=values),
        _result(rule_id="NET_QUANTITY_UNIT_VALIDITY", field="NET_QUANTITY", status=unit_status,
                reason=unit_reason, source_rule=source_rule, decision=decision,
                reference_date=reference_date, candidates=selected, evaluated_value=values),
    ]


def _date_tuple(value: DateNormalized) -> tuple[int, int, int] | None:
    if value.year is None or value.month is None:
        return None
    day = value.day if value.day is not None else 1
    try:
        parsed = date(value.year, value.month, day)
    except ValueError:
        return None
    return parsed.year, parsed.month, parsed.day


def _validate_dates(
    candidates: list[FieldCandidate],
    source_rule: RuleDefinition,
    decision: ApplicabilityDecision,
    reference_date: date,
) -> list[RuleEvaluationResult]:
    selected = _sorted_candidates(candidates, "MONTH_YEAR")
    detected = [candidate for candidate in selected if candidate.status == "DETECTED"]
    if not detected:
        validity = _uncertain_or_missing(
            "DATE_DECLARATION_VALIDITY", source_rule, decision, reference_date, selected,
            "Date validity cannot be determined from missing, unparsed, or uncertain evidence.",
        )
        chronology = validity.model_copy(update={
            "rule_id": "DATE_CHRONOLOGY_CONSISTENCY",
            "status": LegalStatus.NOT_APPLICABLE,
            "reason": "Chronology requires at least one reliable base date and terminal date.",
        })
        return [validity, chronology]

    invalid = []
    incomplete = []
    for candidate in detected:
        value = candidate.normalized_value
        if not isinstance(value, DateNormalized) or value.type == "UNKNOWN":
            incomplete.append(candidate)
        elif value.duration is not None:
            if value.duration <= 0 or value.duration_unit not in {"DAY", "MONTH", "YEAR"}:
                invalid.append(candidate)
        elif _date_tuple(value) is None:
            invalid.append(candidate)
    if invalid:
        validity_status, validity_reason = LegalStatus.FAIL, "Reliable date evidence contains an impossible calendar date or invalid duration."
    elif incomplete or any(candidate.status == "REVIEW_REQUIRED" for candidate in selected):
        validity_status, validity_reason = LegalStatus.REVIEW_REQUIRED, "One or more date declarations are incomplete or uncertain."
    else:
        validity_status, validity_reason = LegalStatus.PASS, "All reliable parsed date declarations are structurally valid."
    validity = _result(
        rule_id="DATE_DECLARATION_VALIDITY", field="MONTH_YEAR", status=validity_status,
        reason=validity_reason, source_rule=source_rule, decision=decision,
        reference_date=reference_date, candidates=selected,
        evaluated_value=[candidate.normalized_value for candidate in detected],
    )

    base_values = [candidate.normalized_value for candidate in detected
                   if isinstance(candidate.normalized_value, DateNormalized)
                   and candidate.normalized_value.type in _BASE_DATE_TYPES]
    terminal_values = [candidate.normalized_value for candidate in detected
                       if isinstance(candidate.normalized_value, DateNormalized)
                       and candidate.normalized_value.type in _TERMINAL_DATE_TYPES]
    if not base_values or not terminal_values:
        chronology_status, chronology_reason = LegalStatus.NOT_APPLICABLE, "Chronology requires both a reliable base date and terminal date."
    elif validity_status != LegalStatus.PASS:
        chronology_status, chronology_reason = LegalStatus.REVIEW_REQUIRED, "Chronology cannot be decided until invalid or uncertain date evidence is resolved."
    else:
        base_points = [_date_tuple(value) for value in base_values]
        terminal_points = [_date_tuple(value) for value in terminal_values]
        if any(point is None for point in base_points + terminal_points):
            if all(value.duration and value.duration > 0 for value in terminal_values):
                chronology_status, chronology_reason = LegalStatus.PASS, "Positive best-before duration is chronologically after the package base date."
            else:
                chronology_status, chronology_reason = LegalStatus.REVIEW_REQUIRED, "Date precision is insufficient for a deterministic chronology comparison."
        elif min(terminal_points) < max(base_points):
            chronology_status, chronology_reason = LegalStatus.FAIL, "A reliable terminal date precedes a reliable manufacture, packing, or import date."
        else:
            chronology_status, chronology_reason = LegalStatus.PASS, "Reliable terminal date does not precede the package base date."
    chronology = _result(
        rule_id="DATE_CHRONOLOGY_CONSISTENCY", field="MONTH_YEAR", status=chronology_status,
        reason=chronology_reason, source_rule=source_rule, decision=decision,
        reference_date=reference_date, candidates=selected,
        evaluated_value=[candidate.normalized_value for candidate in detected],
    )
    return [validity, chronology]


def _validate_business(
    candidates: list[FieldCandidate],
    source_rule: RuleDefinition,
    decision: ApplicabilityDecision,
    reference_date: date,
    evidence_sufficiency: str,
    roles: set[str],
    rule_id: str,
) -> RuleEvaluationResult:
    selected = _sorted_candidates(
        candidates,
        "MANUFACTURER_PACKER_IMPORTER",
        lambda candidate: isinstance(candidate.normalized_value, BusinessNormalized)
        and candidate.normalized_value.role in roles,
    )
    candidate, unresolved = _single_reliable_candidate(rule_id, source_rule, decision, reference_date, selected)
    if unresolved:
        return unresolved
    value = candidate.normalized_value
    if not isinstance(value, BusinessNormalized) or not value.name or len(value.name.strip()) < 2:
        status, reason = LegalStatus.REVIEW_REQUIRED, "Business role was observed but the entity name is incomplete or ambiguous."
    elif value.address and len(value.address.strip()) >= 5:
        status, reason = LegalStatus.PASS, "Business declaration contains both an entity name and an address."
    elif evidence_sufficiency == "SUFFICIENT_FOR_ABSENCE_EVALUATION":
        status, reason = LegalStatus.FAIL, "Reliable business declaration contains an entity name but no address across an absence-eligible evidence set."
    else:
        status, reason = LegalStatus.REVIEW_REQUIRED, "Business entity name was detected, but address evidence is incomplete and absence cannot be established."
    return _result(
        rule_id=rule_id, field="MANUFACTURER_PACKER_IMPORTER", status=status,
        reason=reason, source_rule=source_rule, decision=decision,
        reference_date=reference_date, candidates=selected, evaluated_value=value,
    )


def _validate_consumer_care(
    candidates: list[FieldCandidate],
    source_rule: RuleDefinition,
    decision: ApplicabilityDecision,
    reference_date: date,
) -> RuleEvaluationResult:
    selected = _sorted_candidates(candidates, "CONSUMER_CARE")
    candidate, unresolved = _single_reliable_candidate(
        "CONSUMER_CARE_STRUCTURE_VALIDITY", source_rule, decision, reference_date, selected
    )
    if unresolved:
        return unresolved
    value = candidate.normalized_value
    valid_email = isinstance(value, ConsumerCareNormalized) and bool(
        value.email and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value.email)
    )
    valid_phone = isinstance(value, ConsumerCareNormalized) and bool(
        value.phone and 7 <= len(re.sub(r"\D", "", value.phone)) <= 15
    )
    if valid_email or valid_phone:
        status, reason = LegalStatus.PASS, "Consumer-care declaration contains a structurally usable telephone number or e-mail address."
    else:
        status, reason = LegalStatus.REVIEW_REQUIRED, "Consumer-care text was detected, but no structurally usable contact channel was parsed."
    return _result(
        rule_id="CONSUMER_CARE_STRUCTURE_VALIDITY", field="CONSUMER_CARE", status=status,
        reason=reason, source_rule=source_rule, decision=decision,
        reference_date=reference_date, candidates=selected, evaluated_value=value,
    )


def evaluate_declaration_validity(
    *,
    candidates: list[FieldCandidate],
    applicable_rules: list[RuleDefinition],
    applicability_decisions: dict[str, ApplicabilityDecision],
    reference_date: date,
    evidence_sufficiency: str,
) -> list[RuleEvaluationResult]:
    """Return stable, additive validity findings for active declaration rules."""
    rules = {rule.rule_id: rule for rule in applicable_rules}
    results: list[RuleEvaluationResult] = []

    def source(source_id: str, derived_ids: list[str]):
        source_rule = rules.get(source_id)
        decision = applicability_decisions.get(source_id)
        if not source_rule or not decision:
            return None, None
        for derived_id in derived_ids:
            applicability_result = _applicability_result(derived_id, source_rule, decision, reference_date)
            if applicability_result:
                results.append(applicability_result)
        return source_rule, decision

    source_rule, decision = source(
        "MRP_DECLARATION_PRESENCE", ["MRP_VALUE_FORMAT_VALIDITY", "MRP_TAX_WORDING_CONSISTENCY"]
    )
    if source_rule and decision and decision.status == ApplicabilityStatus.APPLICABLE:
        results.extend(_validate_mrp(candidates, source_rule, decision, reference_date))

    source_rule, decision = source(
        "NET_QUANTITY_PRESENCE", ["NET_QUANTITY_FORMAT_VALIDITY", "NET_QUANTITY_UNIT_VALIDITY"]
    )
    if source_rule and decision and decision.status == ApplicabilityStatus.APPLICABLE:
        results.extend(_validate_net_quantity(candidates, source_rule, decision, reference_date))

    source_rule, decision = source(
        "MONTH_YEAR_DECLARATION_PRESENCE", ["DATE_DECLARATION_VALIDITY", "DATE_CHRONOLOGY_CONSISTENCY"]
    )
    if source_rule and decision and decision.status == ApplicabilityStatus.APPLICABLE:
        results.extend(_validate_dates(candidates, source_rule, decision, reference_date))

    source_rule, decision = source(
        "MANUFACTURER_PACKER_DECLARATION_PRESENCE", ["MANUFACTURER_PACKER_ADDRESS_VALIDITY"]
    )
    if source_rule and decision and decision.status == ApplicabilityStatus.APPLICABLE:
        results.append(_validate_business(
            candidates, source_rule, decision, reference_date, evidence_sufficiency,
            {"MANUFACTURER", "PACKER"}, "MANUFACTURER_PACKER_ADDRESS_VALIDITY",
        ))

    source_rule, decision = source("IMPORTER_DECLARATION_PRESENCE", ["IMPORTER_ADDRESS_VALIDITY"])
    if source_rule and decision and decision.status == ApplicabilityStatus.APPLICABLE:
        results.append(_validate_business(
            candidates, source_rule, decision, reference_date, evidence_sufficiency,
            {"IMPORTER"}, "IMPORTER_ADDRESS_VALIDITY",
        ))

    source_rule, decision = source(
        "CONSUMER_CARE_DECLARATION_PRESENCE", ["CONSUMER_CARE_STRUCTURE_VALIDITY"]
    )
    if source_rule and decision and decision.status == ApplicabilityStatus.APPLICABLE:
        results.append(_validate_consumer_care(candidates, source_rule, decision, reference_date))

    return results
