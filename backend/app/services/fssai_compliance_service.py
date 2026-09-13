import re
from datetime import date
from typing import List, Optional
from app.schemas.compliance import RuleEvaluationResult, LegalStatus
from app.schemas.ocr import FieldCandidate

def evaluate_fssai_compliance(
    candidates: List[FieldCandidate],
    reference_date: date,
    evidence_sufficiency: str = "INSUFFICIENT_FOR_ABSENCE_EVALUATION",
    is_single_ingredient: Optional[bool] = None,
    is_nutrition_exempt: Optional[bool] = None,
    veg_nonveg_exempt: Optional[bool] = None,
    package_area_exemption: Optional[bool] = None,
    validity_candidates: Optional[List[FieldCandidate]] = None,
) -> List[RuleEvaluationResult]:
    """
    Evaluates FSSAI/Food Label compliance rules on extracted candidates.
    Supports FSSAI 2020 base regulations and handles date boundaries for amendments and FSSAI Directions.
    """
    results = []
    
    # Help function to find candidate by field
    def find_cand(field: str) -> Optional[FieldCandidate]:
        for c in candidates:
            if c.field == field:
                return c
        return None

    # Date-aware logic for FSSAI (Labelling and Display) First Amendment Regulations, 2026
    # Notified: 24 March 2026 | Effective: 1 July 2027
    # Scope: RDA/serving info for infant nutrition, small-package logo treatment, nutritional info exemptions, non-retail container labelling.
    amendment_2026_effective = date(2027, 7, 1)
    is_amendment_2026_active = reference_date >= amendment_2026_effective
    rule_ver_2026 = "1.1" if is_amendment_2026_active else "1.0"
    amendment_2026_info = (
        " (Amended by First Amendment Regulations, 2026 - active; covers infant nutrition serve-RDA, small package logo, nutritional exemptions)" 
        if is_amendment_2026_active else 
        " (First Amendment Regulations, 2026 is not yet effective - notified 2026-03-24, effective 2027-07-01; covers infant nutrition serve-RDA, small package logo, nutritional exemptions)"
    )

    # 1. Ingredients List Rule (Regulation 5(2))
    cand_ing = find_cand("FSSAI_INGREDIENTS")
    if is_single_ingredient is True:
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_INGREDIENTS_DECLARATION",
            rule_version=rule_ver_2026,
            field="FSSAI_INGREDIENTS",
            status=LegalStatus.NOT_APPLICABLE,
            reason=f"Exempt under Regulation 5(2)(i) as a single-ingredient food product.{amendment_2026_info}",
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(2)(i)",
            source_url="https://www.fssai.gov.in"
        ))
    elif cand_ing and cand_ing.status == "DETECTED":
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_INGREDIENTS_DECLARATION",
            rule_version=rule_ver_2026,
            field="FSSAI_INGREDIENTS",
            status=LegalStatus.PASS,
            reason=f"Authoritative Regulation 5(2) requires list of ingredients. Ingredients declaration detected.{amendment_2026_info}",
            evaluated_value=cand_ing.raw_value,
            evidence_ids=cand_ing.evidence_ids,
            capture_ids=cand_ing.capture_ids,
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(2)",
            source_url="https://www.fssai.gov.in"
        ))
    elif is_single_ingredient is None:
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_INGREDIENTS_DECLARATION",
            rule_version=rule_ver_2026,
            field="FSSAI_INGREDIENTS",
            status=LegalStatus.REVIEW_REQUIRED,
            reason=f"Single-ingredient status context is missing; manual verification required to check if list is exempt under Regulation 5(2)(i).{amendment_2026_info}",
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(2)",
            source_url="https://www.fssai.gov.in"
        ))
    else:
        status = LegalStatus.FAIL if evidence_sufficiency == "SUFFICIENT_FOR_ABSENCE_EVALUATION" else LegalStatus.REVIEW_REQUIRED
        reason = ("Required list of ingredients was not detected on any captured packaging panel. "
                  f"Regulation 5(2) mandates list of ingredients declaration.{amendment_2026_info}")
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_INGREDIENTS_DECLARATION",
            rule_version=rule_ver_2026,
            field="FSSAI_INGREDIENTS",
            status=status,
            reason=reason,
            evidence_ids=[],
            capture_ids=[],
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(2)",
            source_url="https://www.fssai.gov.in"
        ))

    # 2. Veg / Non Veg Symbol (Regulation 5(4))
    cand_veg = find_cand("FSSAI_VEG_NONVEG")
    if veg_nonveg_exempt is True:
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_VEG_NONVEG_SYMBOL",
            rule_version=rule_ver_2026,
            field="FSSAI_VEG_NONVEG",
            status=LegalStatus.NOT_APPLICABLE,
            reason=f"Exempt from vegetarian/non-vegetarian symbol labelling requirements under Regulation 5(4).{amendment_2026_info}",
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(4)",
            source_url="https://www.fssai.gov.in"
        ))
    elif cand_veg and cand_veg.status in ("DETECTED", "REVIEW_REQUIRED"):
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_VEG_NONVEG_SYMBOL",
            rule_version=rule_ver_2026,
            field="FSSAI_VEG_NONVEG",
            status=LegalStatus.REVIEW_REQUIRED,
            reason=f"FSSAI Regulation 5(4) requires a visual, colour-coded symbol. Supporting text '{cand_veg.raw_value}' was detected, but visual symbol compliance must be manually verified.{amendment_2026_info}",
            evaluated_value=cand_veg.raw_value,
            evidence_ids=cand_veg.evidence_ids,
            capture_ids=cand_veg.capture_ids,
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(4)",
            source_url="https://www.fssai.gov.in"
        ))
    elif veg_nonveg_exempt is None:
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_VEG_NONVEG_SYMBOL",
            rule_version=rule_ver_2026,
            field="FSSAI_VEG_NONVEG",
            status=LegalStatus.REVIEW_REQUIRED,
            reason=f"Exemption context is missing; manual verification required to check if symbol is required under Regulation 5(4).{amendment_2026_info}",
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(4)",
            source_url="https://www.fssai.gov.in"
        ))
    else:
        status = LegalStatus.FAIL if evidence_sufficiency == "SUFFICIENT_FOR_ABSENCE_EVALUATION" else LegalStatus.REVIEW_REQUIRED
        reason = ("Vegetarian / Non-Vegetarian symbol or declaration not detected. "
                  f"Regulation 5(4) mandates a veg/non-veg symbol indicator.{amendment_2026_info}")
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_VEG_NONVEG_SYMBOL",
            rule_version=rule_ver_2026,
            field="FSSAI_VEG_NONVEG",
            status=status,
            reason=reason,
            evidence_ids=[],
            capture_ids=[],
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(4)",
            source_url="https://www.fssai.gov.in"
        ))

    # 3. FSSAI Licence Number (Regulation 5(7))
    cand_lic = find_cand("FSSAI_LICENCE")
    if cand_lic and cand_lic.status == "DETECTED":
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_LICENCE_PRESENCE",
            rule_version=rule_ver_2026,
            field="FSSAI_LICENCE",
            status=LegalStatus.REVIEW_REQUIRED,
            reason=f"Regulation 5(7) requires both the FSSAI logo and 14-digit licence number. Plausible licence number '{cand_lic.raw_value}' was detected, but the presence of the accompanying official logo must be verified.{amendment_2026_info}",
            evaluated_value=cand_lic.raw_value,
            evidence_ids=cand_lic.evidence_ids,
            capture_ids=cand_lic.capture_ids,
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(7)",
            source_url="https://www.fssai.gov.in"
        ))
    else:
        status = LegalStatus.FAIL if evidence_sufficiency == "SUFFICIENT_FOR_ABSENCE_EVALUATION" else LegalStatus.REVIEW_REQUIRED
        reason = ("FSSAI registration/licence number not detected. "
                  f"Regulation 5(7) mandates licence number declaration.{amendment_2026_info}")
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_LICENCE_PRESENCE",
            rule_version=rule_ver_2026,
            field="FSSAI_LICENCE",
            status=status,
            reason=reason,
            evidence_ids=[],
            capture_ids=[],
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(7)",
            source_url="https://www.fssai.gov.in"
        ))

    # 3a. Licence number format validity remains separate from presence/logo review.
    # This service is invoked only for officer-confirmed FOOD context, so the
    # validator cannot leak into Legal Metrology or non-food inspections.
    licence_candidates = sorted(
        (candidate for candidate in (validity_candidates if validity_candidates is not None else candidates)
         if candidate.field == "FSSAI_LICENCE"),
        key=lambda candidate: candidate.model_dump_json(),
    )
    detected_licences = [candidate for candidate in licence_candidates if candidate.status == "DETECTED"]
    licence_values = {
        re.sub(r"\D", "", candidate.raw_value or "")
        for candidate in detected_licences
    }
    if not detected_licences:
        licence_format_status = LegalStatus.REVIEW_REQUIRED
        licence_format_reason = "FSSAI licence number format cannot be validated from missing or uncertain evidence."
        licence_format_value = None
    elif any(not re.fullmatch(r"\d{14}", value) for value in licence_values):
        licence_format_status = LegalStatus.FAIL
        licence_format_reason = "At least one reliable FSSAI licence declaration does not have the required 14-digit structure."
        licence_format_value = sorted(licence_values)
    elif len(licence_values) != 1:
        licence_format_status = LegalStatus.REVIEW_REQUIRED
        licence_format_reason = "Conflicting valid-format FSSAI licence number evidence requires officer review."
        licence_format_value = sorted(licence_values)
    else:
        licence_format_value = next(iter(licence_values))
        if re.fullmatch(r"\d{14}", licence_format_value):
            licence_format_status = LegalStatus.PASS
            licence_format_reason = "Detected FSSAI licence number has the required 14-digit structure."
        else:
            licence_format_status = LegalStatus.FAIL
            licence_format_reason = "Reliable FSSAI licence evidence does not have the required 14-digit structure."
    results.append(RuleEvaluationResult(
        rule_id="FSSAI_LICENCE_FORMAT_VALIDITY",
        rule_version=rule_ver_2026,
        field="FSSAI_LICENCE",
        status=licence_format_status,
        reason=f"{licence_format_reason}{amendment_2026_info}",
        evaluated_value=licence_format_value,
        evidence_ids=sorted({item for candidate in licence_candidates for item in candidate.evidence_ids}),
        capture_ids=sorted({item for candidate in licence_candidates for item in candidate.capture_ids}),
        reference_date=reference_date,
        source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(7)",
        source_url="https://www.fssai.gov.in"
    ))

    # 4. Allergen Declaration (Regulation 5(14))
    cand_all = find_cand("FSSAI_ALLERGENS")
    if cand_all and cand_all.status == "DETECTED":
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_ALLERGEN_DECLARATION",
            rule_version=rule_ver_2026,
            field="FSSAI_ALLERGENS",
            status=LegalStatus.PASS,
            reason=f"Regulation 5(14) requires allergen warning statements if present. Allergen declaration '{cand_all.raw_value}' detected.{amendment_2026_info}",
            evaluated_value=cand_all.raw_value,
            evidence_ids=cand_all.evidence_ids,
            capture_ids=cand_all.capture_ids,
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(14)",
            source_url="https://www.fssai.gov.in"
        ))
    else:
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_ALLERGEN_DECLARATION",
            rule_version=rule_ver_2026,
            field="FSSAI_ALLERGENS",
            status=LegalStatus.REVIEW_REQUIRED,
            reason=f"No explicit allergen warning statement detected. Verify if the product's ingredients require an allergen declaration under Regulation 5(14).{amendment_2026_info}",
            evidence_ids=[],
            capture_ids=[],
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(14)",
            source_url="https://www.fssai.gov.in"
        ))

    # 5. Nutritional Info Panel (Regulation 5(3))
    cand_nut = find_cand("FSSAI_NUTRITION")
    if is_nutrition_exempt is True or package_area_exemption is True:
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_NUTRITIONAL_INFO",
            rule_version=rule_ver_2026,
            field="FSSAI_NUTRITION",
            status=LegalStatus.NOT_APPLICABLE,
            reason=f"Exempt from nutritional facts declaration under Regulation 5(3)(b) exemptions.{amendment_2026_info}",
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(3)(b)",
            source_url="https://www.fssai.gov.in"
        ))
    elif cand_nut and cand_nut.status == "DETECTED":
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_NUTRITIONAL_INFO",
            rule_version=rule_ver_2026,
            field="FSSAI_NUTRITION",
            status=LegalStatus.PASS,
            reason=f"Authoritative Regulation 5(3) requires nutritional information panel. Nutritional facts panel detected.{amendment_2026_info}",
            evaluated_value=cand_nut.raw_value,
            evidence_ids=cand_nut.evidence_ids,
            capture_ids=cand_nut.capture_ids,
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(3)",
            source_url="https://www.fssai.gov.in"
        ))
    elif is_nutrition_exempt is None or package_area_exemption is None:
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_NUTRITIONAL_INFO",
            rule_version=rule_ver_2026,
            field="FSSAI_NUTRITION",
            status=LegalStatus.REVIEW_REQUIRED,
            reason=f"Exemption/label surface area context is missing; manual verification required to check if nutritional facts are required under Regulation 5(3).{amendment_2026_info}",
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(3)",
            source_url="https://www.fssai.gov.in"
        ))
    else:
        status = LegalStatus.FAIL if evidence_sufficiency == "SUFFICIENT_FOR_ABSENCE_EVALUATION" else LegalStatus.REVIEW_REQUIRED
        reason = ("Nutritional facts panel not detected. "
                  f"Regulation 5(3) mandates nutritional declarations on all packaged food.{amendment_2026_info}")
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_NUTRITIONAL_INFO",
            rule_version=rule_ver_2026,
            field="FSSAI_NUTRITION",
            status=status,
            reason=reason,
            evidence_ids=[],
            capture_ids=[],
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) Regulations, 2020 - Regulation 5(3)",
            source_url="https://www.fssai.gov.in"
        ))

    # 6. Coffee-Chicory Mixture amendment (First Amendment Regulations, 2025)
    # Final Gazette Notification: 8 August 2025 | Effective: 1 July 2026
    # Note: FSSAI Direction dated 22 July 2026 kept enforcement in abeyance until 1 July 2027, allowing interim simplified PDP declarations.
    is_coffee_chicory = False
    cand_name = find_cand("COMMON_GENERIC_NAME")
    if cand_name and cand_name.status == "DETECTED":
        name_upper = str(cand_name.raw_value).upper()
        if "COFFEE" in name_upper and "CHICORY" in name_upper:
            is_coffee_chicory = True
            
    if cand_ing and cand_ing.status == "DETECTED":
        ing_upper = str(cand_ing.raw_value).upper()
        if "COFFEE" in ing_upper and "CHICORY" in ing_upper:
            is_coffee_chicory = True

    if is_coffee_chicory:
        # Effective date boundary checking (1 July 2026)
        is_mixture_notified = reference_date >= date(2025, 8, 8)
        is_mixture_effective = reference_date >= date(2026, 7, 1)
        is_direction_active = reference_date >= date(2026, 7, 22)
        is_final_enforced = reference_date >= date(2027, 7, 1)

        if not is_mixture_effective:
            results.append(RuleEvaluationResult(
                rule_id="FSSAI_COFFEE_CHICORY_PROPORTIONS",
                rule_version="1.0",
                field="FSSAI_INGREDIENTS",
                status=LegalStatus.NOT_APPLICABLE,
                reason="Coffee-chicory mixture 2025 amendment is not yet effective on this reference date (becomes effective 2026-07-01).",
                reference_date=reference_date,
                source_reference="Food Safety and Standards (Labelling and Display) First Amendment Regulations, 2025",
                source_url="https://www.fssai.gov.in"
            ))
        elif is_direction_active and not is_final_enforced:
            # 22 July 2026 Direction: Original box rules in abeyance till 1 July 2027; interim text declaration is active.
            mixture_raw = cand_ing.raw_value if cand_ing else ""
            if ing_match := re.search(r"\bCOFFEE\s*\d+\s*%", mixture_raw.upper()):
                results.append(RuleEvaluationResult(
                    rule_id="FSSAI_COFFEE_CHICORY_PROPORTIONS",
                    rule_version="1.0",
                    field="FSSAI_INGREDIENTS",
                    status=LegalStatus.PASS,
                    reason="Coffee-Chicory box declaration is in abeyance until 1 July 2027 (FSSAI Direction 22 July 2026). Interim text-based PDP proportion declaration is detected.",
                    evaluated_value=cand_ing.raw_value,
                    evidence_ids=cand_ing.evidence_ids if cand_ing else [],
                    capture_ids=cand_ing.capture_ids if cand_ing else [],
                    reference_date=reference_date,
                    source_reference="FSSAI Enforcement Direction dated 22 July 2026",
                    source_url="https://www.fssai.gov.in"
                ))
            else:
                results.append(RuleEvaluationResult(
                    rule_id="FSSAI_COFFEE_CHICORY_PROPORTIONS",
                    rule_version="1.0",
                    field="FSSAI_INGREDIENTS",
                    status=LegalStatus.FAIL,
                    reason="Coffee-Chicory box declaration in abeyance (FSSAI Direction 22 July 2026); however, required interim text-based PDP proportions are missing.",
                    reference_date=reference_date,
                    source_reference="FSSAI Enforcement Direction dated 22 July 2026",
                    source_url="https://www.fssai.gov.in"
                ))
        else:
            # Post-July 2027 or pre-direction July 2026
            mixture_raw = cand_ing.raw_value if cand_ing else ""
            if ing_match := re.search(r"\bCOFFEE\s*\d+\s*%", mixture_raw.upper()):
                results.append(RuleEvaluationResult(
                    rule_id="FSSAI_COFFEE_CHICORY_PROPORTIONS",
                    rule_version="1.0",
                    field="FSSAI_INGREDIENTS",
                    status=LegalStatus.PASS,
                    reason="Authoritative FSSAI First Amendment, 2025 requires proportions declaration. Proportions detected in list.",
                    evaluated_value=cand_ing.raw_value,
                    evidence_ids=cand_ing.evidence_ids if cand_ing else [],
                    capture_ids=cand_ing.capture_ids if cand_ing else [],
                    reference_date=reference_date,
                    source_reference="Food Safety and Standards (Labelling and Display) First Amendment Regulations, 2025",
                    source_url="https://www.fssai.gov.in"
                ))
            else:
                results.append(RuleEvaluationResult(
                    rule_id="FSSAI_COFFEE_CHICORY_PROPORTIONS",
                    rule_version="1.0",
                    field="FSSAI_INGREDIENTS",
                    status=LegalStatus.FAIL,
                    reason="Missing coffee and chicory proportion percentages required under FSSAI First Amendment, 2025.",
                    reference_date=reference_date,
                    source_reference="Food Safety and Standards (Labelling and Display) First Amendment Regulations, 2025",
                    source_url="https://www.fssai.gov.in"
                ))
    else:
        results.append(RuleEvaluationResult(
            rule_id="FSSAI_COFFEE_CHICORY_PROPORTIONS",
            rule_version="1.0",
            field="FSSAI_INGREDIENTS",
            status=LegalStatus.NOT_APPLICABLE,
            reason="Product is not a coffee-chicory mixture. FSSAI 2025 First Amendment is not applicable.",
            reference_date=reference_date,
            source_reference="Food Safety and Standards (Labelling and Display) First Amendment Regulations, 2025",
            source_url="https://www.fssai.gov.in"
        ))

    return results
