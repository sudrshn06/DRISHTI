"""Phase 4 evidence-manifest and escalation-boundary regressions."""

import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.schemas.applicability import ApplicabilityDecision, ApplicabilityStatus
from app.schemas.compliance import LegalStatus, RuleEvaluationResult
from app.schemas.inspection import CapturePlan, CaptureRecord, CaptureViewRequirement, InspectionSession
from app.schemas.ocr import FieldCandidate, MrpNormalized
from app.schemas.officer_review import OfficerDeclarationOverride
from app.services.evidence_package_service import build_evidence_manifest, has_confirmed_deterministic_fail
from app.services.report_service import generate_inspection_report
from app.services.reproducibility_service import build_reproducibility_record, default_capture_processing_provenance


REFERENCE_DATE = date(2026, 8, 27)


def _finding(rule_id, status, *, evaluated_value=None, capture_ids=None, evidence_ids=None):
    return RuleEvaluationResult(
        rule_id=rule_id,
        rule_version="1.0",
        field="MRP",
        status=LegalStatus(status),
        reason=f"Deterministic {status} reason",
        evaluated_value=evaluated_value,
        evidence_ids=evidence_ids or [],
        capture_ids=capture_ids or [],
        reference_date=REFERENCE_DATE,
        source_reference="Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 6",
        applicability=ApplicabilityDecision(
            rule_id=rule_id,
            status=ApplicabilityStatus.APPLICABLE,
            reason="Applicable",
        ),
    )


def _case(statuses=("FAIL", "REVIEW_REQUIRED", "PASS", "NOT_APPLICABLE")):
    observed = FieldCandidate(
        field="MRP", status="DETECTED", raw_value="MRP Rs 137 plus GST",
        normalized_value=MrpNormalized(currency="INR", amount=137),
        evidence_ids=["evidence-front"], capture_ids=["capture-front"], confidence=0.98,
        observation_sources=["PADDLEOCR"],
    )
    capture = CaptureRecord(
        capture_id="capture-front", evidence_id="image-front", view_id="FRONT",
        image_sha256="a" * 64, processing_provenance=default_capture_processing_provenance(),
        field_candidates=[observed], deterministic_field_candidates=[observed],
    )
    session = InspectionSession(
        inspection_id="phase-4-generic", reference_date=REFERENCE_DATE.isoformat(),
        product_category="GENERIC_RETAIL_PACKAGE", product_origin="DOMESTIC",
        regulatory_product_class="NON_FOOD", date_regulatory_regime="GENERAL",
        date_package_exemption="NONE", is_electronic="NON_ELECTRONIC",
        package_structure="SINGLE", alcohol_context="NON_ALCOHOLIC",
        capture_plan_id="phase-4-plan", capture_status="COMPLETE_EVIDENCE_CAPTURE",
        lifecycle_status="FINALIZED", captures=[capture],
        aggregated_candidates=[observed], deterministic_aggregated_candidates=[observed],
        rule_evaluations=[
            _finding(
                f"RULE_{index}_{status}", status,
                evaluated_value={
                    "observed_values": [{"normalized_value": {"amount": 137}, "raw_values": [observed.raw_value]}],
                    "source_views": ["FRONT"],
                    "expected_condition": "Stored deterministic condition",
                },
                capture_ids=[capture.capture_id], evidence_ids=observed.evidence_ids,
            )
            for index, status in enumerate(statuses)
        ],
    )
    session.reproducibility = build_reproducibility_record(session)
    plan = CapturePlan(
        capture_plan_id="phase-4-plan", name="Generic plan",
        views=[CaptureViewRequirement(view_id="FRONT", display_name="Front", required=True)],
    )
    return session, generate_inspection_report(session, plan), observed


def test_manifest_contains_complete_findings_and_separate_all_fail_list():
    session, report, _ = _case(("FAIL", "FAIL", "FAIL", "REVIEW_REQUIRED", "PASS", "NOT_APPLICABLE"))
    manifest = build_evidence_manifest(session, report)

    all_findings = manifest["findings"]["all_deterministic_findings"]
    failures = manifest["findings"]["confirmed_deterministic_fail_findings"]
    assert len(all_findings) == 6
    assert len(failures) == 3
    assert {item["status"] for item in all_findings} == {"FAIL", "REVIEW_REQUIRED", "PASS", "NOT_APPLICABLE"}
    assert all(item["evaluated_value"] and item["legal_reference"] for item in failures)
    summary = manifest["deterministic_escalation_summary"]
    assert summary["confirmed_fail_count"] == 3
    assert summary["generated_from"] == "FINALIZED_DETERMINISTIC_FAIL_FINDINGS_ONLY"
    assert all(item["evaluated_value"] for item in summary["findings"])


def test_manifest_preserves_cross_surface_and_image_provenance():
    session, report, _ = _case(("FAIL",))
    manifest = build_evidence_manifest(session, report)

    capture = manifest["capture_evidence"][0]
    finding = manifest["findings"]["confirmed_deterministic_fail_findings"][0]
    assert capture["image_sha256"] == "a" * 64
    assert capture["evidence_id"] == "image-front"
    assert capture["ocr_engine"] == "PADDLEOCR"
    assert finding["source_views"] == ["FRONT"]
    assert finding["evidence_ids"] == ["evidence-front"]
    assert finding["expected_condition"] == "Stored deterministic condition"


