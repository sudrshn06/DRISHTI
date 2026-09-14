from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _frontend_source(relative_path: str) -> str:
    return (PROJECT_ROOT / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_primary_result_uses_officer_friendly_deterministic_outcomes():
    source = _frontend_source("components/inspection/OfficerResultSummary.jsx")

    for label in (
        "Compliant",
        "Non-compliant",
        "Needs Officer Review",
        "Not Applicable",
    ):
        assert label in source

    assert "Unreadable information has not been treated as legally absent" in source
    assert "session.overall_disposition" in source


def test_detected_information_must_be_reviewed_before_report_finalization():
    source = _frontend_source("pages/MultiViewInspection.jsx")

    assert "packageInfoReviewed" in source
    assert "readyToReviewReport = canFinalize && packageInfoReviewed" in source
    assert "I have reviewed this inspection report and approve it for finalization." in source
    assert "disabled={finalizing || !reportApproved}" in source
    assert "Approve and finalize report" in source


def test_photo_flow_is_mobile_friendly_and_unreadable_is_not_absent():
    inspection_source = _frontend_source("pages/MultiViewInspection.jsx")
    package_source = _frontend_source("components/inspection/PackageInformationCard.jsx")

    assert 'capture="environment"' in inspection_source
    assert "Package information detected" in package_source
    assert "Take another photograph" in package_source
    assert "Unreadable information is kept for officer review and is not treated as legally absent" in package_source
    correction_source = _frontend_source("components/inspection/DeclarationCorrectionModal.jsx")
    assert "Supporting photograph" in correction_source
    assert "The original machine observation remains preserved in the inspection record" in correction_source


def test_complaint_requires_review_and_never_submits_automatically():
    app_source = _frontend_source("App.jsx")
    inspection_source = _frontend_source("pages/MultiViewInspection.jsx")
    complaint_source = _frontend_source("pages/PrepareCase.jsx")
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    compose_source = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "showPortalConfirmation" in complaint_source
    assert "handleConfirmedPortalHandoff" in complaint_source
    assert "Confirm and open portal" in complaint_source
    assert "disabled={!portalConfigured}" in complaint_source
    assert "DRISHTI will not submit the complaint" in complaint_source
    assert "window.open(externalPortalUrl" in complaint_source
    assert "href={externalPortalUrl}" not in complaint_source
    assert "edaakhil.nic.in" not in inspection_source
    assert "VITE_EXTERNAL_COMPLAINT_PORTAL_URL" in app_source
    assert "VITE_EXTERNAL_COMPLAINT_PORTAL_URL=" in env_example
    assert "VITE_EXTERNAL_COMPLAINT_PORTAL_URL=${VITE_EXTERNAL_COMPLAINT_PORTAL_URL:-}" in compose_source


def test_primary_inspection_screen_keeps_provider_terms_out_of_officer_copy():
    source = _frontend_source("pages/MultiViewInspection.jsx")

    for forbidden in ("Gemini", "PaddleOCR", "AI_OBSERVED", "JSON schema"):
        assert forbidden not in source
