"""Phase 3 regressions for complete findings and cross-surface consistency."""

from datetime import date

from app.api.routes.inspections import _update_session_compliance
from app.schemas.compliance import LegalStatus
from app.schemas.inspection import CaptureRecord, InspectionSession
from app.schemas.ocr import (
    BusinessNormalized,
    ConsumerCareNormalized,
    DateNormalized,
    FieldCandidate,
    MrpNormalized,
    NetQuantityNormalized,
    OcrLine,
    ProviderEvidence,
)
from app.schemas.report import DeclarationFindingItem, OverallDisposition
from app.services.officer_review_service import (
    create_officer_declaration_override,
    rebuild_authoritative_candidates,
)
from app.services.candidate_extractor import extract_candidates
from app.services.report_service import compute_overall_disposition
from app.services.report_service import generate_inspection_report


REFERENCE_DATE = date(2023, 8, 24)


def _candidate(field, normalized, raw, *, evidence_id, status="DETECTED"):
    return FieldCandidate(
        field=field,
        status=status,
        raw_value=raw,
        normalized_value=normalized,
        evidence_ids=[evidence_id],
        confidence=0.98,
        observation_sources=["PADDLEOCR"],
    )


def _capture(capture_id, view_id, candidates, image_sha):
    return CaptureRecord(
        capture_id=capture_id,
        view_id=view_id,
        image_sha256=image_sha,
        field_candidates=[candidate.model_copy(deep=True) for candidate in candidates],
        deterministic_field_candidates=[candidate.model_copy(deep=True) for candidate in candidates],
    )


def _session(captures, *, regulatory_class="NON_FOOD", origin="DOMESTIC"):
    session = InspectionSession(
        inspection_id="phase-3-generic",
        reference_date=REFERENCE_DATE.isoformat(),
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin=origin,
        regulatory_product_class=regulatory_class,
        date_regulatory_regime="FOOD" if regulatory_class == "FOOD" else "GENERAL",
        date_package_exemption="NONE",
        is_electronic="NON_ELECTRONIC",
        package_structure="SINGLE",
        alcohol_context="NON_ALCOHOLIC",
        capture_plan_id="plan_software_1",
        capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        captures=captures,
    )
    rebuild_authoritative_candidates(session)
    _update_session_compliance(session)
    return session


def _finding(session, rule_id, *, food=False):
    results = session.food_label_evaluations if food else session.rule_evaluations
    return next(item for item in results if item.rule_id == rule_id)


def _report_finding(rule_id, status):
    return DeclarationFindingItem(
        rule_id=rule_id,
        field=rule_id,
        status=status,
        reason="Deterministic test finding",
        legal_reference="Existing source",
        applicability_status="APPLICABLE",
    )


def _line(text, confidence=0.98):
    return OcrLine(
        text=text,
        confidence=confidence,
        polygon=[[0.0, 0.0], [100.0, 0.0], [100.0, 10.0], [0.0, 10.0]],
    )


def _session_from_lines(lines, *, regulatory_class="NON_FOOD"):
    evidence_map = {str(index): f"ev-{index}" for index in range(len(lines))}
    candidates = extract_candidates(lines, evidence_map)
    capture = _capture("cap-ocr", "BACK", candidates, "3" * 64)
    return _session([capture], regulatory_class=regulatory_class)


def test_two_independent_fail_findings_are_both_returned():
    candidates = [
        _candidate("MRP", MrpNormalized(currency="INR", amount=137), "MRP Rs 137 plus GST", evidence_id="ev-mrp"),
        _candidate("NET_QUANTITY", NetQuantityNormalized(value=12, unit="boxes"), "Net Quantity 12 boxes", evidence_id="ev-nq"),
    ]
    session = _session([_capture("cap-a", "FRONT", candidates, "a" * 64)])

    failures = {item.rule_id for item in session.rule_evaluations if item.status == LegalStatus.FAIL}
    assert {"MRP_TAX_WORDING_CONSISTENCY", "NET_QUANTITY_UNIT_VALIDITY"}.issubset(failures)


