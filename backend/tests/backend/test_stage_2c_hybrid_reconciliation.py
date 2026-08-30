"""Focused Stage 2C safety contract for hybrid OCR/Gemini reconciliation."""

from datetime import date

from app.schemas.gemini import (
    BusinessObservation,
    CountryOfOriginObservation,
    DateObservation,
    GeminiAnalysisStatus,
    GeminiAuditMetadata,
    GeminiPackageAnalysis,
    MrpObservation,
    StructuredDeclarationObservations,
    TextObservation,
)
from app.schemas.inspection import CapturePlan, CaptureRecord
from app.schemas.ocr import (
    DateNormalized,
    FieldCandidate,
    MrpNormalized,
)
from app.services.compliance_service import orchestrate_compliance
from app.services.hybrid_reconciliation_service import reconcile_capture_candidates
from app.services.inspection_service import evaluate_evidence_sufficiency


def _analysis(**declarations) -> GeminiPackageAnalysis:
    return GeminiPackageAnalysis(
        status=GeminiAnalysisStatus.SUCCEEDED,
        declarations=StructuredDeclarationObservations(**declarations),
        metadata=GeminiAuditMetadata(
            model="mock-model",
            schema_version="2.0",
            prompt_version="2.0",
            generated_at="2026-08-29T00:00:00Z",
        ),
    )


def _text(raw: str, value: str, **overrides) -> TextObservation:
    return TextObservation(
        raw_text=raw,
        value=value,
        confidence=overrides.pop("confidence", 0.96),
        uncertain=overrides.pop("uncertain", False),
        contradiction=overrides.pop("contradiction", False),
        evidence_note=overrides.pop("evidence_note", "Explicitly visible declaration"),
        **overrides,
    )


def _reconcile(paddle: list[FieldCandidate], analysis: GeminiPackageAnalysis):
    return reconcile_capture_candidates(
        paddle,
        analysis,
        capture_id="capture-back",
        view_id="BACK",
    )


def _field(candidates: list[FieldCandidate], field: str) -> FieldCandidate:
    return next(candidate for candidate in candidates if candidate.field == field)


def test_paddle_and_gemini_agreement_produces_high_confidence_candidate():
    paddle = [FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs 110",
        normalized_value=MrpNormalized(currency="INR", amount=110),
        evidence_ids=["ocr-mrp"],
        confidence=0.94,
    )]
    gemini = _analysis(mrp=MrpObservation(
        raw_text="MRP ₹110.00 inclusive of all taxes",
        amount=110,
        currency="INR",
        confidence=0.98,
        uncertain=False,
        contradiction=False,
        evidence_note="Explicit MRP declaration",
    ))

    candidate = _field(_reconcile(paddle, gemini), "MRP")

    assert candidate.status == "DETECTED"
    assert candidate.reconciliation_reason == "AGREEMENT"
    assert candidate.normalized_value.amount == 110
    assert candidate.observation_sources == ["PADDLEOCR", "GOOGLE_GEMINI"]
    assert {item.provider for item in candidate.provider_evidence} == {"PADDLEOCR", "GOOGLE_GEMINI"}


def test_paddle_date_token_can_receive_gemini_contextual_association():
    paddle = [FieldCandidate(
        field="MONTH_YEAR",
        status="DETECTED",
        raw_value="15/05/2024",
        normalized_value=DateNormalized(type="UNKNOWN", day=15, month=5, year=2024),
        evidence_ids=["ocr-date"],
        confidence=0.95,
    )]
    gemini = _analysis(dates=[DateObservation(
        raw_text="Packed On: 15/05/2024",
        date_type="PACKED",
        day=15,
        month=5,
        year=2024,
        confidence=0.98,
        uncertain=False,
        contradiction=False,
        evidence_note="Date printed beside Packed On",
    )])

    candidate = _field(_reconcile(paddle, gemini), "MONTH_YEAR")

    assert candidate.status == "DETECTED"
    assert candidate.normalized_value.type == "PACKED"
    assert candidate.reconciliation_reason == "OCR_SUPPORTED_GEMINI_CONTEXT"
    assert candidate.evidence_ids == ["ocr-date"]


