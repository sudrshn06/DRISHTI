from typing import List, Dict

from app.schemas.compliance import RuleDefinition
from app.schemas.ocr import FieldCandidate
from app.schemas.applicability import ApplicabilityStatus, ApplicabilityDecision
from decimal import Decimal

def get_legal_denominator_quantity(qty_value: float, qty_unit: str):
    """
    Returns the numeric quantity in the legally required denominator unit.
    Returns None if the legal text is ambiguous (e.g., exactly 1 kg/L/m).
    """
    val = Decimal(str(qty_value))
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
            return qty_in_g
        elif qty_in_g > Decimal('1000'):
            return qty_in_g / Decimal('1000')
        else:
            return None # Ambiguous exactly 1kg
            
    if unit in ["ml", "mls", "milliliter", "millilitre", "milliliters", "millilitres"]:
        qty_in_ml = val
    elif unit in ["l", "liter", "litre", "liters", "litres"]:
        qty_in_ml = val * Decimal('1000')
    else:
        qty_in_ml = None
        
    if qty_in_ml is not None:
        if qty_in_ml < Decimal('1000'):
            return qty_in_ml
        elif qty_in_ml > Decimal('1000'):
            return qty_in_ml / Decimal('1000')
        else:
            return None # Ambiguous exactly 1L
            
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
            return qty_in_cm
        elif qty_in_cm > Decimal('100'):
            return qty_in_cm / Decimal('100')
        else:
            return None # Ambiguous exactly 1m
            
    if unit in ["u", "n", "number", "unit", "units", "piece", "pieces", "pcs"]:
        return val
        
    return None