def test_three_independent_fail_findings_are_all_returned():
    candidates = [
        _candidate("MRP", MrpNormalized(currency="INR", amount=137), "MRP Rs 137 plus taxes", evidence_id="ev-mrp"),
        _candidate("NET_QUANTITY", NetQuantityNormalized(value=12, unit="boxes"), "Net Quantity 12 boxes", evidence_id="ev-nq"),
        _candidate(
            "MONTH_YEAR",
            DateNormalized(type="MANUFACTURED", day=31, month=2, year=2023),
            "Manufactured 31/02/2023",
            evidence_id="ev-date",
        ),
    ]
    session = _session([_capture("cap-a", "BACK", candidates, "b" * 64)])

    failures = {item.rule_id for item in session.rule_evaluations if item.status == LegalStatus.FAIL}
    assert {
        "MRP_TAX_WORDING_CONSISTENCY",
        "NET_QUANTITY_UNIT_VALIDITY",
        "DATE_DECLARATION_VALIDITY",
    }.issubset(failures)


def test_fail_and_review_required_are_both_retained():
    candidates = [
        _candidate("MRP", MrpNormalized(currency="INR", amount=137), "MRP Rs 137 plus GST", evidence_id="ev-mrp"),
        FieldCandidate(field="CONSUMER_CARE", status="REVIEW_REQUIRED", raw_value="Consumer care unclear", evidence_ids=["ev-care"]),
    ]
    session = _session([_capture("cap-a", "BACK", candidates, "c" * 64)])

    assert _finding(session, "MRP_TAX_WORDING_CONSISTENCY").status == LegalStatus.FAIL
    assert _finding(session, "CONSUMER_CARE_STRUCTURE_VALIDITY").status == LegalStatus.REVIEW_REQUIRED


def test_pass_and_fail_make_overall_disposition_violations_found():
    disposition, _ = compute_overall_disposition(
        [_report_finding("PASSING_RULE", "PASS"), _report_finding("FAILING_RULE", "FAIL")],
        [],
        "COMPLETE_EVIDENCE_CAPTURE",
        "INSUFFICIENT_FOR_ABSENCE_EVALUATION",
    )
    assert disposition == OverallDisposition.VIOLATIONS_FOUND


def test_not_applicable_and_fail_remain_distinct():
    candidates = [
        _candidate("MRP", MrpNormalized(currency="INR", amount=137), "MRP Rs 137 plus GST", evidence_id="ev-mrp"),
    ]
    session = _session([_capture("cap-a", "FRONT", candidates, "d" * 64)], origin="DOMESTIC")

    assert _finding(session, "IMPORTER_DECLARATION_PRESENCE").status == LegalStatus.NOT_APPLICABLE
    assert _finding(session, "MRP_TAX_WORDING_CONSISTENCY").status == LegalStatus.FAIL


def test_valid_duplicate_across_views_merges_evidence_without_duplicate_finding():
    front = _candidate("MRP", MrpNormalized(currency="INR", amount=137), "MRP Rs 137", evidence_id="ev-front")
    back = _candidate("MRP", MrpNormalized(currency="INR", amount=137), "MRP Rs 137", evidence_id="ev-back")
    session = _session([
        _capture("cap-front", "FRONT", [front], "e" * 64),
        _capture("cap-back", "BACK", [back], "f" * 64),
    ])

    assert not any(item.rule_id == "CROSS_SURFACE_MRP_CONSISTENCY" for item in session.rule_evaluations)
    presence = _finding(session, "MRP_DECLARATION_PRESENCE")
    assert presence.status == LegalStatus.PASS
    assert presence.evidence_ids == ["ev-back", "ev-front"]
    assert presence.capture_ids == ["cap-back", "cap-front"]


def test_conflicting_mrp_across_surfaces_is_review_with_linked_provenance():
    session = _session([
        _capture("cap-front", "FRONT", [
            _candidate("MRP", MrpNormalized(currency="INR", amount=137), "MRP Rs 137", evidence_id="ev-front")
        ], "1" * 64),
        _capture("cap-back", "BACK", [
            _candidate("MRP", MrpNormalized(currency="INR", amount=149), "MRP Rs 149", evidence_id="ev-back")
        ], "2" * 64),
    ])

    result = _finding(session, "CROSS_SURFACE_MRP_CONSISTENCY")
    assert result.status == LegalStatus.REVIEW_REQUIRED
    assert result.capture_ids == ["cap-back", "cap-front"]
    assert result.evidence_ids == ["ev-back", "ev-front"]
    assert result.evaluated_value["source_views"] == ["BACK", "FRONT"]
    assert len(result.evaluated_value["observed_values"]) == 2
    assert sorted(
        raw
        for observed in result.evaluated_value["observed_values"]
        for raw in observed["raw_values"]
    ) == ["MRP Rs 137", "MRP Rs 149"]
    assert result.source_reference


