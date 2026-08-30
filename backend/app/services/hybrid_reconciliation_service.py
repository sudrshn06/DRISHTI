"""Safe Stage 2C promotion boundary for PaddleOCR and Gemini observations.

This module reconciles visible declaration evidence only. It cannot express or
calculate legal outcomes; those remain the responsibility of DRISHTI's
deterministic rule services.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

from app.schemas.gemini import (
    BusinessObservation,
    ConsumerCareObservation,
    CountryOfOriginObservation,
    DateObservation,
    GeminiAnalysisStatus,
    GeminiPackageAnalysis,
    MrpObservation,
    NetQuantityObservation,
    ObservationBase,
    TextObservation,
    UnitSalePriceObservation,
)
from app.schemas.ocr import (
    BusinessNormalized,
    CommonGenericNameNormalized,
    ConsumerCareNormalized,
    CountryOfOriginNormalized,
    DateNormalized,
    FieldCandidate,
    MrpNormalized,
    NetQuantityNormalized,
    ProviderEvidence,
    UnitSalePriceNormalized,
)


_EXPLICIT_ORIGIN_PATTERN = re.compile(
    r"\b(?:country\s+of\s+origin|made\s+in|product\s+of|manufactured\s+in|assembled\s+in)\b",
    re.IGNORECASE,
)


def _has_explicit_country_origin(observation: CountryOfOriginObservation) -> bool:
    country = _canonical_text(observation.country_text)
    visible = _canonical_text(observation.raw_text)
    return bool(
        country
        and country in visible
        and _EXPLICIT_ORIGIN_PATTERN.search(observation.raw_text)
    )


def _observation_items(analysis: GeminiPackageAnalysis) -> Iterable[tuple[str, ObservationBase]]:
    declarations = analysis.declarations
    singles = (
        ("MRP", declarations.mrp),
        ("NET_QUANTITY", declarations.net_quantity),
        ("COUNTRY_OF_ORIGIN", declarations.country_of_origin),
        ("COMMON_GENERIC_NAME", declarations.common_generic_name),
        ("BRAND_NAME", declarations.brand_trade_name),
        ("CONSUMER_CARE", declarations.consumer_care),
        ("UNIT_SALE_PRICE", declarations.unit_sale_price),
        ("COMMON_NAME_QR_INSTRUCTION", declarations.qr_common_name_instruction),
        ("FSSAI_LICENCE", declarations.fssai_licence),
        ("FSSAI_INGREDIENTS", declarations.ingredients),
        ("FSSAI_ALLERGENS", declarations.allergens),
        ("FSSAI_NUTRITION", declarations.nutrition),
        ("FSSAI_VEG_NONVEG", declarations.veg_non_veg),
    )
    for field, observation in singles:
        if observation is not None:
            yield field, observation
    for observation in declarations.manufacturer_packer_importer:
        yield "MANUFACTURER_PACKER_IMPORTER", observation
    for observation in declarations.dates:
        yield "MONTH_YEAR", observation


def _normalized_from_gemini(field: str, observation: ObservationBase):
    if isinstance(observation, MrpObservation):
        if observation.amount is None:
            return None
        return MrpNormalized(currency=observation.currency or "INR", amount=observation.amount)
    if isinstance(observation, NetQuantityObservation):
        if observation.value is None or not observation.unit:
            return None
        return NetQuantityNormalized(value=observation.value, unit=observation.unit)
    if isinstance(observation, BusinessObservation):
        if not any((observation.name, observation.address, observation.pin_code)):
            return None
        return BusinessNormalized(
            role=observation.role,
            name=observation.name,
            address=observation.address,
            pin_code=observation.pin_code,
            raw_text=observation.raw_text,
        )
    if isinstance(observation, DateObservation):
        if not any((observation.day, observation.month, observation.year, observation.duration)):
            return None
        return DateNormalized(
            type=observation.date_type,
            day=observation.day,
            month=observation.month,
            year=observation.year,
            duration=observation.duration,
            duration_unit=observation.duration_unit,
        )
    if isinstance(observation, CountryOfOriginObservation):
        if not observation.country_text:
            return None
        return CountryOfOriginNormalized(
            declaration_type=observation.declaration_type,
            country_text=observation.country_text,
            raw_text=observation.raw_text,
        )
    if isinstance(observation, ConsumerCareObservation):
        if not observation.email and not observation.phone:
            return None
        return ConsumerCareNormalized(email=observation.email, phone=observation.phone)
    if isinstance(observation, UnitSalePriceObservation):
        if None in (observation.amount, observation.per_quantity) or not observation.per_unit:
            return None
        return UnitSalePriceNormalized(
            amount=observation.amount,
            currency=observation.currency or "INR",
            per_quantity=observation.per_quantity,
            per_unit=observation.per_unit,
        )
    if isinstance(observation, TextObservation) and observation.value:
        if field == "COMMON_GENERIC_NAME":
            return CommonGenericNameNormalized(name_text=observation.value)
        return observation.value
    return None


def _display_value(field: str, observation: ObservationBase) -> str:
    if isinstance(observation, TextObservation) and observation.value:
        return observation.value
    return observation.raw_text


def _plain(value):
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _canonical_text(value: object) -> str:
    text = str(value or "").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _currency(value: Optional[str]) -> str:
    normalized = _canonical_text(value)
    return "inr" if normalized in {"", "rs", "inr"} or value == "₹" else normalized


def _values_agree(left, right) -> bool:
    if isinstance(left, MrpNormalized) and isinstance(right, MrpNormalized):
        return left.amount == right.amount and _currency(left.currency) == _currency(right.currency)
    if isinstance(left, NetQuantityNormalized) and isinstance(right, NetQuantityNormalized):
        return left.value == right.value and _canonical_text(left.unit) == _canonical_text(right.unit)
    if isinstance(left, DateNormalized) and isinstance(right, DateNormalized):
        return left.model_dump(exclude={"type"}) == right.model_dump(exclude={"type"}) and left.type == right.type
    if isinstance(left, BusinessNormalized) and isinstance(right, BusinessNormalized):
        return all(
            _canonical_text(getattr(left, name)) == _canonical_text(getattr(right, name))
            for name in ("role", "name", "address", "pin_code")
        )
    if isinstance(left, ConsumerCareNormalized) and isinstance(right, ConsumerCareNormalized):
        return (
            _canonical_text(left.email) == _canonical_text(right.email)
            and _canonical_text(left.phone) == _canonical_text(right.phone)
        )
    if isinstance(left, CommonGenericNameNormalized) and isinstance(right, CommonGenericNameNormalized):
        return _canonical_text(left.name_text) == _canonical_text(right.name_text)
    if isinstance(left, str) and isinstance(right, str):
        return _canonical_text(left) == _canonical_text(right)
    return _plain(left) == _plain(right)


def _date_context_match(left, right) -> bool:
    return (
        isinstance(left, DateNormalized)
        and isinstance(right, DateNormalized)
        and left.type == "UNKNOWN"
        and right.type != "UNKNOWN"
        and left.model_dump(exclude={"type"}) == right.model_dump(exclude={"type"})
    )


def _partial_context_support(field: str, paddle: FieldCandidate, gemini_value) -> bool:
    paddle_value = paddle.normalized_value
    if isinstance(paddle_value, BusinessNormalized) and isinstance(gemini_value, BusinessNormalized):
        compared = False
        for name in ("role", "name", "address", "pin_code"):
            existing = getattr(paddle_value, name)
            if existing:
                compared = True
                if _canonical_text(existing) != _canonical_text(getattr(gemini_value, name)):
                    return False
        return compared
    if isinstance(paddle_value, ConsumerCareNormalized) and isinstance(gemini_value, ConsumerCareNormalized):
        compared = False
        for name in ("email", "phone"):
            existing = getattr(paddle_value, name)
            if existing:
                compared = True
                if _canonical_text(existing) != _canonical_text(getattr(gemini_value, name)):
                    return False
        return compared
    if field == "FSSAI_ALLERGENS":
        clean = _canonical_text(gemini_value)
        return bool(clean) and clean in _canonical_text(paddle.raw_value)
    return False


def _matches_observation(candidate: FieldCandidate, field: str, gemini_value) -> bool:
    if candidate.field != field:
        return False
    value = candidate.normalized_value
    if field == "MONTH_YEAR" and isinstance(gemini_value, DateNormalized):
        return not isinstance(value, DateNormalized) or value.type in {"UNKNOWN", gemini_value.type}
    if field == "MANUFACTURER_PACKER_IMPORTER" and isinstance(gemini_value, BusinessNormalized):
        return not isinstance(value, BusinessNormalized) or value.role in {"UNKNOWN", gemini_value.role}
    return True


def _provider_evidence(
    paddle: Iterable[FieldCandidate],
    observation: ObservationBase,
    *,
    capture_id: str,
    view_id: str,
) -> list[ProviderEvidence]:
    evidence = [
        ProviderEvidence(
            provider="PADDLEOCR",
            raw_text=candidate.raw_value,
            normalized_value=_plain(candidate.normalized_value),
            evidence_ids=list(candidate.evidence_ids),
            capture_id=capture_id,
            view_id=view_id,
            confidence=candidate.confidence,
        )
        for candidate in paddle
        if candidate.status != "NOT_DETECTED"
    ]
    evidence.append(ProviderEvidence(
        provider="GOOGLE_GEMINI",
        raw_text=observation.raw_text,
        normalized_value=_plain(_normalized_from_gemini("", observation)),
        capture_id=capture_id,
        view_id=view_id,
        confidence=observation.confidence,
        uncertain=observation.uncertain,
        contradiction=observation.contradiction,
        evidence_note=observation.evidence_note,
    ))
    return evidence


def _reconciled_candidate(
    *,
    field: str,
    paddle: list[FieldCandidate],
    observation: ObservationBase,
    gemini_value,
    capture_id: str,
    view_id: str,
) -> FieldCandidate:
    active = [candidate for candidate in paddle if candidate.status in {"DETECTED", "REVIEW_REQUIRED"}]
    meaningful = [candidate for candidate in active if candidate.normalized_value is not None]
    context_match = next(
        (candidate for candidate in meaningful if _date_context_match(candidate.normalized_value, gemini_value)),
        None,
    )
    agreement = next(
        (candidate for candidate in meaningful if _values_agree(candidate.normalized_value, gemini_value)),
        None,
    )
    partial = next(
        (candidate for candidate in active if _partial_context_support(field, candidate, gemini_value)),
        None,
    )
    disagreement = bool(meaningful and not (agreement or context_match or partial))

    if observation.contradiction or disagreement:
        reason = "PROVIDER_CONFLICT"
        status = "REVIEW_REQUIRED"
        normalized_value = None
        raw_value = " | ".join(
            value for value in [*(candidate.raw_value for candidate in active), observation.raw_text] if value
        )
    elif context_match or partial:
        reason = "OCR_SUPPORTED_GEMINI_CONTEXT"
        status = "REVIEW_REQUIRED" if observation.uncertain else "DETECTED"
        normalized_value = gemini_value
        raw_value = _display_value(field, observation)
    elif agreement:
        reason = "AGREEMENT"
        status = "REVIEW_REQUIRED" if observation.uncertain else "DETECTED"
        normalized_value = gemini_value
        raw_value = _display_value(field, observation)
    else:
        reason = "GEMINI_EXPLICIT_EVIDENCE"
        status = "REVIEW_REQUIRED" if observation.uncertain else "DETECTED"
        normalized_value = gemini_value
        raw_value = _display_value(field, observation)

    paddle_confidences = [candidate.confidence for candidate in active if candidate.confidence is not None]
    confidence = min([observation.confidence, *paddle_confidences]) if (agreement or context_match) and paddle_confidences else observation.confidence
    evidence_ids = list(dict.fromkeys(
        evidence_id for candidate in active for evidence_id in candidate.evidence_ids
    ))
    return FieldCandidate(
        field=field,
        status=status,
        raw_value=raw_value,
        normalized_value=normalized_value,
        evidence_ids=evidence_ids,
        capture_ids=[capture_id],
        confidence=confidence,
        observation_layer="RECONCILED",
        extraction_method="HYBRID_RECONCILIATION",
        observation_sources=["PADDLEOCR", "GOOGLE_GEMINI"] if active else ["GOOGLE_GEMINI"],
        reconciliation_reason=reason,
        provider_evidence=_provider_evidence(active, observation, capture_id=capture_id, view_id=view_id),
    )


def reconcile_capture_candidates(
    paddle_candidates: list[FieldCandidate],
    analysis: GeminiPackageAnalysis,
    *,
    capture_id: str,
    view_id: str,
) -> list[FieldCandidate]:
    """Return capture candidates with safe, explicit Gemini evidence reconciled.

    Provider failures preserve the original PaddleOCR path byte-for-byte at the
    model level. Unsupported inferences remain only in the append-only Gemini
    audit and are not promoted into authoritative candidates.
    """
    result = [candidate.model_copy(deep=True) for candidate in paddle_candidates]
    if analysis.status != GeminiAnalysisStatus.SUCCEEDED:
        return result

    for field, observation in _observation_items(analysis):
        if field == "COUNTRY_OF_ORIGIN" and not _has_explicit_country_origin(observation):
            continue
        gemini_value = _normalized_from_gemini(field, observation)
        if gemini_value is None or not observation.raw_text.strip() or not observation.evidence_note.strip():
            continue

        matches = [candidate for candidate in result if _matches_observation(candidate, field, gemini_value)]
        reconciled = _reconciled_candidate(
            field=field,
            paddle=matches,
            observation=observation,
            gemini_value=gemini_value,
            capture_id=capture_id,
            view_id=view_id,
        )
        result = [candidate for candidate in result if candidate not in matches]
        result.append(reconciled)

    return result
