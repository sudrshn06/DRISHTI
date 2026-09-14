"""Compact, product-agnostic SIH26034 final regression fixtures."""

from datetime import date
from types import SimpleNamespace

import pytest

from app.api.routes.inspections import _update_session_compliance
from app.schemas.compliance import LegalStatus
from app.repositories.inspection_repository import InspectionRepository
from app.schemas.inspection import (
    CapturePlan,
    CaptureRecord,
    CaptureViewRequirement,
    InspectionSession,
)
from app.schemas.ocr import DateNormalized, FieldCandidate, MrpNormalized, NetQuantityNormalized
from app.schemas.report import OverallDisposition
from app.services.compliance_service import orchestrate_compliance
from app.services.fssai_compliance_service import evaluate_fssai_compliance
from app.services.officer_review_service import create_officer_declaration_override, rebuild_authoritative_candidates
from app.services.report_service import compute_overall_disposition
from app.services.workflow_service import WorkflowService


REFERENCE_DATE = date(2023, 8, 24)


def _evaluate(candidates):
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
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        inspection_complete=True,
    )


def _result(results, rule_id):
    return next(item for item in results if item.rule_id == rule_id)


@pytest.mark.parametrize(
    ("candidates", "rule_id", "expected"),
    [
        ([FieldCandidate(
            field="MRP", status="DETECTED", raw_value="MRP Rs 142 inclusive of all taxes",
            normalized_value=MrpNormalized(currency="INR", amount=142), confidence=0.97,
        )], "MRP_VALUE_FORMAT_VALIDITY", LegalStatus.PASS),
        ([FieldCandidate(
            field="MRP", status="DETECTED", raw_value="MRP Rs 142 plus GST",
            normalized_value=MrpNormalized(currency="INR", amount=142), confidence=0.97,
        )], "MRP_TAX_WORDING_CONSISTENCY", LegalStatus.FAIL),
        ([FieldCandidate(
            field="NET_QUANTITY", status="REVIEW_REQUIRED", raw_value="Net quantity 640", confidence=0.91,
        )], "NET_QUANTITY_UNIT_VALIDITY", LegalStatus.REVIEW_REQUIRED),
        ([FieldCandidate(
            field="NET_QUANTITY", status="REVIEW_REQUIRED", raw_value="Net quantity several units", confidence=0.90,
        )], "NET_QUANTITY_FORMAT_VALIDITY", LegalStatus.REVIEW_REQUIRED),
        ([FieldCandidate(
            field="MONTH_YEAR", status="DETECTED", raw_value="Manufactured 31/02/2023",
            normalized_value=DateNormalized(type="MANUFACTURED", day=31, month=2, year=2023), confidence=0.98,
        )], "DATE_DECLARATION_VALIDITY", LegalStatus.FAIL),
        ([
            FieldCandidate(
                field="MONTH_YEAR", status="DETECTED", raw_value="Manufactured 12/08/2023",
                normalized_value=DateNormalized(type="MANUFACTURED", day=12, month=8, year=2023), confidence=0.98,
            ),
            FieldCandidate(
                field="MONTH_YEAR", status="DETECTED", raw_value="Use by 11/08/2023",
                normalized_value=DateNormalized(type="USE_BY", day=11, month=8, year=2023), confidence=0.98,
            ),
        ], "DATE_CHRONOLOGY_CONSISTENCY", LegalStatus.FAIL),
        ([FieldCandidate(
            field="MRP", status="REVIEW_REQUIRED", raw_value="MRP Rs 142 plus GST",
            normalized_value=MrpNormalized(currency="INR", amount=142), confidence=0.54,
        )], "MRP_TAX_WORDING_CONSISTENCY", LegalStatus.REVIEW_REQUIRED),
        ([FieldCandidate(field="MRP", status="NOT_DETECTED")], "MRP_DECLARATION_PRESENCE", LegalStatus.REVIEW_REQUIRED),
    ],
)
def test_compact_declaration_validity_fixtures(candidates, rule_id, expected):
    assert _result(_evaluate(candidates), rule_id).status == expected


def test_malformed_food_licence_is_food_scoped():
    malformed = FieldCandidate(field="FSSAI_LICENCE", status="DETECTED", raw_value="1045678901234")
    result = _result(
        evaluate_fssai_compliance([malformed], REFERENCE_DATE),
        "FSSAI_LICENCE_FORMAT_VALIDITY",
    )
    assert result.status == LegalStatus.FAIL


def _mrp(value, evidence):
    return FieldCandidate(
        field="MRP", status="DETECTED", raw_value=f"MRP Rs {value}",
        normalized_value=MrpNormalized(currency="INR", amount=value),
        evidence_ids=[evidence], confidence=0.98,
    )