def evaluate_applicability(
    rules: List[RuleDefinition], 
    candidates: List[FieldCandidate], 
    product_category: str,
    product_origin: str = "UNKNOWN",
    regulatory_category: str = "UNKNOWN",
    is_electronic: str = "UNKNOWN",
    package_structure: str = "UNKNOWN",
    alcohol_context: str = "UNKNOWN",
    date_regulatory_regime: str = "UNKNOWN",
    date_package_exemption: str = "UNKNOWN"
) -> Dict[str, ApplicabilityDecision]:
    """
    Evaluates the applicability of each rule based on explicit inspection context.
    Returns a dictionary mapping rule_id to its ApplicabilityDecision.
    """
    decisions = {}
    
    # Pre-process candidates to find any contradiction with explicit context
    business_candidates = [c for c in candidates if c.field == "MANUFACTURER_PACKER_IMPORTER" and c.status in ("DETECTED", "REVIEW_REQUIRED")]
    has_importer_evidence = any(c.normalized_value and getattr(c.normalized_value, "role", "") == "IMPORTER" for c in business_candidates)
    
    for rule in rules:
        # Base product scope check
        if rule.product_scope != "ALL" and rule.product_scope != product_category:
            decisions[rule.rule_id] = ApplicabilityDecision(
                rule_id=rule.rule_id,
                status=ApplicabilityStatus.NOT_APPLICABLE,
                reason=f"Product category '{product_category}' does not match rule scope '{rule.product_scope}'.",
                evidence_used=[]
            )
            continue

        # Food Exception (Explanation III of Rule 6(1)(a))
        if regulatory_category == "FOOD" and rule.rule_id in ("MANUFACTURER_PACKER_DECLARATION_PRESENCE", "IMPORTER_DECLARATION_PRESENCE"):
            decisions[rule.rule_id] = ApplicabilityDecision(
                rule_id=rule.rule_id,
                status=ApplicabilityStatus.NOT_APPLICABLE,
                reason="LMPC business declaration provision is redirected to the food regulatory regime (FSSAI). Corresponding FSSAI evaluation is not implemented yet.",
                evidence_used=[]
            )
            continue
            
        # Category unknown fallback for business rules
        if regulatory_category == "UNKNOWN" and rule.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE":
            decisions[rule.rule_id] = ApplicabilityDecision(
                rule_id=rule.rule_id,
                status=ApplicabilityStatus.REVIEW_REQUIRED,
                reason="Regulatory product class is UNKNOWN; cannot safely determine if Food Exception applies.",
                evidence_used=[],
                missing_context=["REGULATORY_PRODUCT_CLASS"]
            )
            continue

        # Importer Logic
        if rule.rule_id == "IMPORTER_DECLARATION_PRESENCE":
            if product_origin == "DOMESTIC":
                if has_importer_evidence:
                    # Contradiction check
                    # Extract evidence IDs for the contradicting evidence
                    contradicting_evidence_ids = []
                    for c in business_candidates:
                        if c.normalized_value and getattr(c.normalized_value, "role", "") == "IMPORTER":
                            contradicting_evidence_ids.extend(c.evidence_ids)
                            
                    decisions[rule.rule_id] = ApplicabilityDecision(
                        rule_id=rule.rule_id,
                        status=ApplicabilityStatus.REVIEW_REQUIRED,
                        reason="Declared importer evidence conflicts with explicit domestic origin context.",
                        evidence_used=contradicting_evidence_ids
                    )
                else:
                    decisions[rule.rule_id] = ApplicabilityDecision(
                        rule_id=rule.rule_id,
                        status=ApplicabilityStatus.NOT_APPLICABLE,
                        reason="Explicit origin is DOMESTIC.",
                        evidence_used=[]
                    )
            elif product_origin == "IMPORTED":
                if regulatory_category == "UNKNOWN":
                    decisions[rule.rule_id] = ApplicabilityDecision(
                        rule_id=rule.rule_id,
                        status=ApplicabilityStatus.REVIEW_REQUIRED,
                        reason="Regulatory product class is UNKNOWN; cannot safely determine if Food Exception applies.",
                        evidence_used=[],
                        missing_context=["REGULATORY_PRODUCT_CLASS"]
                    )
                else:
                    decisions[rule.rule_id] = ApplicabilityDecision(
                        rule_id=rule.rule_id,
                        status=ApplicabilityStatus.APPLICABLE,
                        reason="Explicit origin is IMPORTED.",
                        evidence_used=[]
                    )
            else:
                # product_origin == "UNKNOWN"
                missing = ["PRODUCT_ORIGIN"]
                if regulatory_category == "UNKNOWN":
                    missing.append("REGULATORY_PRODUCT_CLASS")
                decisions[rule.rule_id] = ApplicabilityDecision(
                    rule_id=rule.rule_id,
                    status=ApplicabilityStatus.REVIEW_REQUIRED,
                    reason="Product origin is UNKNOWN; cannot determine if importer declaration is required.",
                    evidence_used=[],
                    missing_context=missing
                )
            continue
            
        elif rule.rule_id == "MANUFACTURER_PACKER_DECLARATION_PRESENCE":
            # For NON_FOOD, manufacturer/packer is generally applicable regardless of origin
            # because "imported does not automatically switch off manufacturer/packer"
            decisions[rule.rule_id] = ApplicabilityDecision(
                rule_id=rule.rule_id,
                status=ApplicabilityStatus.APPLICABLE,
                reason="Manufacturer/Packer declaration is applicable under LMPC Rule 6(1)(a) for non-food packages.",
                evidence_used=[]
            )
            continue
            
        # Country of Origin Logic
        elif rule.rule_id == "COUNTRY_OF_ORIGIN_DECLARATION_PRESENCE":
            if product_origin == "IMPORTED":
                decisions[rule.rule_id] = ApplicabilityDecision(
                    rule_id=rule.rule_id,
                    status=ApplicabilityStatus.APPLICABLE,
                    reason="Explicit origin is IMPORTED. Country of origin declaration is required.",
                    evidence_used=[]
                )
            elif product_origin == "DOMESTIC":
                decisions[rule.rule_id] = ApplicabilityDecision(
                    rule_id=rule.rule_id,
                    status=ApplicabilityStatus.NOT_APPLICABLE,
                    reason="Explicit origin is DOMESTIC. Not strictly required under LMPC Rule 6(1)(aa).",
                    evidence_used=[]
                )
            else:
                decisions[rule.rule_id] = ApplicabilityDecision(
                    rule_id=rule.rule_id,
                    status=ApplicabilityStatus.REVIEW_REQUIRED,
                    reason="Product origin is UNKNOWN; cannot determine if country of origin declaration is required.",
                    evidence_used=[],
                    missing_context=["PRODUCT_ORIGIN"]
                )
            continue
            
        elif rule.rule_id == "COMMON_GENERIC_NAME_DECLARATION_PRESENCE":
            decisions[rule.rule_id] = ApplicabilityDecision(
                rule_id=rule.rule_id,
                status=ApplicabilityStatus.APPLICABLE,
                reason="Common/Generic name declaration is generally applicable. Electronic QR provisos are evaluated during candidate matching.",
                evidence_used=[]
            )
            continue
            
        elif rule.rule_id == "MONTH_YEAR_DECLARATION_PRESENCE":
            if date_regulatory_regime in ("FOOD", "CERTIFIED_SEED", "COSMETIC"):
                decisions[rule.rule_id] = ApplicabilityDecision(
                    rule_id=rule.rule_id,
                    status=ApplicabilityStatus.NOT_APPLICABLE,
                    reason=f"LMPC month/year requirement is deferred for {date_regulatory_regime}.",
                    evidence_used=[]
                )
            elif date_package_exemption in ("BIDI_OR_INCENSE", "PSU_DOMESTIC_LPG_14_2_OR_5KG"):
                decisions[rule.rule_id] = ApplicabilityDecision(
                    rule_id=rule.rule_id,
                    status=ApplicabilityStatus.NOT_APPLICABLE,
                    reason=f"Month/year requirement is exempted under context: {date_package_exemption}.",
                    evidence_used=[]
                )
            elif date_regulatory_regime == "UNKNOWN" or (date_package_exemption == "UNKNOWN" and date_regulatory_regime == "GENERAL"):
                missing = []
                if date_regulatory_regime == "UNKNOWN":
                    missing.append("DATE_REGULATORY_REGIME")
                if date_package_exemption == "UNKNOWN" and date_regulatory_regime in ("GENERAL", "UNKNOWN"):
                    missing.append("DATE_PACKAGE_EXEMPTION")
                    
                decisions[rule.rule_id] = ApplicabilityDecision(
                    rule_id=rule.rule_id,
                    status=ApplicabilityStatus.REVIEW_REQUIRED,
                    reason="Date regime and/or exemption context is UNKNOWN; cannot determine if Month/Year of Manufacture is legally required.",
                    evidence_used=[],
                    missing_context=missing
                )
            else:
                decisions[rule.rule_id] = ApplicabilityDecision(
                    rule_id=rule.rule_id,
                    status=ApplicabilityStatus.APPLICABLE,
                    reason="Month/year declaration is applicable under LMPC Rule 6(1)(d).",
                    evidence_used=[]
                )
            continue
            
        elif rule.rule_id in ("UNIT_SALE_PRICE_DECLARATION_PRESENCE", "UNIT_SALE_PRICE_DENOMINATOR_CONSISTENCY"):
            if alcohol_context == "ALCOHOLIC":
                decisions[rule.rule_id] = ApplicabilityDecision(
                    rule_id=rule.rule_id,
                    status=ApplicabilityStatus.NOT_APPLICABLE,
                    reason="USP evaluation under LMPC Rule 6(11) is not performed for this context; applicable State Excise laws and rules govern packages containing alcoholic beverages or spirituous liquor within the State in which they are manufactured.",
                    evidence_used=[]
                )
            elif package_structure in ("COMBINATION", "GROUP", "MULTI_PIECE"):
                decisions[rule.rule_id] = ApplicabilityDecision(
                    rule_id=rule.rule_id,
                    status=ApplicabilityStatus.NOT_APPLICABLE,
                    reason=f"Unit Sale Price is exempted for {package_structure} packages under LMPC Rule 26.",
                    evidence_used=[]
                )
            elif alcohol_context == "UNKNOWN" or package_structure == "UNKNOWN":
                missing = []
                if alcohol_context == "UNKNOWN":
                    missing.append("ALCOHOL_CONTEXT")
                if package_structure == "UNKNOWN":
                    missing.append("PACKAGE_STRUCTURE")
                    
                decisions[rule.rule_id] = ApplicabilityDecision(
                    rule_id=rule.rule_id,
                    status=ApplicabilityStatus.REVIEW_REQUIRED,
                    reason="Alcohol and/or package structure context is UNKNOWN; cannot determine if Unit Sale Price is legally required.",
                    evidence_used=[],
                    missing_context=missing
                )
            else:
                # SINGLE, NON_ALCOHOLIC -> Evaluate RSP == USP exemption
                mrp_cands = [c for c in candidates if c.field == "MRP" and c.status == "DETECTED"]
                net_cands = [c for c in candidates if c.field == "NET_QUANTITY" and c.status == "DETECTED"]
                
                if not mrp_cands or not net_cands:
                    decisions[rule.rule_id] = ApplicabilityDecision(
                        rule_id=rule.rule_id,
                        status=ApplicabilityStatus.REVIEW_REQUIRED,
                        reason="Missing MRP or Net Quantity evidence. Cannot deterministically establish if Retail Sale Price == Unit Sale Price exemption applies.",
                        evidence_used=[]
                    )
                    continue
                    
                if len(mrp_cands) > 1 or len(net_cands) > 1:
                    decisions[rule.rule_id] = ApplicabilityDecision(
                        rule_id=rule.rule_id,
                        status=ApplicabilityStatus.REVIEW_REQUIRED,
                        reason="Multiple conflicting MRP or Net Quantity candidates. Cannot deterministically establish RSP == USP exemption.",
                        evidence_used=[]
                    )
                    continue
                    
                mrp_cand = mrp_cands[0]
                net_cand = net_cands[0]
                
                mrp_val = getattr(mrp_cand.normalized_value, "amount", None)
                qty_val = getattr(net_cand.normalized_value, "value", None)
                qty_unit = getattr(net_cand.normalized_value, "unit", None)
                
                if mrp_val is None or qty_val is None or not qty_unit:
                    decisions[rule.rule_id] = ApplicabilityDecision(
                        rule_id=rule.rule_id,
                        status=ApplicabilityStatus.REVIEW_REQUIRED,
                        reason="Malformed MRP or Net Quantity evidence. Cannot deterministically establish RSP == USP exemption.",
                        evidence_used=[]
                    )
                    continue
                    
                denom_qty = get_legal_denominator_quantity(qty_val, qty_unit)
                
                if denom_qty is None:
                    decisions[rule.rule_id] = ApplicabilityDecision(
                        rule_id=rule.rule_id,
                        status=ApplicabilityStatus.REVIEW_REQUIRED,
                        reason="Ambiguous legally required denominator (e.g. exactly 1kg/1L/1m). Cannot deterministically establish RSP == USP equality.",
                        evidence_used=[]
                    )
                    continue
                    
                # Calculate USP and check equality
                try:
                    usp_calculated = Decimal(str(mrp_val)) / denom_qty
                    if usp_calculated == Decimal(str(mrp_val)):
                        decisions[rule.rule_id] = ApplicabilityDecision(
                            rule_id=rule.rule_id,
                            status=ApplicabilityStatus.NOT_APPLICABLE,
                            reason="Retail Sale Price equals Unit Sale Price based on calculated evidence. Declaration is exempted under Rule 6(11) proviso.",
                            evidence_used=mrp_cand.evidence_ids + net_cand.evidence_ids
                        )
                        continue
                except Exception:
                    pass
                    
                decisions[rule.rule_id] = ApplicabilityDecision(
                    rule_id=rule.rule_id,
                    status=ApplicabilityStatus.APPLICABLE,
                    reason="Single, non-alcoholic packages require Unit Sale Price declaration. RSP == USP exemption does not apply.",
                    evidence_used=[]
                )
            continue
            
        # For all other rules (e.g. MRP, Net Quantity, Consumer Care)
        decisions[rule.rule_id] = ApplicabilityDecision(
            rule_id=rule.rule_id,
            status=ApplicabilityStatus.APPLICABLE,
            reason="Rule is generally applicable to this product category.",
            evidence_used=[]
        )
        
    return decisions
