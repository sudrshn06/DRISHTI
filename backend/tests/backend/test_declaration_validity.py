"""Focused tests separating declaration presence from structural validity."""

from datetime import date

from app.schemas.compliance import LegalStatus
from app.schemas.inspection import CaptureRecord, InspectionSession
from app.schemas.ocr import (
    BusinessNormalized,
    ConsumerCareNormalized,
    DateNormalized,
    FieldCandidate,
    MrpNormalized,
    NetQuantityNormalized,
)
from app.schemas.officer_review import OfficerDeclarationOverride
from app.services.compliance_service import orchestrate_compliance
from app.services.officer_review_service import apply_officer_overrides
from app.services.fssai_compliance_service import evaluate_fssai_compliance
from app.api.routes.inspections import _update_session_compliance


REFERENCE_DATE = date(2023, 8, 24)


def _evaluate(candidates, *, evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION"):
    return orchestrate_compliance(
        candidates=candidates,
        reference_date=REFERENCE_DATE,
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin="DOMESTIC",
        regulatory_category="NON_FOOD",
        is_electronic="NON_ELECTRONIC",
        package_structure="SINGLE",
        alcohol_context="NON_ALCOHOLIC",
        date_regulatory_regime="GENERAL",
        date_package_exemption="NONE",
        evidence_sufficiency=evidence_sufficiency,
        inspection_complete=True,
    )


def _result(results, rule_id):
    return next(item for item in results if item.rule_id == rule_id)


def test_valid_mrp_has_separate_passing_presence_value_format_and_tax_wording():
    candidate = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs 137 inclusive of all taxes",
        normalized_value=MrpNormalized(currency="INR", amount=137),
        confidence=0.96,
    )
    results = _evaluate([candidate])

    assert _result(results, "MRP_DECLARATION_PRESENCE").status == LegalStatus.PASS
    assert _result(results, "MRP_VALUE_FORMAT_VALIDITY").status == LegalStatus.PASS
    assert _result(results, "MRP_TAX_WORDING_CONSISTENCY").status == LegalStatus.PASS


def test_reliable_explicit_tax_extra_wording_is_deterministic_fail():
    candidate = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs 137 plus applicable taxes",
        normalized_value=MrpNormalized(currency="INR", amount=137),
        confidence=0.97,
    )

    result = _result(_evaluate([candidate]), "MRP_TAX_WORDING_CONSISTENCY")

    assert result.status == LegalStatus.FAIL
    assert "inclusive of all taxes" in result.reason.lower()


def test_absent_optional_tax_phrase_is_not_treated_as_a_failure():
    candidate = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs 137",
        normalized_value=MrpNormalized(currency="INR", amount=137),
    )

    result = _result(_evaluate([candidate]), "MRP_TAX_WORDING_CONSISTENCY")

    assert result.status == LegalStatus.NOT_APPLICABLE


def test_conflicting_explicit_tax_wording_requires_review_regardless_of_order():
    candidates = [
        FieldCandidate(
            field="MRP",
            status="DETECTED",
            raw_value="MRP Rs 137 inclusive of all taxes",
            normalized_value=MrpNormalized(currency="INR", amount=137),
        ),
        FieldCandidate(
            field="MRP",
            status="DETECTED",
            raw_value="MRP Rs 137 plus GST",
            normalized_value=MrpNormalized(currency="INR", amount=137),
        ),
    ]

    first = _result(_evaluate(candidates), "MRP_TAX_WORDING_CONSISTENCY")
    second = _result(_evaluate(list(reversed(candidates))), "MRP_TAX_WORDING_CONSISTENCY")

    assert first.status == LegalStatus.REVIEW_REQUIRED
    assert first.model_dump() == second.model_dump()


def test_valid_net_quantity_has_separate_format_and_unit_results():
    candidate = FieldCandidate(
        field="NET_QUANTITY",
        status="DETECTED",
        raw_value="Net Quantity 725 g",
        normalized_value=NetQuantityNormalized(value=725, unit="g"),
        confidence=0.95,
    )
    results = _evaluate([candidate])

    assert _result(results, "NET_QUANTITY_PRESENCE").status == LegalStatus.PASS
    assert _result(results, "NET_QUANTITY_FORMAT_VALIDITY").status == LegalStatus.PASS
    assert _result(results, "NET_QUANTITY_UNIT_VALIDITY").status == LegalStatus.PASS


