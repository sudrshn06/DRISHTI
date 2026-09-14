from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _source(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_indexeddb_write_resolves_on_transaction_completion():
    source = _source("frontend/src/services/pendingCaptureStore.js")

    assert "transaction.oncomplete" in source
    # The one remaining direct resolution belongs to opening IndexedDB, not to
    # a write transaction. Writes resolve from transaction.oncomplete.
    assert source.count("request.onsuccess = () => resolve(request.result)") == 1


def test_leave_warning_is_limited_to_non_durable_pending_photographs():
    source = _source("frontend/src/pages/MultiViewInspection.jsx")

    assert "hasUnsafePendingCapture" in source
    assert "if (!hasUnsafePendingCapture) return undefined" in source
    assert "item.persisted === false" in source


def test_saved_photographs_use_the_authenticated_capture_endpoint():
    api_source = _source("frontend/src/services/api.js")
    inspection_source = _source("frontend/src/pages/MultiViewInspection.jsx")

    assert "`/inspections/${inspectionId}/captures/${captureId}/image`" in api_source
    assert "getCaptureImage(inspectionId, capture.capture_id)" in inspection_source
    assert "object_key" not in inspection_source
    assert "minio" not in inspection_source.lower()


def test_phone_and_tablet_have_reachable_primary_actions_and_optional_details():
    source = _source("frontend/src/pages/MultiViewInspection.jsx")

    assert "mobile-primary-action" in source
    assert "lg:hidden" in source
    assert "View details" in source
    assert "<details" in source
    assert "<EvidenceInspectorPanel" in source


def test_correction_resets_report_approval_and_uses_existing_supporting_photograph():
    inspection_source = _source("frontend/src/pages/MultiViewInspection.jsx")
    correction_source = _source("frontend/src/components/inspection/DeclarationCorrectionModal.jsx")

    assert "setReportApproved(false)" in inspection_source
    assert "Supporting photograph" in correction_source
    assert "original machine observation remains preserved" in correction_source.lower()


def test_absence_safety_document_covers_each_required_boundary():
    source = _source("docs/6-absence-evaluation-safety.md").lower()

    for required in (
        "surface coverage",
        "image quality",
        "contradiction",
        "rule-specific evidence",
        "absence_evaluation_eligible=false",
        "officer",
    ):
        assert required in source