def test_valid_mrp_wording_does_not_hide_reliable_tax_extra_violation():
    session = _session([
        _capture("cap-front", "FRONT", [
            _candidate("MRP", MrpNormalized(currency="INR", amount=137), "MRP Rs 137 inclusive of all taxes", evidence_id="ev-front")
        ], "7" * 64),
        _capture("cap-back", "BACK", [
            _candidate("MRP", MrpNormalized(currency="INR", amount=149), "MRP Rs 149 plus GST", evidence_id="ev-back")
        ], "8" * 64),
    ])

    assert _finding(session, "MRP_TAX_WORDING_CONSISTENCY").status == LegalStatus.FAIL
    assert _finding(session, "CROSS_SURFACE_MRP_CONSISTENCY").status == LegalStatus.REVIEW_REQUIRED


def test_valid_net_quantity_does_not_hide_reliable_invalid_unit():
    session = _session([
        _capture("cap-front", "FRONT", [
            _candidate("NET_QUANTITY", NetQuantityNormalized(value=725, unit="g"), "Net Quantity 725 g", evidence_id="ev-front")
        ], "9" * 64),
        _capture("cap-back", "BACK", [
            _candidate("NET_QUANTITY", NetQuantityNormalized(value=750, unit="boxes"), "Net Quantity 750 boxes", evidence_id="ev-back")
        ], "a" * 64),
    ])

    assert _finding(session, "NET_QUANTITY_UNIT_VALIDITY").status == LegalStatus.FAIL
    assert _finding(session, "CROSS_SURFACE_NET_QUANTITY_CONSISTENCY").status == LegalStatus.REVIEW_REQUIRED


def test_valid_food_licence_does_not_hide_reliable_malformed_licence():
    session = _session([
        _capture("cap-front", "FRONT", [
            _candidate("FSSAI_LICENCE", "10456789012345", "10456789012345", evidence_id="ev-front")
        ], "b" * 64),
        _capture("cap-back", "BACK", [
            _candidate("FSSAI_LICENCE", "1045678901234", "1045678901234", evidence_id="ev-back")
        ], "c" * 64),
    ], regulatory_class="FOOD")

    assert _finding(session, "FSSAI_LICENCE_FORMAT_VALIDITY", food=True).status == LegalStatus.FAIL
    assert _finding(session, "CROSS_SURFACE_FSSAI_LICENCE_CONSISTENCY", food=True).status == LegalStatus.REVIEW_REQUIRED


def test_conflicting_net_quantity_across_surfaces_requires_review():
    session = _session([
        _capture("cap-front", "FRONT", [
            _candidate("NET_QUANTITY", NetQuantityNormalized(value=725, unit="g"), "Net Quantity 725 g", evidence_id="ev-front")
        ], "3" * 64),
        _capture("cap-back", "BACK", [
            _candidate("NET_QUANTITY", NetQuantityNormalized(value=750, unit="g"), "Net Quantity 750 g", evidence_id="ev-back")
        ], "4" * 64),
    ])
    assert _finding(session, "CROSS_SURFACE_NET_QUANTITY_CONSISTENCY").status == LegalStatus.REVIEW_REQUIRED


def test_conflicting_same_type_dates_across_surfaces_require_review():
    session = _session([
        _capture("cap-top", "TOP", [
            _candidate("MONTH_YEAR", DateNormalized(type="MANUFACTURED", month=7, year=2023), "MFG 07/2023", evidence_id="ev-top")
        ], "5" * 64),
        _capture("cap-bottom", "BOTTOM", [
            _candidate("MONTH_YEAR", DateNormalized(type="MANUFACTURED", month=8, year=2023), "MFG 08/2023", evidence_id="ev-bottom")
        ], "6" * 64),
    ])
    assert _finding(session, "CROSS_SURFACE_DATE_MANUFACTURED_CONSISTENCY").status == LegalStatus.REVIEW_REQUIRED