def test_quantity_number_without_unit_and_malformed_quantity_require_review():
    missing_unit = FieldCandidate(
        field="NET_QUANTITY",
        status="REVIEW_REQUIRED",
        raw_value="Net Quantity 725",
        confidence=0.94,
    )
    malformed = FieldCandidate(
        field="NET_QUANTITY",
        status="REVIEW_REQUIRED",
        raw_value="Net Quantity seven hundred grams",
        confidence=0.93,
    )

    for candidate in (missing_unit, malformed):
        results = _evaluate([candidate])
        assert _result(results, "NET_QUANTITY_FORMAT_VALIDITY").status == LegalStatus.REVIEW_REQUIRED
        assert _result(results, "NET_QUANTITY_UNIT_VALIDITY").status == LegalStatus.REVIEW_REQUIRED


def test_unrecognized_explicit_quantity_unit_fails_unit_validity_only():
    candidate = FieldCandidate(
        field="NET_QUANTITY",
        status="DETECTED",
        raw_value="Net Quantity 12 boxes",
        normalized_value=NetQuantityNormalized(value=12, unit="boxes"),
        confidence=0.98,
    )
    results = _evaluate([candidate])

    assert _result(results, "NET_QUANTITY_PRESENCE").status == LegalStatus.PASS
    assert _result(results, "NET_QUANTITY_UNIT_VALIDITY").status == LegalStatus.FAIL


def test_impossible_and_valid_calendar_dates_are_distinguished():
    impossible = FieldCandidate(
        field="MONTH_YEAR",
        status="DETECTED",
        raw_value="Manufactured 31/02/2023",
        normalized_value=DateNormalized(type="MANUFACTURED", day=31, month=2, year=2023),
        confidence=0.98,
    )
    valid = FieldCandidate(
        field="MONTH_YEAR",
        status="DETECTED",
        raw_value="Manufactured 28/02/2023",
        normalized_value=DateNormalized(type="MANUFACTURED", day=28, month=2, year=2023),
        confidence=0.98,
    )

    assert _result(_evaluate([impossible]), "DATE_DECLARATION_VALIDITY").status == LegalStatus.FAIL
    assert _result(_evaluate([valid]), "DATE_DECLARATION_VALIDITY").status == LegalStatus.PASS


def test_terminal_date_before_manufacture_date_fails_chronology():
    candidates = [
        FieldCandidate(
            field="MONTH_YEAR",
            status="DETECTED",
            raw_value="Manufactured 10/08/2023",
            normalized_value=DateNormalized(type="MANUFACTURED", day=10, month=8, year=2023),
            confidence=0.98,
        ),
        FieldCandidate(
            field="MONTH_YEAR",
            status="DETECTED",
            raw_value="Use by 09/08/2023",
            normalized_value=DateNormalized(type="USE_BY", day=9, month=8, year=2023),
            confidence=0.98,
        ),
    ]

    result = _result(_evaluate(candidates), "DATE_CHRONOLOGY_CONSISTENCY")

    assert result.status == LegalStatus.FAIL


def test_uncertain_ocr_never_becomes_validity_fail():
    candidate = FieldCandidate(
        field="MRP",
        status="REVIEW_REQUIRED",
        raw_value="MRP Rs 137 plus applicable taxes",
        normalized_value=MrpNormalized(currency="INR", amount=137),
        confidence=0.61,
    )
    results = _evaluate([candidate])

    assert _result(results, "MRP_VALUE_FORMAT_VALIDITY").status == LegalStatus.REVIEW_REQUIRED
    assert _result(results, "MRP_TAX_WORDING_CONSISTENCY").status == LegalStatus.REVIEW_REQUIRED


def test_business_name_without_address_does_not_fail_when_absence_is_ineligible():
    candidate = FieldCandidate(
        field="MANUFACTURER_PACKER_IMPORTER",
        status="DETECTED",
        raw_value="Manufactured by Example Industries Ltd",
        normalized_value=BusinessNormalized(
            role="MANUFACTURER",
            name="Example Industries Ltd",
            raw_text="Manufactured by Example Industries Ltd",
        ),
        confidence=0.96,
    )

    result = _result(_evaluate([candidate]), "MANUFACTURER_PACKER_ADDRESS_VALIDITY")

    assert result.status == LegalStatus.REVIEW_REQUIRED


def test_missing_declaration_with_insufficient_coverage_remains_review_required():
    candidate = FieldCandidate(field="MRP", status="NOT_DETECTED")

    results = _evaluate([candidate])

    assert _result(results, "MRP_DECLARATION_PRESENCE").status == LegalStatus.REVIEW_REQUIRED
    assert _result(results, "MRP_VALUE_FORMAT_VALIDITY").status == LegalStatus.REVIEW_REQUIRED


