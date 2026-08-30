from datetime import date
from typing import List
from app.schemas.compliance import RuleDefinition, RuleEvaluationResult, LegalStatus
from app.schemas.ocr import FieldCandidate

def get_applicable_rules(rules: List[RuleDefinition], reference_date: date) -> List[RuleDefinition]:
    """
    Selects rules that are active on the reference_date.
    If multiple versions of the same rule exist, picks the most recent active one.
    """
    active_rules = []
    for rule in rules:
        if rule.effective_from <= reference_date:
            if rule.effective_to is None or reference_date <= rule.effective_to:
                active_rules.append(rule)
                
    # Group by rule_id and pick the latest effective_from (tie-break with rule_version)
    latest_rules = {}
    for rule in active_rules:
        if rule.rule_id not in latest_rules:
            latest_rules[rule.rule_id] = rule
        else:
            current = latest_rules[rule.rule_id]
            if rule.effective_from > current.effective_from:
                latest_rules[rule.rule_id] = rule
            elif rule.effective_from == current.effective_from:
                # Tie-breaker on rule_version (string comparison or semantic if desired, 
                # using basic string compare for deterministic tie-break as requested)
                if str(rule.rule_version) > str(current.rule_version):
                    latest_rules[rule.rule_id] = rule
                
    return list(latest_rules.values())

def evaluate_candidate(
    candidate: FieldCandidate, 
    rule: RuleDefinition, 
    reference_date: date, 
    product_category: str = "ALL",
    evidence_sufficiency: str = "INSUFFICIENT_FOR_ABSENCE_EVALUATION"
) -> RuleEvaluationResult:
    """
    Evaluates a candidate against a rule using deterministic logic.
    """
    # Product Scope check
    if rule.product_scope != "ALL" and rule.product_scope != product_category:
        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            rule_version=rule.rule_version,
            field=rule.field,
            status=LegalStatus.NOT_APPLICABLE,
            reason=f"Rule scope '{rule.product_scope}' does not match product category '{product_category}'",
            evaluated_value=None,
            evidence_ids=candidate.evidence_ids,
            capture_ids=candidate.capture_ids,
            reference_date=reference_date
        )

    status = LegalStatus.REVIEW_REQUIRED
    reason = "Evaluation incomplete"
    evaluated_value = candidate.normalized_value or candidate.raw_value

    if candidate.status == "REVIEW_REQUIRED":
        status = LegalStatus.REVIEW_REQUIRED
        reason = "Extracted evidence requires human review"
    elif candidate.status == "NOT_DETECTED":
        if rule.evaluation_type in ("REQUIRED_DECLARATION", "REQUIRED_ROLE"):
            if evidence_sufficiency == "SUFFICIENT_FOR_ABSENCE_EVALUATION":
                status = LegalStatus.FAIL
                reason = "Required declaration was not detected across the complete usable evidence set for an absence-eligible inspection plan."
            else:
                status = LegalStatus.REVIEW_REQUIRED
                reason = "Evidence not detected in this image; may exist elsewhere. Inspection plan is not sufficient for absence."
        else:
            status = LegalStatus.REVIEW_REQUIRED
            reason = "Evidence not detected in this image; may exist elsewhere"
    elif candidate.status == "DETECTED":
        # Process based on evaluation type
        if rule.evaluation_type == "REQUIRED_DECLARATION":
            status = LegalStatus.PASS
            reason = rule.parameters.get("pass_reason", f"{rule.field} declaration evidence was detected for this rule.")
        elif rule.evaluation_type == "VALUE_PRESENT":
            if evaluated_value:
                status = LegalStatus.PASS
                reason = "Value is present"
            else:
                status = LegalStatus.FAIL
                reason = "Value is missing despite field detection"
        elif rule.evaluation_type == "ALLOWED_UNIT":
            allowed_units = rule.parameters.get("allowed_units", [])
            # NetQuantityNormalized has a 'unit' field. 
            # We assume evaluated_value is the normalized object.
            if hasattr(evaluated_value, 'unit') and evaluated_value.unit in allowed_units:
                status = LegalStatus.PASS
                reason = f"Unit '{evaluated_value.unit}' is allowed"
            elif hasattr(evaluated_value, 'unit'):
                status = LegalStatus.FAIL
                reason = f"Unit '{evaluated_value.unit}' is not in allowed list: {allowed_units}"
            else:
                status = LegalStatus.REVIEW_REQUIRED
                reason = "Unit cannot be evaluated"
        elif rule.evaluation_type == "REQUIRED_SUBFIELD":
            subfield = rule.parameters.get("subfield")
            if not subfield:
                status = LegalStatus.REVIEW_REQUIRED
                reason = "Rule configuration error: missing subfield"
            else:
                has_subfield = False
                if evaluated_value and hasattr(evaluated_value, subfield):
                    if getattr(evaluated_value, subfield) is not None:
                        has_subfield = True
                
                if has_subfield:
                    status = LegalStatus.PASS
                    reason = rule.parameters.get("pass_reason", f"Subfield {subfield} detected.")
                else:
                    if evidence_sufficiency == "SUFFICIENT_FOR_ABSENCE_EVALUATION":
                        status = LegalStatus.FAIL
                        reason = f"Required subfield '{subfield}' was not detected across the complete usable evidence set for an absence-eligible inspection plan."
                    else:
                        status = LegalStatus.REVIEW_REQUIRED
                        reason = f"Subfield '{subfield}' not detected in this image; may exist elsewhere. Inspection plan is not sufficient for absence."
        elif rule.evaluation_type == "REQUIRED_ROLE":
            status = LegalStatus.PASS
            reason = rule.parameters.get("pass_reason", f"{rule.field} role evidence was detected for this rule.")
        else:
            status = LegalStatus.REVIEW_REQUIRED
            reason = f"Unknown evaluation type: {rule.evaluation_type}"
            
    return RuleEvaluationResult(
        rule_id=rule.rule_id,
        rule_version=rule.rule_version,
        field=rule.field,
        status=status,
        reason=reason,
        evaluated_value=evaluated_value,
        evidence_ids=candidate.evidence_ids,
        capture_ids=candidate.capture_ids,
        reference_date=reference_date,
        source_reference=rule.source_reference,
        source_url=rule.source_url
    )