def test_conflicting_business_information_across_surfaces_requires_review():
    session = _session([
        _capture("cap-left", "LEFT", [_candidate(
            "MANUFACTURER_PACKER_IMPORTER",
            BusinessNormalized(role="PACKER", name="Example One Ltd", address="One Road", raw_text="Packed by Example One Ltd"),
            "Packed by Example One Ltd, One Road",
            evidence_id="ev-left",
        )], "7" * 64),
        _capture("cap-right", "RIGHT", [_candidate(
            "MANUFACTURER_PACKER_IMPORTER",
            BusinessNormalized(role="PACKER", name="Example Two Ltd", address="Two Road", raw_text="Packed by Example Two Ltd"),
            "Packed by Example Two Ltd, Two Road",
            evidence_id="ev-right",
        )], "8" * 64),
    ])
    assert _finding(session, "CROSS_SURFACE_BUSINESS_PACKER_CONSISTENCY").status == LegalStatus.REVIEW_REQUIRED


def test_conflicting_consumer_care_across_surfaces_requires_review():
    session = _session([
        _capture("cap-left", "LEFT", [_candidate(
            "CONSUMER_CARE", ConsumerCareNormalized(email="one@example.test"), "one@example.test", evidence_id="ev-left"
        )], "9" * 64),
        _capture("cap-right", "RIGHT", [_candidate(
            "CONSUMER_CARE", ConsumerCareNormalized(email="two@example.test"), "two@example.test", evidence_id="ev-right"
        )], "a" * 64),
    ])
    assert _finding(session, "CROSS_SURFACE_CONSUMER_CARE_CONSISTENCY").status == LegalStatus.REVIEW_REQUIRED


def test_conflicting_fssai_licences_are_food_scoped_and_review_required():
    session = _session([
        _capture("cap-front", "FRONT", [
            _candidate("FSSAI_LICENCE", "10456789012345", "10456789012345", evidence_id="ev-front")
        ], "b" * 64),
        _capture("cap-back", "BACK", [
            _candidate("FSSAI_LICENCE", "10987654321098", "10987654321098", evidence_id="ev-back")
        ], "c" * 64),
    ], regulatory_class="FOOD")

    result = _finding(session, "CROSS_SURFACE_FSSAI_LICENCE_CONSISTENCY", food=True)
    assert result.status == LegalStatus.REVIEW_REQUIRED
    assert result.source_reference and "Regulation 5(7)" in result.source_reference


def test_capture_order_and_random_ids_do_not_change_logical_findings_or_fingerprint():
    def build(front_id, back_id, reverse=False):
        captures = [
            _capture(front_id, "FRONT", [
                _candidate("MRP", MrpNormalized(currency="INR", amount=137), "MRP Rs 137", evidence_id="random-front")
            ], "d" * 64),
            _capture(back_id, "BACK", [
                _candidate("MRP", MrpNormalized(currency="INR", amount=149), "MRP Rs 149", evidence_id="random-back")
            ], "e" * 64),
        ]
        return _session(list(reversed(captures)) if reverse else captures)

    first = build("uuid-z", "uuid-a")
    second = build("uuid-b", "uuid-y", reverse=True)

    def logical(session):
        return [
            (item.rule_id, item.status, item.reason, item.evaluated_value)
            for item in session.rule_evaluations
        ]

    assert logical(first) == logical(second)
    assert first.reproducibility.result_fingerprint == second.reproducibility.result_fingerprint


def test_officer_confirmed_correction_resolves_cross_surface_conflict():
    session = _session([
        _capture("cap-front", "FRONT", [
            _candidate("MRP", MrpNormalized(currency="INR", amount=137), "MRP Rs 137", evidence_id="ev-front")
        ], "f" * 64),
        _capture("cap-back", "BACK", [
            _candidate("MRP", MrpNormalized(currency="INR", amount=149), "MRP Rs 149", evidence_id="ev-back")
        ], "0" * 64),
    ])
    conflict_index = next(i for i, item in enumerate(session.aggregated_candidates) if item.field == "MRP")
    create_officer_declaration_override(
        session,
        candidate_index=conflict_index,
        field="MRP",
        confirmed_value="Rs 137",
        reason="Confirmed from the visible declaration",
        supporting_capture_id="cap-front",
        officer_user_id="officer-generic",
        officer_username="officer",
    )
    _update_session_compliance(session)

    assert not any(item.rule_id == "CROSS_SURFACE_MRP_CONSISTENCY" for item in session.rule_evaluations)
    assert _finding(session, "MRP_VALUE_FORMAT_VALIDITY").status == LegalStatus.PASS
    assert len(session.officer_declaration_overrides) == 1


