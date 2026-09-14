from datetime import date
from typing import List, Optional

from app.schemas.compliance import RuleEvaluationResult, LegalStatus
from app.schemas.ocr import FieldCandidate
from app.services.rule_loader import load_production_rules
from app.services.rule_engine import get_applicable_rules, evaluate_candidate

from app.services.applicability_model import evaluate_applicability
from app.schemas.applicability import ApplicabilityStatus
from app.services.declaration_validity_service import evaluate_declaration_validity
from decimal import Decimal

def get_expected_usp_denominator(qty_val: float, qty_unit: str):
    """
    Returns the legally expected denominator unit based on Rule 6(11).
    Returns None if ambiguous (exactly 1kg/1L/1m).
    """
    val = Decimal(str(qty_val))
    unit = qty_unit.lower().strip()
    
    if unit in ["g", "gm", "gms", "gram", "grams"]:
        qty_in_g = val
    elif unit in ["kg", "kgs", "kilogram", "kilograms"]:
        qty_in_g = val * Decimal('1000')
    elif unit in ["mg", "mgs", "milligram", "milligrams"]:
        qty_in_g = val / Decimal('1000')
    else:
        qty_in_g = None
        
    if qty_in_g is not None:
        if qty_in_g < Decimal('1000'):
            return "g"
        elif qty_in_g > Decimal('1000'):
            return "kg"
        else:
            return None
            
    if unit in ["ml", "mls", "milliliter", "millilitre", "milliliters", "millilitres"]:
        qty_in_ml = val
    elif unit in ["l", "liter", "litre", "liters", "litres"]:
        qty_in_ml = val * Decimal('1000')
    else:
        qty_in_ml = None
        
    if qty_in_ml is not None:
        if qty_in_ml < Decimal('1000'):
            return "ml"
        elif qty_in_ml > Decimal('1000'):
            return "l"
        else:
            return None
            
    if unit in ["cm", "cms", "centimeter", "centimetre", "centimeters", "centimetres"]:
        qty_in_cm = val
    elif unit in ["m", "meter", "metre", "meters", "metres"]:
        qty_in_cm = val * Decimal('100')
    elif unit in ["mm", "mms", "millimeter", "millimetre", "millimeters", "millimetres"]:
        qty_in_cm = val / Decimal('10')
    else:
        qty_in_cm = None
        
    if qty_in_cm is not None:
        if qty_in_cm < Decimal('100'):
            return "cm"
        elif qty_in_cm > Decimal('100'):
            return "m"
        else:
            return None
            
    if unit in ["u", "n", "number", "unit", "units", "piece", "pieces", "pcs"]:
        return "unit"
        
    return None

