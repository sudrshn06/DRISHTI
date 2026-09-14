"""Officer-authoritative package review and correction services.

Machine observations remain preserved in captures. Officer corrections are an
append-only overlay applied after deterministic multi-capture aggregation and
before the existing deterministic compliance services.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Iterable, Optional

from app.schemas.inspection import InspectionSession
from app.schemas.ocr import FieldCandidate
from app.schemas.officer_review import (
    OfficerDeclarationOverride,
    PackageInformationReview,
)
from app.services.declaration_normalizer import (
    parse_consumer_care,
    parse_country_of_origin,
    parse_date_declaration,
    parse_mrp,
    parse_net_quantity,
    parse_unit_sale_price,
)
from app.services.inspection_service import aggregate_candidates


OFFICER_CORRECTABLE_FIELDS = {
    "MRP",
    "NET_QUANTITY",
    "UNIT_SALE_PRICE",
    "COMMON_GENERIC_NAME",
    "BRAND_NAME",
    "MANUFACTURER_PACKER_IMPORTER",
    "MONTH_YEAR",
    "COUNTRY_OF_ORIGIN",
    "CONSUMER_CARE",
    "COMMON_NAME_QR_INSTRUCTION",
    "FSSAI_LICENCE",
    "FSSAI_INGREDIENTS",
    "FSSAI_ALLERGENS",
    "FSSAI_NUTRITION",
    "FSSAI_VEG_NONVEG",
}


def _normalized_member(candidate: FieldCandidate, name: str) -> Optional[str]:
    value = candidate.normalized_value
    if value is None:
        return None
    if isinstance(value, dict):
        member = value.get(name)
    else:
        member = getattr(value, name, None)
    return str(member) if member else None


def candidate_target_key(candidate: FieldCandidate) -> str:
    """Return a stable declaration target without relying on UI array order."""
    if candidate.field == "MONTH_YEAR":
        date_type = _normalized_member(candidate, "type")
        if date_type:
            return f"MONTH_YEAR:{date_type}"
    if candidate.field == "MANUFACTURER_PACKER_IMPORTER":
        role = _normalized_member(candidate, "role")
        if role:
            return f"MANUFACTURER_PACKER_IMPORTER:{role}"
    return candidate.field


def _candidate_matches_target(candidate: FieldCandidate, target_key: str, field: str) -> bool:
    # An unqualified target represents a conflict or unreadable declaration and
    # therefore replaces every current aggregate for that base field.
    if ":" not in target_key:
        return candidate.field == field
    return candidate_target_key(candidate) == target_key


def _same_candidate(left: FieldCandidate, right: FieldCandidate) -> bool:
    """Compare complete candidate values without relying on object identity."""
    return left.model_dump(mode="json") == right.model_dump(mode="json")


def _find_previous_override_for_candidate(
    candidate: FieldCandidate,
    overrides: Iterable[OfficerDeclarationOverride],
) -> Optional[OfficerDeclarationOverride]:
    """Resolve the audit record that produced the currently displayed overlay."""
    return next(
        (
            override
            for override in reversed(list(overrides))
            if _same_candidate(override.confirmed_candidate, candidate)
        ),
        None,
    )


def _original_machine_observation(
    override: OfficerDeclarationOverride,
    overrides: Iterable[OfficerDeclarationOverride],
) -> FieldCandidate:
    """Walk older audit entries until the original non-officer observation is found.

    The loop also repairs provenance for inspections written by the earliest
    Stage 1.5 shape, where a repeated correction could have captured the prior
    officer overlay as its observed value.
    """
    history = list(overrides)
    observed = override.observed_candidate
    visited: set[str] = set()
    while observed.observation_layer == "OFFICER_CONFIRMED":
        previous = _find_previous_override_for_candidate(observed, history)
        if not previous or previous.override_id in visited:
            break
        visited.add(previous.override_id)
        observed = previous.observed_candidate
    return observed.model_copy(deep=True)


def apply_officer_overrides(
    aggregated_candidates: Iterable[FieldCandidate],
    overrides: Iterable[OfficerDeclarationOverride],
) -> list[FieldCandidate]:
    """Overlay the latest officer correction for each target deterministically."""
    latest_by_target: dict[str, OfficerDeclarationOverride] = {}
    for override in overrides:
        latest_by_target[override.target_key] = override

    remaining = list(aggregated_candidates)
    results: list[FieldCandidate] = []
    inserted_targets: set[str] = set()

    for candidate in remaining:
        matching = next(
            (
                override
                for target, override in latest_by_target.items()
                if _candidate_matches_target(candidate, target, override.field)
            ),
            None,
        )
        if matching:
            if matching.target_key not in inserted_targets:
                results.append(matching.confirmed_candidate.model_copy(deep=True))
                inserted_targets.add(matching.target_key)
            continue
        results.append(candidate)

    for target, override in latest_by_target.items():
        if target not in inserted_targets:
            results.append(override.confirmed_candidate.model_copy(deep=True))

    return results


def rebuild_authoritative_candidates(session: InspectionSession) -> None:
    base = aggregate_candidates(session.captures)
    session.aggregated_candidates = apply_officer_overrides(
        base,
        session.officer_declaration_overrides,
    )
    from app.services.reproducibility_service import deterministic_candidates_for_capture
    deterministic_captures = [
        capture.model_copy(update={
            "field_candidates": deterministic_candidates_for_capture(capture),
        })
        for capture in session.captures
    ]
    deterministic_base = aggregate_candidates(deterministic_captures)
    session.deterministic_aggregated_candidates = apply_officer_overrides(
        deterministic_base,
        session.officer_declaration_overrides,
    )


def _review_basis_payload(session: InspectionSession) -> dict:
    return {
        "captures": [
            {
                "capture_id": capture.capture_id,
                "image_sha256": capture.image_sha256,
                "field_candidates": [
                    candidate.model_dump(mode="json")
                    for candidate in capture.field_candidates
                ],
            }
            for capture in sorted(session.captures, key=lambda item: item.capture_id)
        ],
        "officer_overrides": [
            {
                "override_id": override.override_id,
                "target_key": override.target_key,
                "confirmed_candidate": override.confirmed_candidate.model_dump(mode="json"),
            }
            for override in session.officer_declaration_overrides
        ],
    }


def package_information_basis_fingerprint(session: InspectionSession) -> str:
    canonical = json.dumps(
        _review_basis_payload(session),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def package_information_review_is_current(session: InspectionSession) -> bool:
    review = session.package_information_review
    if not review:
        return False
    return review.basis_fingerprint == package_information_basis_fingerprint(session)


def invalidate_package_information_review(session: InspectionSession) -> None:
    session.package_information_review = None


def confirm_package_information_review(
    session: InspectionSession,
    *,
    user_id: str,
    username: str,
) -> PackageInformationReview:
    review = PackageInformationReview(
        reviewed_by_user_id=user_id,
        reviewed_by_username=username,
        reviewed_at=datetime.now(timezone.utc),
        basis_fingerprint=package_information_basis_fingerprint(session),
    )
    session.package_information_review = review
    return review


def _normalize_officer_value(
    *,
    field: str,
    confirmed_value: str,
    observed_candidate: FieldCandidate,
    declaration_role: Optional[str] = None,
    date_type: Optional[str] = None,
):
    if field == "MRP":
        parsed = parse_mrp(f"MRP {confirmed_value}")
    elif field == "NET_QUANTITY":
        parsed = parse_net_quantity(confirmed_value)
    elif field == "UNIT_SALE_PRICE":
        parsed = parse_unit_sale_price(f"UNIT SALE PRICE {confirmed_value}")
    elif field == "CONSUMER_CARE":
        parsed = parse_consumer_care(confirmed_value)
    elif field == "COUNTRY_OF_ORIGIN":
        parsed = parse_country_of_origin(f"COUNTRY OF ORIGIN: {confirmed_value}")
    elif field == "MANUFACTURER_PACKER_IMPORTER":
        role = declaration_role or _normalized_member(observed_candidate, "role")
        if not role or role == "UNKNOWN":
            raise ValueError("Select the business role shown on the package")
        prefixes = {
            "MANUFACTURER": "MANUFACTURED BY",
            "PACKER": "PACKED BY",
            "IMPORTER": "IMPORTED BY",
            "MARKETER": "MARKETED BY",
        }
        from app.services.declaration_normalizer import parse_business_declaration
        parsed = parse_business_declaration(f"{prefixes[role]}: {confirmed_value}")
    elif field == "MONTH_YEAR":
        resolved_type = date_type or _normalized_member(observed_candidate, "type") or "UNKNOWN"
        prefixes = {
            "MANUFACTURED": "MFG",
            "PACKED": "PKD",
            "IMPORTED": "IMPORTED",
            "USE_BY": "USE BY",
            "EXPIRY": "EXPIRY",
            "BEST_BEFORE": "BEST BEFORE",
            "UNKNOWN": "DATE",
        }
        parsed = parse_date_declaration(f"{prefixes[resolved_type]}: {confirmed_value}")
    elif field == "COMMON_GENERIC_NAME":
        from app.schemas.ocr import CommonGenericNameNormalized
        parsed = CommonGenericNameNormalized(name_text=confirmed_value)
    else:
        parsed = confirmed_value

    if parsed is None:
        raise ValueError("Enter the value exactly as it is printed on the package")
    return parsed


def create_officer_declaration_override(
    session: InspectionSession,
    *,
    candidate_index: int,
    field: str,
    confirmed_value: str,
    reason: str,
    supporting_capture_id: str,
    officer_user_id: str,
    officer_username: str,
    declaration_role: Optional[str] = None,
    date_type: Optional[str] = None,
) -> OfficerDeclarationOverride:
    if field not in OFFICER_CORRECTABLE_FIELDS:
        raise ValueError("This package declaration cannot be corrected here")
    if candidate_index >= len(session.aggregated_candidates):
        raise ValueError("The package information changed; reopen the correction and try again")

    selected_candidate = session.aggregated_candidates[candidate_index]
    if selected_candidate.field != field:
        raise ValueError("The package information changed; reopen the correction and try again")
    if selected_candidate.status not in {"DETECTED", "REVIEW_REQUIRED"}:
        raise ValueError("An unreadable or missing declaration cannot be converted into legal absence")

    previous_override = _find_previous_override_for_candidate(
        selected_candidate,
        session.officer_declaration_overrides,
    )
    if previous_override:
        target_key = previous_override.target_key
        observed = _original_machine_observation(
            previous_override,
            session.officer_declaration_overrides,
        )
    else:
        target_key = candidate_target_key(selected_candidate)
        observed = selected_candidate.model_copy(deep=True)

    supporting_capture = next(
        (capture for capture in session.captures if capture.capture_id == supporting_capture_id),
        None,
    )
    if not supporting_capture:
        raise ValueError("Select a supporting package photograph from this inspection")

    normalized_value = _normalize_officer_value(
        field=field,
        confirmed_value=confirmed_value,
        observed_candidate=selected_candidate,
        declaration_role=declaration_role,
        date_type=date_type,
    )
    confirmed_candidate = FieldCandidate(
        field=field,
        status="DETECTED",
        raw_value=confirmed_value,
        normalized_value=normalized_value,
        evidence_ids=list(observed.evidence_ids),
        capture_ids=[supporting_capture_id],
        confidence=None,
        observation_layer="OFFICER_CONFIRMED",
        extraction_method="OFFICER_CONFIRMED",
        observation_sources=["OFFICER_CONFIRMED"],
    )
    override = OfficerDeclarationOverride(
        override_id=str(uuid.uuid4()),
        target_key=target_key,
        field=field,
        observed_candidate=observed.model_copy(deep=True),
        confirmed_candidate=confirmed_candidate,
        supporting_capture_id=supporting_capture_id,
        reason=reason,
        officer_user_id=officer_user_id,
        officer_username=officer_username,
        confirmed_at=datetime.now(timezone.utc),
    )
    session.officer_declaration_overrides.append(override)
    invalidate_package_information_review(session)
    rebuild_authoritative_candidates(session)
    return override