def test_officer_confirmed_correction_replaces_invalid_ocr_value_for_validity():
    observed = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs 137 plus taxes",
        normalized_value=MrpNormalized(currency="INR", amount=137),
    )
    confirmed = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs 137 inclusive of all taxes",
        normalized_value=MrpNormalized(currency="INR", amount=137),
        observation_layer="OFFICER_CONFIRMED",
        extraction_method="OFFICER_CONFIRMED",
        observation_sources=["OFFICER_CONFIRMED"],
    )
    override = OfficerDeclarationOverride(
        override_id="override-generic",
        target_key="MRP",
        field="MRP",
        observed_candidate=observed,
        confirmed_candidate=confirmed,
        supporting_capture_id="capture-generic",
        reason="Confirmed from visible package declaration",
        officer_user_id="officer-generic",
        officer_username="officer",
        confirmed_at="2026-08-24T00:00:00Z",
    )

    corrected = apply_officer_overrides([observed], [override])
    results = _evaluate(corrected)

    assert _result(results, "MRP_TAX_WORDING_CONSISTENCY").status == LegalStatus.PASS


def test_gemini_only_value_does_not_change_validity_or_reproducibility_fingerprint():
    deterministic = FieldCandidate(field="MRP", status="NOT_DETECTED")

    def session(display_candidate):
        value = InspectionSession(
            inspection_id="inspection-validity",
            reference_date=REFERENCE_DATE.isoformat(),
            product_category="GENERIC_RETAIL_PACKAGE",
            product_origin="DOMESTIC",
            regulatory_product_class="NON_FOOD",
            date_regulatory_regime="GENERAL",
            date_package_exemption="NONE",
            is_electronic="NON_ELECTRONIC",
            package_structure="SINGLE",
            alcohol_context="NON_ALCOHOLIC",
            capture_plan_id="plan_software_1",
            capture_status="COMPLETE_EVIDENCE_CAPTURE",
            evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
            captures=[CaptureRecord(
                capture_id="capture-generic",
                view_id="FRONT",
                image_sha256="a" * 64,
                field_candidates=[display_candidate],
                deterministic_field_candidates=[deterministic],
            )],
            aggregated_candidates=[display_candidate],
            deterministic_aggregated_candidates=[deterministic],
        )
        _update_session_compliance(value)
        return value

    gemini_display = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs 137 inclusive of all taxes",
        normalized_value=MrpNormalized(currency="INR", amount=137),
        observation_layer="RECONCILED",
        extraction_method="HYBRID_RECONCILIATION",
        observation_sources=["GOOGLE_GEMINI"],
        reconciliation_reason="GEMINI_EXPLICIT_EVIDENCE",
        provider_evidence=[{
            "provider": "GOOGLE_GEMINI",
            "raw_text": "MRP Rs 137 inclusive of all taxes",
            "evidence_note": "Visible declaration",
        }],
    )
    with_gemini = session(gemini_display)
    without_gemini = session(deterministic)

    assert [(item.rule_id, item.status) for item in with_gemini.rule_evaluations] == [
        (item.rule_id, item.status) for item in without_gemini.rule_evaluations
    ]
    assert with_gemini.reproducibility.result_fingerprint == without_gemini.reproducibility.result_fingerprint


def test_business_address_can_fail_only_with_absence_eligible_evidence():
    candidate = FieldCandidate(
        field="MANUFACTURER_PACKER_IMPORTER",
        status="DETECTED",
        raw_value="Packed by Example Industries Ltd",
        normalized_value=BusinessNormalized(
            role="PACKER",
            name="Example Industries Ltd",
            raw_text="Packed by Example Industries Ltd",
        ),
        confidence=0.98,
    )

    result = _result(
        _evaluate([candidate], evidence_sufficiency="SUFFICIENT_FOR_ABSENCE_EVALUATION"),
        "MANUFACTURER_PACKER_ADDRESS_VALIDITY",
    )

    assert result.status == LegalStatus.FAIL


