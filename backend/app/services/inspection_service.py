import json
from typing import List, Dict, Any
from collections import defaultdict
from app.schemas.inspection import CapturePlan, CaptureRecord
from app.schemas.ocr import FieldCandidate, is_authoritative_field_candidate


def _merged_provenance(candidates_with_caps: List[tuple[FieldCandidate, str]]) -> tuple[str, List[str]]:
    sources = sorted({
        source
        for candidate, _ in candidates_with_caps
        for source in (candidate.observation_sources or [candidate.extraction_method])
    })
    method = sources[0] if len(sources) == 1 else "MULTI_SOURCE"
    return method, sources


def _merged_reconciliation(candidates_with_caps: List[tuple[FieldCandidate, str]]):
    reasons = {
        candidate.reconciliation_reason
        for candidate, _ in candidates_with_caps
        if candidate.reconciliation_reason
    }
    reason = next(iter(reasons)) if len(reasons) == 1 else ("PROVIDER_CONFLICT" if reasons else None)
    provider_evidence = []
    for candidate, _ in candidates_with_caps:
        provider_evidence.extend(item.model_copy(deep=True) for item in candidate.provider_evidence)
    return reason, provider_evidence

def evaluate_completeness(plan: CapturePlan, captures: List[CaptureRecord]) -> str:
    """
    Evaluates if all required views in the CapturePlan have at least one CaptureRecord.
    Duplicate views do not negatively impact completeness.
    """
    required_views = {view.view_id for view in plan.views if view.required}
    captured_views = {capture.view_id for capture in captures}
    
    if required_views.issubset(captured_views):
        return "COMPLETE_EVIDENCE_CAPTURE"
    return "INCOMPLETE_INSPECTION"

def evaluate_evidence_sufficiency(plan: CapturePlan, captures: List[CaptureRecord]) -> str:
    """
    Evaluates if the captured evidence is sufficient for a safe absence evaluation.
    Requires an eligible plan, a complete inspection, and every required view to have at least one usable capture.
    """
    if not plan.absence_evaluation_eligible:
        return "INSUFFICIENT_FOR_ABSENCE_EVALUATION"
        
    capture_status = evaluate_completeness(plan, captures)
    if capture_status != "COMPLETE_EVIDENCE_CAPTURE":
        return "INSUFFICIENT_FOR_ABSENCE_EVALUATION"
        
    required_views = {view.view_id for view in plan.views if view.required}
    
    usable_captures_per_view = defaultdict(list)
    for cap in captures:
        if cap.status != "RETAKE_RECOMMENDED" and cap.pipeline_status != "FAILED":
            usable_captures_per_view[cap.view_id].append(cap)
            
    for view in required_views:
        if not usable_captures_per_view[view]:
            return "INSUFFICIENT_FOR_ABSENCE_EVALUATION"
            
    return "SUFFICIENT_FOR_ABSENCE_EVALUATION"

def _normalize_value_to_hashable(val: Any) -> Any:
    """
    Converts a normalized value to a hashable format for deduplication.
    Handles Pydantic models, dicts, lists, etc.
    """
    if val is None:
        return None
    if isinstance(val, list):
        return tuple(_normalize_value_to_hashable(item) for item in val)
    if hasattr(val, "model_dump"):
        # Convert pydantic model to dict, then to tuple of sorted items
        d = val.model_dump()
        return tuple(sorted((k, _normalize_value_to_hashable(v)) for k, v in d.items()))
    if isinstance(val, dict):
        return tuple(sorted((k, _normalize_value_to_hashable(v)) for k, v in val.items()))
    return val


def _semantic_candidate_key(candidate: FieldCandidate) -> str:
    payload = candidate.model_dump(
        mode="json",
        exclude={"capture_ids", "evidence_ids", "confidence", "provider_evidence"},
    )
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_capture_key(capture: CaptureRecord) -> tuple[str, str, tuple[str, ...]]:
    candidates = capture.deterministic_field_candidates
    if candidates is None:
        candidates = capture.field_candidates
    return (
        capture.view_id,
        capture.image_sha256 or "",
        tuple(sorted(_semantic_candidate_key(candidate) for candidate in candidates)),
    )