def test_gemini_can_recover_explicit_mrp_missed_by_paddle():
    paddle = [FieldCandidate(field="MRP", status="REVIEW_REQUIRED", raw_value="MRP:", evidence_ids=["ocr-label"])]
    gemini = _analysis(mrp=MrpObservation(
        raw_text="MRP ₹: 110.00 (incl. of all taxes)",
        amount=110,
        currency="₹",
        confidence=1.0,
        uncertain=False,
        contradiction=False,
        evidence_note="Amount explicitly follows MRP label",
    ))

    candidate = _field(_reconcile(paddle, gemini), "MRP")

    assert candidate.status == "DETECTED"
    assert candidate.normalized_value.amount == 110
    assert candidate.reconciliation_reason == "GEMINI_EXPLICIT_EVIDENCE"
    assert candidate.evidence_ids == ["ocr-label"]


def test_gemini_recovers_nutrition_values_missed_by_paddle():
    paddle = [FieldCandidate(
        field="FSSAI_NUTRITION",
        status="DETECTED",
        raw_value="Energy | Protein | Carbohydrate | Fat",
        evidence_ids=["ocr-nutrition"],
    )]
    gemini = _analysis(nutrition=_text(
        "Nutrition per 100 g: Energy 343 kcal; Protein 22.3 g; Carbohydrate 63.1 g; Fat 1.7 g",
        "Energy 343 kcal; Protein 22.3 g; Carbohydrate 63.1 g; Fat 1.7 g",
    ))

    candidate = _field(_reconcile(paddle, gemini), "FSSAI_NUTRITION")

    assert candidate.status == "DETECTED"
    assert "343 kcal" in candidate.raw_value
    assert candidate.reconciliation_reason == "GEMINI_EXPLICIT_EVIDENCE"


def test_gemini_cleans_ocr_allergen_grouping_when_tokens_are_supported():
    paddle = [FieldCandidate(
        field="FSSAI_ALLERGENS",
        status="DETECTED",
        raw_value="Allergen Advice: Packed in a facility COOKING INSTRUCTIONS that also handles wheat, peanuts, soyabean, sesame and nuts.",
        evidence_ids=["ocr-allergens"],
    )]
    gemini = _analysis(allergens=_text(
        "Allergen Advice: facility also handles wheat, peanuts, soyabean, sesame and nuts",
        "wheat, peanuts, soyabean, sesame and nuts",
    ))

    candidate = _field(_reconcile(paddle, gemini), "FSSAI_ALLERGENS")

    assert candidate.raw_value == "wheat, peanuts, soyabean, sesame and nuts"
    assert candidate.reconciliation_reason == "OCR_SUPPORTED_GEMINI_CONTEXT"


def test_provider_disagreement_requires_officer_review_and_preserves_both_values():
    paddle = [FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs 100",
        normalized_value=MrpNormalized(currency="INR", amount=100),
        evidence_ids=["ocr-mrp"],
    )]
    gemini = _analysis(mrp=MrpObservation(
        raw_text="MRP Rs 110",
        amount=110,
        currency="INR",
        confidence=0.99,
        uncertain=False,
        contradiction=True,
        evidence_note="Visible price differs from OCR",
    ))

    candidate = _field(_reconcile(paddle, gemini), "MRP")

    assert candidate.status == "REVIEW_REQUIRED"
    assert candidate.reconciliation_reason == "PROVIDER_CONFLICT"
    assert [item.raw_text for item in candidate.provider_evidence] == ["MRP Rs 100", "MRP Rs 110"]


def test_gemini_uncertainty_remains_review_required():
    paddle = [FieldCandidate(field="MRP", status="NOT_DETECTED")]
    gemini = _analysis(mrp=MrpObservation(
        raw_text="MRP perhaps Rs 110",
        amount=110,
        currency="INR",
        confidence=0.55,
        uncertain=True,
        contradiction=False,
        evidence_note="Price is partly obscured",
    ))

    candidate = _field(_reconcile(paddle, gemini), "MRP")

    assert candidate.status == "REVIEW_REQUIRED"
    assert candidate.provider_evidence[-1].uncertain is True


def test_timeout_and_unavailable_gemini_leave_paddle_unchanged():
    paddle = [FieldCandidate(
        field="MRP",
        status="DETECTED",
        raw_value="MRP Rs 110",
        normalized_value=MrpNormalized(currency="INR", amount=110),
        evidence_ids=["ocr-mrp"],
    )]
    for status in (GeminiAnalysisStatus.TIMEOUT, GeminiAnalysisStatus.DISABLED, GeminiAnalysisStatus.FAILED):
        analysis = _analysis()
        analysis.status = status
        result = _reconcile(paddle, analysis)
        assert result == paddle
        assert result is not paddle