def orchestrate_compliance(
    candidates: List[FieldCandidate],
    reference_date: date,
    product_category: str,
    product_origin: str = "UNKNOWN",
    regulatory_category: str = "UNKNOWN",
    is_electronic: str = "UNKNOWN",
    package_structure: str = "UNKNOWN",
    alcohol_context: str = "UNKNOWN",
    date_regulatory_regime: str = "UNKNOWN",
    date_package_exemption: str = "UNKNOWN",
    evidence_sufficiency: str = "INSUFFICIENT_FOR_ABSENCE_EVALUATION",
    inspection_complete: bool = False,
    validity_candidates: Optional[List[FieldCandidate]] = None,
) -> List[RuleEvaluationResult]:
    """
    Orchestrates the compliance evaluation process.
    Matches extracted candidates to applicable production rules.
    """
    rules = load_production_rules()
    applicable_rules = get_applicable_rules(rules, reference_date)
    
    # 1. Evaluate applicability for all rules
    applicability_decisions = evaluate_applicability(
        applicable_rules, 
        candidates, 
        product_category,
        product_origin,
        regulatory_category,
        is_electronic,
        package_structure,
        alcohol_context,
        date_regulatory_regime,
        date_package_exemption
    )
    
    results = []
    
    for rule in applicable_rules:
        decision = applicability_decisions.get(rule.rule_id)
        if not decision:
            continue
            
        if decision.status == ApplicabilityStatus.NOT_APPLICABLE:
            # Short-circuit: do not run compliance logic for non-applicable rules
            results.append(
                RuleEvaluationResult(
                    rule_id=rule.rule_id,
                    rule_version=rule.rule_version,
                    field=rule.field,
                    status=LegalStatus.NOT_APPLICABLE,
                    reason=decision.reason,
                    reference_date=reference_date,
                    source_reference=rule.source_reference,
                    source_url=rule.source_url,
                    capture_ids=[],
                    applicability=decision
                )
            )
            continue
            
        if decision.status == ApplicabilityStatus.REVIEW_REQUIRED:
            # Short-circuit: if applicability is ambiguous, the whole legal result is ambiguous
            results.append(
                RuleEvaluationResult(
                    rule_id=rule.rule_id,
                    rule_version=rule.rule_version,
                    field=rule.field,
                    status=LegalStatus.REVIEW_REQUIRED,
                    reason=f"Applicability requires review: {decision.reason}",
                    reference_date=reference_date,
                    source_reference=rule.source_reference,
                    source_url=rule.source_url,
                    capture_ids=[],
                    applicability=decision
                )
            )
            continue
            
        # Match candidates by exact DRISHTI field
        matching_candidates = [c for c in candidates if c.field == rule.field]
        
        # If the rule has a REQUIRED_ROLE constraint, filter candidates by that role
        if rule.evaluation_type == "REQUIRED_ROLE":
            allowed_roles = rule.parameters.get("allowed_roles", [])
            matching_candidates = [
                c for c in matching_candidates 
                if c.normalized_value and getattr(c.normalized_value, "role", None) in allowed_roles
            ]
            
        # If the rule is for MONTH_YEAR_DECLARATION_PRESENCE, filter candidates by allowed subtypes
        if rule.rule_id == "MONTH_YEAR_DECLARATION_PRESENCE":
            allowed_subtypes = rule.parameters.get("allowed_subtypes", [])
            filtered_candidates = []
            for c in matching_candidates:
                if c.normalized_value and getattr(c.normalized_value, "type", None) in allowed_subtypes:
                    filtered_candidates.append(c)
                elif c.status == "REVIEW_REQUIRED":
                    # Keep unparsed/malformed candidates for review
                    filtered_candidates.append(c)
            matching_candidates = filtered_candidates
            
        if not matching_candidates:
            # Missing candidate behavior
            if decision.status == ApplicabilityStatus.REVIEW_REQUIRED:
                status = LegalStatus.REVIEW_REQUIRED
                reason = f"Applicability is ambiguous: {decision.reason}. Cannot safely fail."
            elif rule.evaluation_type in ("REQUIRED_DECLARATION", "REQUIRED_ROLE") and evidence_sufficiency == "SUFFICIENT_FOR_ABSENCE_EVALUATION":
                status = LegalStatus.FAIL
                reason = "Required declaration was not detected across the complete usable evidence set for an absence-eligible inspection plan."
            else:
                status = LegalStatus.REVIEW_REQUIRED
                reason = "Insufficient evidence: No candidate found for this field."
                
            # Apply electronic QR proviso logic if the printed name failed or requires review
            if rule.rule_id == "COMMON_GENERIC_NAME_DECLARATION_PRESENCE":
                if is_electronic == "ELECTRONIC":
                    if reference_date >= date(2023, 6, 23):
                        # Post-2023 QR Proviso
                        qr_candidates = [c for c in candidates if c.field == "COMMON_NAME_QR_INSTRUCTION" and c.status in ("DETECTED", "REVIEW_REQUIRED")]
                        if qr_candidates:
                            status = LegalStatus.REVIEW_REQUIRED
                            reason = "Printed name missing, but qualifying QR instruction detected. QR content unverified."
                        elif evidence_sufficiency == "SUFFICIENT_FOR_ABSENCE_EVALUATION":
                            status = LegalStatus.FAIL
                            reason = "Printed name missing, and no qualifying QR instruction found, across sufficient evidence."
                        else:
                            status = LegalStatus.REVIEW_REQUIRED
                            reason = "Printed name missing and no QR instruction found, but inspection is incomplete."
                    elif date(2022, 7, 15) < reference_date < date(2023, 6, 23):
                        # Historical 2022 QR Proviso
                        status = LegalStatus.REVIEW_REQUIRED
                        reason = "Printed name missing during historical 2022 QR proviso period. Eligibility cannot be established from explicit context."
                elif is_electronic == "UNKNOWN":
                    if status == LegalStatus.FAIL:
                        status = LegalStatus.REVIEW_REQUIRED
                        reason = "Printed name missing, and electronic status is UNKNOWN. Cannot safely fail because electronic QR exception might apply."
                        if decision:
                            if "IS_ELECTRONIC" not in decision.missing_context:
                                decision.missing_context.append("IS_ELECTRONIC")

            results.append(
                RuleEvaluationResult(
                    rule_id=rule.rule_id,
                    rule_version=rule.rule_version,
                    field=rule.field,
                    status=status,
                    reason=reason,
                    reference_date=reference_date,
                    source_reference=rule.source_reference,
                    source_url=rule.source_url,
                    capture_ids=[],
                    applicability=decision
                )
            )
            continue
            
        # Prioritize strong DETECTED candidates to avoid false conflicts with weak fallback unparsed evidence
        if rule.rule_id != "MONTH_YEAR_DECLARATION_PRESENCE" and rule.evaluation_type != "REQUIRED_ROLE":
            detected_cands = [c for c in matching_candidates if c.status == "DETECTED"]
            if detected_cands:
                filtered_cands = list(detected_cands)
                for c in matching_candidates:
                    if c.status == "REVIEW_REQUIRED":
                        # Only suppress weak evidence if we can definitively prove it originates from the same
                        # declaration as a DETECTED candidate (via overlapping evidence IDs).
                        shares_evidence = False
                        if c.evidence_ids:
                            for dc in detected_cands:
                                if dc.evidence_ids and set(c.evidence_ids).intersection(set(dc.evidence_ids)):
                                    shares_evidence = True
                                    break
                        if not shares_evidence:
                            filtered_cands.append(c)
                    elif c.status != "DETECTED":
                        filtered_cands.append(c)
                matching_candidates = filtered_cands
            
        if len(matching_candidates) > 1:
            # Check for conflicts
            
            # Determine capture provenance for messaging
            all_capture_ids = set()
            for c in matching_candidates:
                if getattr(c, "capture_ids", None):
                    all_capture_ids.update(c.capture_ids)
            
            if len(all_capture_ids) == 1:
                conflict_reason = "Conflicting declaration evidence was detected within this capture."
            elif len(all_capture_ids) > 1:
                conflict_reason = "Conflicting declaration evidence was detected across captures."
            else:
                conflict_reason = "Conflicting declaration evidence was detected."
                
            if rule.rule_id == "MONTH_YEAR_DECLARATION_PRESENCE":
                has_conflict = False
                # Group by subtype
                from collections import defaultdict
                grouped = defaultdict(list)
                for c in matching_candidates:
                    stype = getattr(c.normalized_value, "type", "UNKNOWN") if c.normalized_value else "UNKNOWN"
                    grouped[stype].append(c)
                    
                for stype, cands in grouped.items():
                    if len(cands) > 1:
                        def _comp(c):
                            d = c.model_dump(exclude={'evidence_ids', 'confidence'})
                            return str(d)
                        first_rep = _comp(cands[0])
                        if any(_comp(c) != first_rep for c in cands[1:]):
                            has_conflict = True
                            break
                            
                if has_conflict:
                    results.append(
                        RuleEvaluationResult(
                            rule_id=rule.rule_id,
                            rule_version=rule.rule_version,
                            field=rule.field,
                            status=LegalStatus.REVIEW_REQUIRED,
                            reason=conflict_reason,
                            reference_date=reference_date,
                            source_reference=rule.source_reference,
                            source_url=rule.source_url,
                            applicability=decision
                        )
                    )
                    continue
                else:
                    # No conflicts within any subtype, pick the first one that is DETECTED if possible
                    target_candidate = next((c for c in matching_candidates if c.status == "DETECTED"), matching_candidates[0])
            elif rule.evaluation_type == "REQUIRED_ROLE":
                has_conflict = False
                from collections import defaultdict
                grouped = defaultdict(list)
                for c in matching_candidates:
                    role = getattr(c.normalized_value, "role", "UNKNOWN") if c.normalized_value else "UNKNOWN"
                    grouped[role].append(c)
                    
                for role, cands in grouped.items():
                    if len(cands) > 1:
                        def _comp(c):
                            d = c.model_dump(exclude={'evidence_ids', 'confidence'})
                            return str(d)
                        first_rep = _comp(cands[0])
                        if any(_comp(c) != first_rep for c in cands[1:]):
                            has_conflict = True
                            break
                            
                if has_conflict:
                    results.append(
                        RuleEvaluationResult(
                            rule_id=rule.rule_id,
                            rule_version=rule.rule_version,
                            field=rule.field,
                            status=LegalStatus.REVIEW_REQUIRED,
                            reason=conflict_reason,
                            reference_date=reference_date,
                            source_reference=rule.source_reference,
                            source_url=rule.source_url,
                            applicability=decision
                        )
                    )
                    continue
                else:
                    target_candidate = next((c for c in matching_candidates if c.status == "DETECTED"), matching_candidates[0])
            else:
                def _comparable(c):
                    d = c.model_dump(exclude={'evidence_ids', 'confidence'})
                    return str(d)
                    
                first_rep = _comparable(matching_candidates[0])
                has_conflict = any(_comparable(c) != first_rep for c in matching_candidates[1:])
                
                if has_conflict:
                    results.append(
                        RuleEvaluationResult(
                            rule_id=rule.rule_id,
                            rule_version=rule.rule_version,
                            field=rule.field,
                            status=LegalStatus.REVIEW_REQUIRED,
                            reason=conflict_reason,
                            reference_date=reference_date,
                            source_reference=rule.source_reference,
                            source_url=rule.source_url,
                            applicability=decision
                        )
                    )
                    continue
                else:
                    target_candidate = matching_candidates[0]
        else:
            target_candidate = matching_candidates[0]
            
        # Evaluate the deterministic candidate
        result = evaluate_candidate(
            target_candidate,
            rule,
            reference_date,
            product_category,
            evidence_sufficiency
        )
        
        # Apply electronic QR proviso logic if the printed name failed or requires review
        if rule.rule_id == "COMMON_GENERIC_NAME_DECLARATION_PRESENCE" and result.status in (LegalStatus.FAIL, LegalStatus.REVIEW_REQUIRED) and target_candidate.status == "NOT_DETECTED":
            if is_electronic == "ELECTRONIC":
                if reference_date >= date(2023, 6, 23):
                    # Post-2023 QR Proviso
                    qr_candidates = [c for c in candidates if c.field == "COMMON_NAME_QR_INSTRUCTION" and c.status in ("DETECTED", "REVIEW_REQUIRED")]
                    if qr_candidates:
                        result.status = LegalStatus.REVIEW_REQUIRED
                        result.reason = "Printed name missing, but qualifying QR instruction detected. QR content unverified."
                    elif evidence_sufficiency == "SUFFICIENT_FOR_ABSENCE_EVALUATION":
                        result.status = LegalStatus.FAIL
                        result.reason = "Printed name missing, and no qualifying QR instruction found, across sufficient evidence."
                    else:
                        result.status = LegalStatus.REVIEW_REQUIRED
                        result.reason = "Printed name missing and no QR instruction found, but inspection is incomplete."
                elif date(2022, 7, 15) < reference_date < date(2023, 6, 23):
                    # Historical 2022 QR Proviso
                    result.status = LegalStatus.REVIEW_REQUIRED
                    result.reason = "Printed name missing during historical 2022 QR proviso period. Eligibility cannot be established from explicit context."
            elif is_electronic == "UNKNOWN":
                if result.status == LegalStatus.FAIL:
                    result.status = LegalStatus.REVIEW_REQUIRED
                    result.reason = "Printed name missing, and electronic status is UNKNOWN. Cannot safely fail because electronic QR exception might apply."
                    if result.applicability:
                        if "IS_ELECTRONIC" not in result.applicability.missing_context:
                            result.applicability.missing_context.append("IS_ELECTRONIC")
                    
        # Apply UNIT_SALE_PRICE_DENOMINATOR_CONSISTENCY logic
        if rule.rule_id == "UNIT_SALE_PRICE_DENOMINATOR_CONSISTENCY" and result.status == LegalStatus.PASS:
            net_cands = [c for c in candidates if c.field == "NET_QUANTITY" and c.status == "DETECTED"]
            if not net_cands:
                result.status = LegalStatus.REVIEW_REQUIRED
                result.reason = "Missing Net Quantity evidence. Cannot evaluate denominator compatibility."
            elif len(net_cands) > 1:
                result.status = LegalStatus.REVIEW_REQUIRED
                result.reason = "Multiple conflicting Net Quantity candidates. Cannot safely evaluate denominator compatibility."
            else:
                net_cand = net_cands[0]
                qty_val = getattr(net_cand.normalized_value, "value", None)
                qty_unit = getattr(net_cand.normalized_value, "unit", None)
                
                if qty_val is None or not qty_unit:
                    result.status = LegalStatus.REVIEW_REQUIRED
                    result.reason = "Malformed Net Quantity evidence. Cannot evaluate denominator compatibility."
                else:
                    expected = get_expected_usp_denominator(qty_val, qty_unit)
                    if expected is None:
                        result.status = LegalStatus.REVIEW_REQUIRED
                        result.reason = "Legally ambiguous denominator boundary (exactly 1kg/1L/1m). Cannot deterministically evaluate consistency."
                    else:
                        actual = getattr(result.evaluated_value, "per_unit", "").lower()
                        # Normalize actual
                        if actual in ["g", "gm", "gms", "gram", "grams"]:
                            actual_norm = "g"
                        elif actual in ["kg", "kgs", "kilogram", "kilograms"]:
                            actual_norm = "kg"
                        elif actual in ["ml", "mls", "milliliter", "millilitre"]:
                            actual_norm = "ml"
                        elif actual in ["l", "liter", "litre"]:
                            actual_norm = "l"
                        elif actual in ["cm", "cms", "centimeter", "centimetre"]:
                            actual_norm = "cm"
                        elif actual in ["m", "meter", "metre"]:
                            actual_norm = "m"
                        elif actual in ["u", "n", "number", "unit", "piece", "pcs"]:
                            actual_norm = "unit"
                        else:
                            actual_norm = actual
                            
                        if actual_norm == expected:
                            result.status = LegalStatus.PASS
                            result.reason = f"USP denominator '{actual}' is compatible with expected '{expected}'."
                        else:
                            result.status = LegalStatus.FAIL
                            result.reason = f"USP denominator '{actual}' is incompatible with expected '{expected}' for net quantity {qty_val}{qty_unit}."
                            
                    
        result.applicability = decision
        results.append(result)
        
    results.extend(evaluate_declaration_validity(
        candidates=validity_candidates if validity_candidates is not None else candidates,
        applicable_rules=applicable_rules,
        applicability_decisions=applicability_decisions,
        reference_date=reference_date,
        evidence_sufficiency=evidence_sufficiency,
    ))
    return results