def test_importer_name_and_address_validity_uses_imported_context_only():
    candidate = FieldCandidate(
        field="MANUFACTURER_PACKER_IMPORTER",
        status="DETECTED",
        raw_value="Imported by Example Trading Ltd\n12 Market Road, Port City 400001",
        normalized_value=BusinessNormalized(
            role="IMPORTER",
            name="Example Trading Ltd",
            address="12 Market Road, Port City 400001",
            pin_code="400001",
            raw_text="Imported by Example Trading Ltd\n12 Market Road, Port City 400001",
        ),
    )

    results = orchestrate_compliance(
        candidates=[candidate],
        reference_date=REFERENCE_DATE,
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin="IMPORTED",
        regulatory_category="NON_FOOD",
        is_electronic="NON_ELECTRONIC",
        package_structure="SINGLE",
        alcohol_context="NON_ALCOHOLIC",
        date_regulatory_regime="GENERAL",
        date_package_exemption="NONE",
    )

    assert _result(results, "IMPORTER_ADDRESS_VALIDITY").status == LegalStatus.PASS


def test_consumer_care_structural_validity_is_separate_from_presence():
    valid = FieldCandidate(
        field="CONSUMER_CARE",
        status="DETECTED",
        raw_value="Consumer care: help@example.test, 18001234567",
        normalized_value=ConsumerCareNormalized(
            email="help@example.test",
            phone="18001234567",
        ),
    )
    incomplete = FieldCandidate(
        field="CONSUMER_CARE",
        status="REVIEW_REQUIRED",
        raw_value="Consumer care: contact details unclear",
    )

    assert _result(
        _evaluate([valid]), "CONSUMER_CARE_STRUCTURE_VALIDITY"
    ).status == LegalStatus.PASS
    assert _result(
        _evaluate([incomplete]), "CONSUMER_CARE_STRUCTURE_VALIDITY"
    ).status == LegalStatus.REVIEW_REQUIRED


def test_food_context_keeps_lmpc_business_validity_out_of_fssai_scope():
    results = orchestrate_compliance(
        candidates=[],
        reference_date=REFERENCE_DATE,
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin="DOMESTIC",
        regulatory_category="FOOD",
        is_electronic="NON_ELECTRONIC",
        package_structure="SINGLE",
        alcohol_context="NON_ALCOHOLIC",
        date_regulatory_regime="FOOD",
        date_package_exemption="NONE",
    )

    result = _result(results, "MANUFACTURER_PACKER_ADDRESS_VALIDITY")
    assert result.status == LegalStatus.NOT_APPLICABLE


def test_valid_date_order_passes_chronology_deterministically():
    candidates = [
        FieldCandidate(
            field="MONTH_YEAR",
            status="DETECTED",
            raw_value="Manufactured 10/08/2023",
            normalized_value=DateNormalized(type="MANUFACTURED", day=10, month=8, year=2023),
        ),
        FieldCandidate(
            field="MONTH_YEAR",
            status="DETECTED",
            raw_value="Use by 11/08/2023",
            normalized_value=DateNormalized(type="USE_BY", day=11, month=8, year=2023),
        ),
    ]

    first = _evaluate(candidates)
    second = _evaluate(list(reversed(candidates)))

    assert _result(first, "DATE_CHRONOLOGY_CONSISTENCY").status == LegalStatus.PASS
    assert _result(first, "DATE_CHRONOLOGY_CONSISTENCY").model_dump() == _result(
        second, "DATE_CHRONOLOGY_CONSISTENCY"
    ).model_dump()


def test_fssai_licence_format_validation_is_scoped_and_separate_from_logo_review():
    valid = FieldCandidate(
        field="FSSAI_LICENCE",
        status="DETECTED",
        raw_value="10456789012345",
    )
    malformed = FieldCandidate(
        field="FSSAI_LICENCE",
        status="DETECTED",
        raw_value="1045678901234",
    )
    uncertain = malformed.model_copy(update={"status": "REVIEW_REQUIRED"})

    valid_results = evaluate_fssai_compliance([valid], REFERENCE_DATE)
    assert _result(valid_results, "FSSAI_LICENCE_PRESENCE").status == LegalStatus.REVIEW_REQUIRED
    assert _result(valid_results, "FSSAI_LICENCE_FORMAT_VALIDITY").status == LegalStatus.PASS
    assert _result(
        evaluate_fssai_compliance([malformed], REFERENCE_DATE),
        "FSSAI_LICENCE_FORMAT_VALIDITY",
    ).status == LegalStatus.FAIL
    assert _result(
        evaluate_fssai_compliance([uncertain], REFERENCE_DATE),
        "FSSAI_LICENCE_FORMAT_VALIDITY",
    ).status == LegalStatus.REVIEW_REQUIRED