@pytest.mark.parametrize(
    ("finding_evidence", "expected_views"),
    [
        (["evidence-front"], ["FRONT"]),
        (["evidence-back"], ["BACK"]),
        (["evidence-front", "evidence-back"], ["BACK", "FRONT"]),
    ],
)
def test_manifest_finding_views_follow_only_linked_evidence(
    finding_evidence,
    expected_views,
):
    session, report, front_candidate = _case(("FAIL",))
    back_candidate = front_candidate.model_copy(update={
        "raw_value": "MRP Rs 139 plus GST",
        "evidence_ids": ["evidence-back"],
        "capture_ids": ["capture-back"],
    })
    session.captures.append(CaptureRecord(
        capture_id="capture-back",
        evidence_id="image-back",
        view_id="BACK",
        image_sha256="b" * 64,
        processing_provenance=default_capture_processing_provenance(),
        field_candidates=[back_candidate],
        deterministic_field_candidates=[back_candidate],
    ))
    finding = report.declaration_findings[0]
    finding.evidence_ids = finding_evidence
    # Historical aggregate capture provenance can be broader than this
    # finding's exact supporting evidence and must not widen its source views.
    finding.capture_ids = ["capture-front", "capture-back"]
    finding.evaluated_value = {"source_views": ["FRONT", "BACK"]}

    exported = build_evidence_manifest(session, report)["findings"][
        "confirmed_deterministic_fail_findings"
    ][0]

    assert exported["source_views"] == expected_views
    assert exported["capture_ids"] == [
        capture.capture_id
        for capture in sorted(
            (
                capture
                for capture in session.captures
                if capture.view_id in expected_views
            ),
            key=lambda capture: capture.capture_id,
        )
    ]


def test_manifest_preserves_officer_correction_without_rewriting_machine_observation():
    session, report, observed = _case(("FAIL",))
    confirmed = observed.model_copy(update={
        "raw_value": "MRP Rs 137 inclusive of all taxes",
        "observation_layer": "OFFICER_CONFIRMED",
        "extraction_method": "OFFICER_CONFIRMED",
        "observation_sources": ["OFFICER_CONFIRMED"],
    })
    session.officer_declaration_overrides = [OfficerDeclarationOverride(
        override_id="override-generic", target_key="MRP", field="MRP",
        observed_candidate=observed, confirmed_candidate=confirmed,
        supporting_capture_id="capture-front", reason="Visible declaration confirmed",
        officer_user_id="officer-id", officer_username="officer",
        confirmed_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
    )]
    session.deterministic_aggregated_candidates = [confirmed]

    correction = build_evidence_manifest(session, report)["declarations"]["officer_corrections"][0]
    assert correction["original_machine_observation"]["raw_observed_text"] == observed.raw_value
    assert correction["confirmed_declaration"]["officer_confirmed"] is True
    assert correction["supporting_capture_id"] == "capture-front"


@pytest.mark.parametrize("notes", ["", "Officer-controlled context only"])
def test_manifest_export_supports_optional_distinct_officer_notes(notes):
    session, report, _ = _case(("FAIL",))
    manifest = build_evidence_manifest(session, report, officer_notes=notes, complaint_draft="Stored factual summary")
    assert manifest["officer_material"]["officer_notes"] == notes
    assert manifest["officer_material"]["officer_complaint_draft"] == "Stored factual summary"
    assert manifest["officer_material"]["content_owner"] == "OFFICER"
    assert manifest["officer_material"]["machine_findings_unchanged"] is True
    assert "officer_complaint_draft" not in manifest["deterministic_escalation_summary"]


def test_manifest_nested_values_are_json_safe_without_flattening_structures():
    session, report, _ = _case(("FAIL",))
    report.declaration_findings[0].evaluated_value = {
        "measured": Decimal("137.50"),
        "checked_at": datetime(2026, 8, 27, 10, 30, tzinfo=timezone.utc),
        "nested": ({"values": (1, 2)},),
    }

    manifest = build_evidence_manifest(session, report)
    evaluated = manifest["findings"]["confirmed_deterministic_fail_findings"][0]["evaluated_value"]
    assert evaluated == {
        "measured": "137.50",
        "checked_at": "2026-08-27T10:30:00+00:00",
        "nested": [{"values": [1, 2]}],
    }
    json.dumps(manifest, allow_nan=False)


def test_manifest_is_stable_secret_free_and_does_not_mutate_finalized_state():
    session, report, _ = _case(("FAIL", "REVIEW_REQUIRED"))
    before_session = session.model_dump(mode="json")
    before_report = report.model_dump(mode="json")
    first = build_evidence_manifest(session, report, officer_notes="", complaint_draft="Summary")
    second = build_evidence_manifest(session, report, officer_notes="", complaint_draft="Summary")

    assert first == second
    assert session.model_dump(mode="json") == before_session
    assert report.model_dump(mode="json") == before_report
    serialized = json.dumps(first).lower()
    for forbidden in ("api_key", "jwt", "password", "database_url", "object_key", "filesystem"):
        assert forbidden not in serialized
    assert first["external_submission"]["submitted_by_drishti"] is False


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [(("FAIL",), True), (("REVIEW_REQUIRED",), False), (("PASS",), False), ((), False)],
)
def test_escalation_requires_confirmed_deterministic_fail(statuses, expected):
    _, report, _ = _case(statuses)
    assert has_confirmed_deterministic_fail(report) is expected
