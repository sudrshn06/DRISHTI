"""Deterministic, secret-free manifest generation for finalized evidence exports."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from app.schemas.inspection import InspectionSession
from app.schemas.report import InspectionReportSnapshot
from app.services.reproducibility_service import deterministic_candidates_for_capture


MANIFEST_SCHEMA_VERSION = "1.0"


def has_confirmed_deterministic_fail(report: InspectionReportSnapshot) -> bool:
    return any(
        finding.status == "FAIL"
        for finding in (
            *report.declaration_findings,
            *report.food_label_findings,
            *report.visual_compliance_findings,
        )
    )


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _json_value(value.model_dump(mode="json"))
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, set):
        return sorted((_json_value(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    # Manifest construction is allowlisted, so this is a narrow safety net for
    # structured domain values that do not expose a JSON representation.
    return str(value)


def _candidate_record(candidate, *, source_views: list[str]) -> dict[str, Any]:
    return {
        "field": candidate.field,
        "status": candidate.status,
        "normalized_value": _json_value(candidate.normalized_value),
        "raw_observed_text": candidate.raw_value,
        "source_views": sorted(set(source_views)),
        "evidence_ids": sorted(set(candidate.evidence_ids)),
        "capture_ids": sorted(set(candidate.capture_ids)),
        "confidence": candidate.confidence,
        "observation_layer": candidate.observation_layer,
        "extraction_method": candidate.extraction_method,
        "observation_sources": sorted(set(candidate.observation_sources)),
        "officer_confirmed": candidate.observation_layer == "OFFICER_CONFIRMED",
    }


def _finding_record(finding, domain: str, capture_views: dict[str, str]) -> dict[str, Any]:
    evaluated = _json_value(getattr(finding, "evaluated_value", None))
    source_views = sorted({capture_views[item] for item in finding.capture_ids if item in capture_views})
    if isinstance(evaluated, dict):
        source_views = sorted(set(source_views) | set(evaluated.get("source_views", [])))
    return {
        "rule_id": finding.rule_id,
        "domain": domain,
        "status": finding.status,
        "field": finding.field,
        "reason": finding.reason,
        "evaluated_value": evaluated,
        "expected_condition": evaluated.get("expected_condition") if isinstance(evaluated, dict) else None,
        "source_views": source_views,
        "evidence_ids": sorted(set(finding.evidence_ids)),
        "capture_ids": sorted(set(finding.capture_ids)),
        "legal_reference": finding.legal_reference,
        "applicability_status": getattr(finding, "applicability_status", None),
    }


def build_evidence_manifest(
    session: InspectionSession,
    report: InspectionReportSnapshot,
    *,
    officer_notes: str = "",
    complaint_draft: str = "",
) -> dict[str, Any]:
    """Build an allowlisted manifest from the frozen report and deterministic evidence."""
    capture_views = {capture.capture_id: capture.view_id for capture in session.captures}
    capture_by_id = {capture.capture_id: capture for capture in session.captures}

    captures = []
    for asset in sorted(report.evidence_assets, key=lambda item: (item.view_id, item.capture_id)):
        capture = capture_by_id.get(asset.capture_id)
        provenance = capture.processing_provenance if capture else None
        captures.append({
            "capture_id": asset.capture_id,
            "evidence_id": capture.evidence_id if capture else None,
            "surface_view": asset.view_id,
            "image_sha256": asset.image_sha256,
            "media_type": asset.media_type,
            "evidence_ids": sorted(set(asset.evidence_ids)),
            "processing_provenance": _json_value(provenance) if provenance else None,
            "ocr_engine": provenance.ocr_engine if provenance else None,
            "ocr_engine_version": provenance.ocr_engine_version if provenance else None,
            "preprocessing_config_id": provenance.preprocessing_config_id if provenance else None,
            "capture_timestamp": None,
        })

    machine_observations = []
    for capture in sorted(session.captures, key=lambda item: (item.view_id, item.image_sha256 or "")):
        for candidate in deterministic_candidates_for_capture(capture):
            if candidate.status == "NOT_DETECTED":
                continue
            record = _candidate_record(candidate, source_views=[capture.view_id])
            record["capture_ids"] = sorted(set(record["capture_ids"] + [capture.capture_id]))
            machine_observations.append(record)
    machine_observations.sort(key=lambda item: json.dumps(item, sort_keys=True, default=str))

    effective_declarations = []
    for candidate in session.deterministic_aggregated_candidates or session.aggregated_candidates:
        if candidate.status == "NOT_DETECTED":
            continue
        views = [capture_views[item] for item in candidate.capture_ids if item in capture_views]
        effective_declarations.append(_candidate_record(candidate, source_views=views))
    effective_declarations.sort(key=lambda item: json.dumps(item, sort_keys=True, default=str))

    officer_corrections = [{
        "override_id": item.override_id,
        "target_key": item.target_key,
        "field": item.field,
        "original_machine_observation": _candidate_record(item.observed_candidate, source_views=[]),
        "confirmed_declaration": _candidate_record(item.confirmed_candidate, source_views=[]),
        "supporting_capture_id": item.supporting_capture_id,
        "reason": item.reason,
        "officer_user_id": item.officer_user_id,
        "officer_username": item.officer_username,
        "confirmed_at": item.confirmed_at.isoformat(),
        "source": item.source,
    } for item in session.officer_declaration_overrides]

    findings = []
    for domain, items in (
        ("LEGAL_METROLOGY", report.declaration_findings),
        ("FOOD_LABEL_FSSAI", report.food_label_findings),
    ):
        findings.extend(_finding_record(item, domain, capture_views) for item in items)
    for item in report.visual_compliance_findings:
        findings.append({
            "rule_id": item.rule_id, "domain": "VISUAL_PRESENTATION", "status": item.status,
            "field": item.field, "reason": item.reason, "evaluated_value": None,
            "expected_condition": None,
            "source_views": sorted({capture_views[cid] for cid in item.capture_ids if cid in capture_views}),
            "evidence_ids": sorted(set(item.evidence_ids)), "capture_ids": sorted(set(item.capture_ids)),
            "legal_reference": item.legal_reference, "applicability_status": None,
        })
    findings.sort(key=lambda item: (item["domain"], item["rule_id"], item["status"], item.get("field") or ""))
    confirmed_fails = [item for item in findings if item["status"] == "FAIL"]

    review = session.package_information_review
    reproducibility = session.reproducibility
    confirmed_package_context = _json_value(
        reproducibility.confirmed_package_context if reproducibility
        else report.inspector_context.model_dump(mode="json")
    )
    deterministic_escalation_summary = {
        "inspection_id": session.inspection_id,
        "reference_date": _json_value(session.reference_date),
        "confirmed_package_context": confirmed_package_context,
        "ruleset_identifier": reproducibility.ruleset_identifier if reproducibility else None,
        "deterministic_result_fingerprint": reproducibility.result_fingerprint if reproducibility else None,
        "confirmed_fail_count": len(confirmed_fails),
        "findings": [{
            "rule_id": item["rule_id"],
            "domain": item["domain"],
            "field": item["field"],
            "reason": item["reason"],
            "evaluated_value": item["evaluated_value"],
            "legal_reference": item["legal_reference"],
            "source_views": item["source_views"],
            "evidence_ids": item["evidence_ids"],
            "capture_ids": item["capture_ids"],
        } for item in confirmed_fails],
        "generated_from": "FINALIZED_DETERMINISTIC_FAIL_FINDINGS_ONLY",
    }
    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "inspection": {
            "inspection_id": session.inspection_id,
            "reference_date": _json_value(session.reference_date),
            "lifecycle_status": _json_value(session.lifecycle_status),
            "finalized_at": _json_value(report.metadata.generated_at),
            "officer": ({
                "user_id": review.reviewed_by_user_id,
                "username": review.reviewed_by_username,
                "reviewed_at": review.reviewed_at.isoformat(),
            } if review else None),
            "confirmed_package_context": confirmed_package_context,
            "product_category": report.metadata.product_category,
            "ruleset_identifier": reproducibility.ruleset_identifier if reproducibility else None,
            "deterministic_evaluation_version": reproducibility.evaluation_algorithm if reproducibility else None,
            "deterministic_result_fingerprint": reproducibility.result_fingerprint if reproducibility else None,
        },
        "capture_evidence": captures,
        "declarations": {
            "machine_observations": machine_observations,
            "effective_declarations": effective_declarations,
            "officer_corrections": officer_corrections,
        },
        "findings": {
            "all_deterministic_findings": findings,
            "confirmed_deterministic_fail_findings": confirmed_fails,
        },
        "deterministic_escalation_summary": deterministic_escalation_summary,
        "officer_material": {
            "officer_notes": officer_notes,
            "officer_complaint_draft": complaint_draft,
            "content_owner": "OFFICER",
            "editable": True,
            "machine_findings_unchanged": True,
        },
        "external_submission": {
            "submitted_by_drishti": False,
            "statement": "DRISHTI has not submitted a complaint.",
        },
    }
    return _json_value(manifest)