def aggregate_candidates(captures: List[CaptureRecord]) -> List[FieldCandidate]:
    """
    Aggregates FieldCandidates from multiple captures.
    Resolves conflicts deterministically and deduplicates identical findings.
    """
    # 1. Gather all candidates grouped by field name
    field_groups: Dict[str, List[tuple[FieldCandidate, str]]] = defaultdict(list)
    
    # Random database UUIDs must never determine candidate precedence.
    sorted_captures = sorted(captures, key=_stable_capture_key)
    
    # 1a. Provenance-scoped suppression of weak redundant candidates across all captures
    all_cands = []
    for capture in sorted_captures:
        # Defense in depth: raw AI observations stay outside candidates. Stage
        # 2C reconciled candidates remain available to the officer-facing view;
        # the legal boundary uses the separately persisted deterministic stream.
        all_cands.extend([
            (cand.model_copy(deep=True), capture.capture_id)
            for cand in capture.field_candidates
            if is_authoritative_field_candidate(cand)
        ])

    all_cands.sort(key=lambda item: (_semantic_candidate_key(item[0]), item[1]))
        
    filtered_cands = []
    for cand, cap_id in all_cands:
        if cand.status == "REVIEW_REQUIRED":
            shares_evidence = False
            if cand.evidence_ids:
                for dc, _ in all_cands:
                    if dc.field == cand.field and dc.status == "DETECTED" and dc.evidence_ids:
                        if set(cand.evidence_ids).intersection(set(dc.evidence_ids)):
                            shares_evidence = True
                            break
            if not shares_evidence:
                filtered_cands.append((cand, cap_id))
        else:
            filtered_cands.append((cand, cap_id))
    
    for candidate, cap_id in filtered_cands:
        # Group by field, and if it's a date, group by its type to avoid false conflicts
        group_key = candidate.field
        if candidate.field == "MONTH_YEAR" and candidate.normalized_value and getattr(candidate.normalized_value, "type", None):
            group_key = f"MONTH_YEAR_{candidate.normalized_value.type}"
        elif candidate.field == "MANUFACTURER_PACKER_IMPORTER" and candidate.normalized_value and getattr(candidate.normalized_value, "role", None):
            group_key = f"MANUFACTURER_PACKER_IMPORTER_{candidate.normalized_value.role}"
        field_groups[group_key].append((candidate, cap_id))
            
    aggregated_results: List[FieldCandidate] = []
    
    # 2. Process each field group
    for group_key, candidates_with_caps in sorted(field_groups.items()):
        field_name = candidates_with_caps[0][0].field
        
        active_candidates = [
            (cand, cap_id) for cand, cap_id in candidates_with_caps 
            if cand.status in ("DETECTED", "REVIEW_REQUIRED")
        ]
        
        # If there are any DETECTED candidates, suppress REVIEW_REQUIRED to avoid conflicts with generic fallback
        if any(cand.status == "DETECTED" for cand, _ in active_candidates):
            active_candidates = [
                (cand, cap_id) for cand, cap_id in active_candidates
                if cand.status == "DETECTED"
            ]
        
        not_detected_candidates = [
            (cand, cap_id) for cand, cap_id in candidates_with_caps 
            if cand.status == "NOT_DETECTED"
        ]
        
        if not active_candidates:
            # All are NOT_DETECTED
            if not_detected_candidates:
                first_cand, _ = not_detected_candidates[0]
                extraction_method, observation_sources = _merged_provenance(not_detected_candidates)
                reconciliation_reason, provider_evidence = _merged_reconciliation(not_detected_candidates)
                merged = FieldCandidate(
                    field=field_name,
                    status="NOT_DETECTED",
                    raw_value=first_cand.raw_value,
                    normalized_value=first_cand.normalized_value,
                    evidence_ids=[],
                    capture_ids=[],
                    observation_layer="AGGREGATED",
                    extraction_method=extraction_method,
                    observation_sources=observation_sources,
                    reconciliation_reason=reconciliation_reason,
                    provider_evidence=provider_evidence,
                )
                for cand, cap_id in not_detected_candidates:
                    merged.evidence_ids.extend(cand.evidence_ids)
                    if cap_id not in merged.capture_ids:
                        merged.capture_ids.append(cap_id)
                merged.evidence_ids = sorted(set(merged.evidence_ids))
                merged.capture_ids = sorted(set(merged.capture_ids))
                aggregated_results.append(merged)
            continue
            
        # We have active candidates (DETECTED or REVIEW_REQUIRED).
        
        if field_name == "CONSUMER_CARE" and len(active_candidates) > 1:
            from app.schemas.ocr import ConsumerCareNormalized
            merged_cc = ConsumerCareNormalized()
            has_conflict = False
            for cand, _ in active_candidates:
                val = cand.normalized_value
                if val and hasattr(val, "email") and hasattr(val, "phone"):
                    if val.email:
                        if merged_cc.email and merged_cc.email != val.email:
                            has_conflict = True
                        merged_cc.email = val.email
                    if val.phone:
                        if merged_cc.phone and merged_cc.phone != val.phone:
                            has_conflict = True
                        merged_cc.phone = val.phone
                        
            if not has_conflict:
                for cand, _ in active_candidates:
                    if cand.normalized_value:
                        cand.normalized_value = merged_cc

        elif field_name == "MANUFACTURER_PACKER_IMPORTER" and len(active_candidates) > 1:
            from app.schemas.ocr import BusinessNormalized
            merged_biz = BusinessNormalized(role="UNKNOWN", raw_text="")
            has_conflict = False
            for cand, _ in active_candidates:
                val = cand.normalized_value
                if val and hasattr(val, "role"):
                    merged_biz.role = val.role
                    if val.name:
                        if merged_biz.name and merged_biz.name != val.name:
                            has_conflict = True
                        merged_biz.name = val.name
                    if val.address:
                        if merged_biz.address and merged_biz.address != val.address:
                            has_conflict = True
                        merged_biz.address = val.address
                    if val.pin_code:
                        if merged_biz.pin_code and merged_biz.pin_code != val.pin_code:
                            has_conflict = True
                        merged_biz.pin_code = val.pin_code
                        
            if not has_conflict:
                for cand, _ in active_candidates:
                    if cand.normalized_value:
                        cand.normalized_value.name = merged_biz.name
                        cand.normalized_value.address = merged_biz.address
                        cand.normalized_value.pin_code = merged_biz.pin_code
                        # Unify raw_text to avoid conflict in hashing
                        cand.normalized_value.raw_text = active_candidates[0][0].normalized_value.raw_text

        # Group them by their normalized values to check for true conflicts.
        unique_values: Dict[Any, List[tuple[FieldCandidate, str]]] = defaultdict(list)
        
        for cand, cap_id in active_candidates:
            hashable_val = _normalize_value_to_hashable(cand.normalized_value)
            unique_values[hashable_val].append((cand, cap_id))
            
        if len(unique_values) == 1:
            # All active candidates agree on the normalized value!
            group = list(unique_values.values())[0]
            
            # If ANY candidate in this agreed group is DETECTED, the result is DETECTED.
            # Otherwise, it remains REVIEW_REQUIRED.
            best_status = "REVIEW_REQUIRED"
            for cand, _ in group:
                if cand.status == "DETECTED":
                    best_status = "DETECTED"
                    break
                    
            # Pick a representative candidate (preferably one that is DETECTED)
            rep_cand = next((cand for cand, _ in group if cand.status == "DETECTED"), group[0][0])
            extraction_method, observation_sources = _merged_provenance(candidates_with_caps)
            reconciliation_reason, provider_evidence = _merged_reconciliation(candidates_with_caps)
            
            merged = FieldCandidate(
                field=field_name,
                status=best_status,
                raw_value=rep_cand.raw_value,
                normalized_value=rep_cand.normalized_value,
                confidence=rep_cand.confidence,
                evidence_ids=[],
                capture_ids=[],
                observation_layer="AGGREGATED",
                extraction_method=extraction_method,
                observation_sources=observation_sources,
                reconciliation_reason=reconciliation_reason,
                provider_evidence=provider_evidence,
            )
            for hashable_val, grp in unique_values.items():
                for cand, cap_id in grp:
                    merged.evidence_ids.extend(cand.evidence_ids)
                    if cap_id not in merged.capture_ids:
                        merged.capture_ids.append(cap_id)
            # Include evidence from NOT_DETECTED as well
            for cand, cap_id in not_detected_candidates:
                merged.evidence_ids.extend(cand.evidence_ids)
                if cap_id not in merged.capture_ids:
                        merged.capture_ids.append(cap_id)
            merged.evidence_ids = sorted(set(merged.evidence_ids))
            merged.capture_ids = sorted(set(merged.capture_ids))
            aggregated_results.append(merged)
        else:
            # Multiple unique normalized values -> True conflict!
            extraction_method, observation_sources = _merged_provenance(candidates_with_caps)
            reconciliation_reason, provider_evidence = _merged_reconciliation(candidates_with_caps)
            merged = FieldCandidate(
                field=field_name,
                status="REVIEW_REQUIRED",
                evidence_ids=[],
                capture_ids=[],
                observation_layer="AGGREGATED",
                extraction_method=extraction_method,
                observation_sources=observation_sources,
                reconciliation_reason="PROVIDER_CONFLICT" if provider_evidence else reconciliation_reason,
                provider_evidence=provider_evidence,
            )
            for cand, cap_id in active_candidates:
                merged.evidence_ids.extend(cand.evidence_ids)
                if cap_id not in merged.capture_ids:
                    merged.capture_ids.append(cap_id)
            for cand, cap_id in not_detected_candidates:
                merged.evidence_ids.extend(cand.evidence_ids)
                if cap_id not in merged.capture_ids:
                    merged.capture_ids.append(cap_id)
            merged.evidence_ids = sorted(set(merged.evidence_ids))
            merged.capture_ids = sorted(set(merged.capture_ids))
            aggregated_results.append(merged)

    # Filter out NOT_DETECTED if there is any active candidate for the same base field.
    # This prevents redundant "MONTH_YEAR: NOT_DETECTED" when a subtype like "MONTH_YEAR_PACKED" was detected.
    final_aggregated = []
    active_base_fields = {cand.field for cand in aggregated_results if cand.status in ("DETECTED", "REVIEW_REQUIRED")}
    for cand in aggregated_results:
        if cand.status == "NOT_DETECTED" and cand.field in active_base_fields:
            continue
        final_aggregated.append(cand)

    return final_aggregated
