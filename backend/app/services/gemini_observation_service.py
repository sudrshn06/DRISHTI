"""Aggregate advisory Gemini context without granting it legal authority."""

from collections import defaultdict
from typing import Iterable, Optional

from app.core.config import settings
from app.schemas.gemini import (
    DetectedContextItem,
    DetectedPackageContext,
    GeminiAnalysisStatus,
    GeminiPackageAnalysis,
)
from app.schemas.inspection import CaptureRecord, InspectionSession


def aggregate_detected_package_context(
    captures: Iterable[CaptureRecord],
    *,
    min_confidence: Optional[float] = None,
) -> Optional[DetectedPackageContext]:
    """Builds a cross-capture suggestion card without changing session context."""
    threshold = settings.gemini_context_min_confidence if min_confidence is None else min_confidence
    by_field = defaultdict(list)

    for capture in captures:
        audit = capture.ai_analysis
        analysis = audit.analysis if audit else None
        if not analysis or analysis.status != GeminiAnalysisStatus.SUCCEEDED:
            continue
        for suggestion in analysis.context_suggestions:
            value = suggestion.suggested_value.value
            if value == "UNKNOWN":
                continue
            by_field[suggestion.field].append(suggestion)

    if not by_field:
        return None

    items: list[DetectedContextItem] = []
    contradiction_fields: list[str] = []

    for field, suggestions in sorted(by_field.items()):
        eligible = [
            suggestion for suggestion in suggestions
            if suggestion.confidence >= threshold
            and suggestion.evidence
            and not suggestion.uncertain
            and not suggestion.contradiction
        ]
        eligible_values = {suggestion.suggested_value.value for suggestion in eligible}
        explicitly_contradicted = any(suggestion.contradiction for suggestion in suggestions)
        if explicitly_contradicted or len(eligible_values) > 1:
            contradiction_fields.append(field)
            continue
        if not eligible:
            continue

        best = max(eligible, key=lambda suggestion: suggestion.confidence)
        evidence = list(dict.fromkeys(
            evidence_item
            for suggestion in eligible
            for evidence_item in suggestion.evidence
        ))
        items.append(DetectedContextItem(
            field=field,
            suggested_value=best.suggested_value.value,
            confidence=best.confidence,
            evidence=evidence,
        ))

    context_updates = {item.field: item.suggested_value for item in items}
    return DetectedPackageContext(
        suggestions=items,
        context_updates=context_updates,
        contradiction_fields=contradiction_fields,
        ready_for_confirmation=bool(items),
    )


def refresh_detected_package_context(session: InspectionSession) -> None:
    """Refreshes advisory context only; authoritative fields remain untouched."""
    session.detected_package_context = aggregate_detected_package_context(session.captures)