def test_gemini_only_conflict_cannot_create_cross_surface_finding_or_fail():
    deterministic = _candidate(
        "MRP", MrpNormalized(currency="INR", amount=137), "MRP Rs 137", evidence_id="ev-ocr"
    )
    display = FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs 149",
        normalized_value=MrpNormalized(currency="INR", amount=149),
        observation_layer="RECONCILED",
        extraction_method="HYBRID_RECONCILIATION",
        observation_sources=["GOOGLE_GEMINI"],
        reconciliation_reason="GEMINI_EXPLICIT_EVIDENCE",
        provider_evidence=[ProviderEvidence(
            provider="GOOGLE_GEMINI",
            raw_text="MRP Rs 149",
            normalized_value={"currency": "INR", "amount": 149},
        )],
    )
    capture = CaptureRecord(
        capture_id="cap-front",
        view_id="FRONT",
        image_sha256="1" * 64,
        field_candidates=[display],
        deterministic_field_candidates=[deterministic],
    )
    session = _session([capture])

    assert not any(item.rule_id.startswith("CROSS_SURFACE_") for item in session.rule_evaluations)
    assert not any(item.status == LegalStatus.FAIL for item in session.rule_evaluations)


def test_phase_2_validity_results_remain_present_with_cross_surface_checks():
    session = _session([_capture("cap-front", "FRONT", [
        _candidate("MRP", MrpNormalized(currency="INR", amount=137), "MRP Rs 137 inclusive of all taxes", evidence_id="ev-mrp"),
        _candidate("NET_QUANTITY", NetQuantityNormalized(value=725, unit="g"), "Net Quantity 725 g", evidence_id="ev-nq"),
    ], "2" * 64)])

    assert _finding(session, "MRP_VALUE_FORMAT_VALIDITY").status == LegalStatus.PASS
    assert _finding(session, "MRP_TAX_WORDING_CONSISTENCY").status == LegalStatus.PASS
    assert _finding(session, "NET_QUANTITY_FORMAT_VALIDITY").status == LegalStatus.PASS
    assert _finding(session, "NET_QUANTITY_UNIT_VALIDITY").status == LegalStatus.PASS


def test_reliable_quantity_number_without_unit_reaches_validity_layer():
    session = _session_from_lines([_line("NET QUANTITY: 731")])
    candidate = next(item for item in session.deterministic_aggregated_candidates if item.field == "NET_QUANTITY")

    assert candidate.status == "DETECTED"
    assert candidate.raw_value == "NET QUANTITY: 731"
    assert isinstance(candidate.normalized_value, NetQuantityNormalized)
    assert candidate.normalized_value.value == 731
    assert candidate.normalized_value.unit == ""
    assert _finding(session, "NET_QUANTITY_FORMAT_VALIDITY").status == LegalStatus.PASS
    assert _finding(session, "NET_QUANTITY_UNIT_VALIDITY").status == LegalStatus.FAIL


def test_reliable_malformed_quantity_remains_reviewable_instead_of_not_identified():
    session = _session_from_lines([_line("NET QUANTITY: several grams")])
    candidate = next(item for item in session.deterministic_aggregated_candidates if item.field == "NET_QUANTITY")

    assert candidate.status == "REVIEW_REQUIRED"
    assert candidate.raw_value == "NET QUANTITY: several grams"
    assert candidate.evidence_ids == ["ev-0"]
    assert _finding(session, "NET_QUANTITY_FORMAT_VALIDITY").status == LegalStatus.REVIEW_REQUIRED


def test_reliable_impossible_date_reaches_date_validity_layer():
    session = _session_from_lines([_line("MFG DATE: 17/15/2025")])
    candidate = next(item for item in session.deterministic_aggregated_candidates if item.field == "MONTH_YEAR")

    assert candidate.status == "DETECTED"
    assert isinstance(candidate.normalized_value, DateNormalized)
    assert candidate.normalized_value.month == 15
    assert _finding(session, "DATE_DECLARATION_VALIDITY").status == LegalStatus.FAIL