def _session(front_value, back_value):
    captures = [
        CaptureRecord(
            capture_id="front-capture", view_id="FRONT", image_sha256="a" * 64,
            field_candidates=[_mrp(front_value, "front-evidence")],
            deterministic_field_candidates=[_mrp(front_value, "front-evidence")],
        ),
        CaptureRecord(
            capture_id="back-capture", view_id="BACK", image_sha256="b" * 64,
            field_candidates=[_mrp(back_value, "back-evidence")],
            deterministic_field_candidates=[_mrp(back_value, "back-evidence")],
        ),
    ]
    session = InspectionSession(
        inspection_id="generic-multi-surface", reference_date=REFERENCE_DATE.isoformat(),
        product_category="GENERIC_RETAIL_PACKAGE", product_origin="DOMESTIC",
        regulatory_product_class="NON_FOOD", date_regulatory_regime="GENERAL",
        date_package_exemption="NONE", is_electronic="NON_ELECTRONIC",
        package_structure="SINGLE", alcohol_context="NON_ALCOHOLIC",
        capture_plan_id="plan_software_1", capture_status="COMPLETE_EVIDENCE_CAPTURE",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION", captures=captures,
    )
    rebuild_authoritative_candidates(session)
    _update_session_compliance(session)
    return session


def test_identical_and_conflicting_cross_surface_values_remain_distinct():
    identical = _session(142, 142)
    conflicting = _session(142, 146)
    assert not any(item.rule_id == "CROSS_SURFACE_MRP_CONSISTENCY" for item in identical.rule_evaluations)
    conflict = _result(conflicting.rule_evaluations, "CROSS_SURFACE_MRP_CONSISTENCY")
    assert conflict.status == LegalStatus.REVIEW_REQUIRED
    assert conflict.capture_ids == ["back-capture", "front-capture"]


def test_officer_correction_resolves_conflict_without_copying_history():
    session = _session(142, 146)
    candidate_index = next(
        index for index, candidate in enumerate(session.aggregated_candidates)
        if candidate.field == "MRP"
    )
    create_officer_declaration_override(
        session,
        candidate_index=candidate_index,
        field="MRP",
        confirmed_value="Rs 142",
        reason="Officer verified the visible declaration",
        supporting_capture_id="front-capture",
        officer_user_id="officer-generic",
        officer_username="officer",
    )
    _update_session_compliance(session)
    assert not any(item.rule_id == "CROSS_SURFACE_MRP_CONSISTENCY" for item in session.rule_evaluations)
    assert len(session.officer_declaration_overrides) == 1


def test_multiple_independent_violations_are_all_retained():
    candidates = [
        FieldCandidate(
            field="MRP", status="DETECTED", raw_value="MRP Rs 142 plus taxes",
            normalized_value=MrpNormalized(currency="INR", amount=142), confidence=0.98,
        ),
        FieldCandidate(
            field="NET_QUANTITY", status="DETECTED", raw_value="Net quantity 12 boxes",
            normalized_value=NetQuantityNormalized(value=12, unit="boxes"), confidence=0.98,
        ),
    ]
    failures = {item.rule_id for item in _evaluate(candidates) if item.status == LegalStatus.FAIL}
    assert {"MRP_TAX_WORDING_CONSISTENCY", "NET_QUANTITY_UNIT_VALIDITY"}.issubset(failures)


@pytest.mark.parametrize(
    "companion_status",
    ["REVIEW_REQUIRED", "PASS", "NOT_APPLICABLE", "FAIL"],
)
def test_any_deterministic_fail_controls_overall_disposition(companion_status):
    findings = [
        SimpleNamespace(status="FAIL", rule_id="DETERMINISTIC_FAIL"),
        SimpleNamespace(status=companion_status, rule_id="COMPANION_RESULT"),
    ]

    disposition, _ = compute_overall_disposition(
        findings,
        [],
        "COMPLETE_EVIDENCE_CAPTURE",
        "INSUFFICIENT_FOR_ABSENCE_EVALUATION",
    )

    assert disposition == OverallDisposition.VIOLATIONS_FOUND
    assert [finding.status for finding in findings] == ["FAIL", companion_status]


def test_repeated_finalization_reuses_snapshot_and_fingerprint(monkeypatch):
    session = _session(142, 142)
    plan = CapturePlan(
        capture_plan_id="plan_software_1",
        name="Generic multi-surface plan",
        views=[
            CaptureViewRequirement(view_id="FRONT", display_name="Front"),
            CaptureViewRequirement(view_id="BACK", display_name="Back"),
        ],
    )
    writes = {"snapshot": 0, "state": 0}
    monkeypatch.setattr(
        InspectionRepository,
        "save_report_snapshot",
        staticmethod(lambda *_args: writes.__setitem__("snapshot", writes["snapshot"] + 1)),
    )
    monkeypatch.setattr(
        InspectionRepository,
        "update_inspection_state",
        staticmethod(lambda *_args: writes.__setitem__("state", writes["state"] + 1)),
    )

    first = WorkflowService.finalize_inspection(session, plan, db=object())
    report_id = first.report_snapshot.metadata.report_id
    fingerprint = first.reproducibility.result_fingerprint
    second = WorkflowService.finalize_inspection(session, plan, db=object())

    assert second.report_snapshot.metadata.report_id == report_id
    assert second.reproducibility.result_fingerprint == fingerprint
    assert writes == {"snapshot": 1, "state": 1}