def test_unsupported_country_origin_inference_from_marketer_address_is_rejected():
    paddle = [
        FieldCandidate(field="COUNTRY_OF_ORIGIN", status="NOT_DETECTED"),
        FieldCandidate(field="MANUFACTURER_PACKER_IMPORTER", status="REVIEW_REQUIRED", raw_value="MARKETED BY:"),
    ]
    gemini = _analysis(
        manufacturer_packer_importer=[BusinessObservation(
            raw_text="Marketed by Tata Consumer Products Limited, Kolkata, West Bengal, India",
            role="MARKETER",
            name="Tata Consumer Products Limited",
            address="Kolkata, West Bengal, India",
            confidence=0.99,
            uncertain=False,
            contradiction=False,
            evidence_note="Explicit marketer declaration",
        )],
        country_of_origin=CountryOfOriginObservation(
            raw_text="Marketed by Tata Consumer Products Limited, Kolkata, West Bengal, India",
            declaration_type="ORIGIN",
            country_text="India",
            confidence=0.9,
            uncertain=False,
            contradiction=False,
            evidence_note="Country appears in marketer address",
        ),
    )

    result = _reconcile(paddle, gemini)
    origin = _field(result, "COUNTRY_OF_ORIGIN")
    marketer = _field(result, "MANUFACTURER_PACKER_IMPORTER")

    assert origin.status == "NOT_DETECTED"
    assert origin.reconciliation_reason is None
    assert marketer.status == "DETECTED"
    assert marketer.normalized_value.address.endswith("India")


def test_explicit_country_origin_declaration_is_allowed():
    paddle = [FieldCandidate(field="COUNTRY_OF_ORIGIN", status="NOT_DETECTED")]
    gemini = _analysis(country_of_origin=CountryOfOriginObservation(
        raw_text="Country of Origin: India",
        declaration_type="ORIGIN",
        country_text="India",
        confidence=0.99,
        uncertain=False,
        contradiction=False,
        evidence_note="Explicit country-of-origin label",
    ))

    candidate = _field(_reconcile(paddle, gemini), "COUNTRY_OF_ORIGIN")

    assert candidate.status == "DETECTED"
    assert candidate.normalized_value.country_text == "India"


def test_origin_label_without_matching_country_text_is_not_promoted():
    paddle = [FieldCandidate(field="COUNTRY_OF_ORIGIN", status="NOT_DETECTED")]
    gemini = _analysis(country_of_origin=CountryOfOriginObservation(
        raw_text="Country of Origin: Nepal",
        declaration_type="ORIGIN",
        country_text="India",
        confidence=0.99,
        uncertain=False,
        contradiction=False,
        evidence_note="Model value contradicts the visible declaration",
    ))

    candidate = _field(_reconcile(paddle, gemini), "COUNTRY_OF_ORIGIN")

    assert candidate.status == "NOT_DETECTED"


def test_legal_engine_remains_deterministic_and_evidence_sufficiency_is_unchanged():
    paddle = [FieldCandidate(field="MRP", status="NOT_DETECTED")]
    gemini = _analysis(mrp=MrpObservation(
        raw_text="MRP Rs 110 inclusive of all taxes",
        amount=110,
        currency="INR",
        confidence=0.99,
        uncertain=False,
        contradiction=False,
        evidence_note="Explicit MRP declaration",
    ))
    candidates = _reconcile(paddle, gemini)

    results = orchestrate_compliance(
        candidates=candidates,
        reference_date=date(2026, 8, 29),
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin="DOMESTIC",
        regulatory_category="NON_FOOD",
        is_electronic="NON_ELECTRONIC",
        package_structure="SINGLE",
        alcohol_context="NON_ALCOHOLIC",
        date_regulatory_regime="GENERAL",
        date_package_exemption="NONE",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        inspection_complete=False,
    )

    assert results
    assert all(result.status.value in {"PASS", "FAIL", "REVIEW_REQUIRED", "NOT_APPLICABLE"} for result in results)
    plan = CapturePlan(capture_plan_id="locked", name="Locked", views=[], absence_evaluation_eligible=False)
    assert evaluate_evidence_sufficiency(plan, [CaptureRecord(capture_id="c", view_id="BACK")]) == "INSUFFICIENT_FOR_ABSENCE_EVALUATION"


def test_reconciliation_contains_no_tata_product_hardcoding():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "app" / "services" / "hybrid_reconciliation_service.py").read_text(encoding="utf-8").lower()
    for forbidden in ("tata", "sampann", "toor dal"):
        assert forbidden not in source