def test_reliable_ocr_date_pair_reaches_chronology_rule():
    session = _session_from_lines([
        _line("MFG DATE: 21/08/2025"),
        _line("USE BY: 20/08/2025"),
    ])
    assert _finding(session, "DATE_CHRONOLOGY_CONSISTENCY").status == LegalStatus.FAIL


def test_reliable_malformed_food_licence_reaches_scoped_format_validator():
    session = _session_from_lines(
        [_line("FSSAI LICENCE NO: 1045678901234")],
        regulatory_class="FOOD",
    )
    candidate = next(item for item in session.deterministic_aggregated_candidates if item.field == "FSSAI_LICENCE")

    assert candidate.status == "DETECTED"
    assert candidate.raw_value == "1045678901234"
    assert candidate.evidence_ids == ["ev-0"]
    assert _finding(session, "FSSAI_LICENCE_FORMAT_VALIDITY", food=True).status == LegalStatus.FAIL


def test_mrp_raw_wording_survives_when_numeric_value_is_unparsed():
    session = _session_from_lines([_line("MRP amount unclear; GST extra")])
    candidate = next(item for item in session.deterministic_aggregated_candidates if item.field == "MRP")

    assert candidate.status == "DETECTED"
    assert candidate.normalized_value is None
    assert candidate.raw_value == "MRP amount unclear; GST extra"
    assert _finding(session, "MRP_VALUE_FORMAT_VALIDITY").status == LegalStatus.REVIEW_REQUIRED
    tax_result = _finding(session, "MRP_TAX_WORDING_CONSISTENCY")
    assert tax_result.status == LegalStatus.FAIL
    assert "GST extra" in tax_result.evaluated_value[0]


def test_uncertain_structurally_invalid_ocr_remains_review_required():
    session = _session_from_lines([_line("MFG DATE: 17/15/2025", confidence=0.61)])

    assert _finding(session, "DATE_DECLARATION_VALIDITY").status == LegalStatus.REVIEW_REQUIRED
    assert not any(
        item.field == "MONTH_YEAR" and item.status == LegalStatus.FAIL
        for item in session.rule_evaluations
    )


def test_valid_ocr_declarations_continue_to_pass():
    session = _session_from_lines([
        _line("MRP Rs 137 inclusive of all taxes"),
        _line("NET QUANTITY: 731 g"),
        _line("MFG DATE: 21/08/2025"),
        _line("USE BY: 22/08/2025"),
    ])

    assert _finding(session, "MRP_VALUE_FORMAT_VALIDITY").status == LegalStatus.PASS
    assert _finding(session, "MRP_TAX_WORDING_CONSISTENCY").status == LegalStatus.PASS
    assert _finding(session, "NET_QUANTITY_FORMAT_VALIDITY").status == LegalStatus.PASS
    assert _finding(session, "NET_QUANTITY_UNIT_VALIDITY").status == LegalStatus.PASS
    assert _finding(session, "DATE_DECLARATION_VALIDITY").status == LegalStatus.PASS
    assert _finding(session, "DATE_CHRONOLOGY_CONSISTENCY").status == LegalStatus.PASS


def test_ocr_package_with_multiple_independent_invalid_declarations_returns_all_failures():
    session = _session_from_lines([
        _line("MRP Rs 137 plus GST"),
        _line("NET QUANTITY: 731"),
        _line("MFG DATE: 17/15/2025"),
        _line("FSSAI LICENCE NO: 1045678901234"),
    ], regulatory_class="FOOD")

    failures = {
        item.rule_id
        for item in [*(session.rule_evaluations or []), *(session.food_label_evaluations or [])]
        if item.status == LegalStatus.FAIL
    }
    assert {
        "MRP_TAX_WORDING_CONSISTENCY",
        "NET_QUANTITY_UNIT_VALIDITY",
        "FSSAI_LICENCE_FORMAT_VALIDITY",
    }.issubset(failures)


def test_finalized_finding_preserves_real_observed_value_for_escalation():
    session = _session_from_lines([_line("MRP Rs 137 plus GST")])
    report = generate_inspection_report(session)
    finding = next(
        item for item in report.declaration_findings
        if item.rule_id == "MRP_TAX_WORDING_CONSISTENCY"
    )

    assert finding.status == "FAIL"
    assert finding.evaluated_value
    assert "MRP Rs 137 plus GST" in str(finding.evaluated_value)
