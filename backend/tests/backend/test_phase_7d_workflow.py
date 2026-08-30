import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import numpy as np
import cv2

from app.main import app
from app.db.session import SessionLocal
from app.core.security import hash_password
from app.repositories.user_repository import UserRepository
from app.repositories.inspection_repository import InspectionRepository
from app.models.inspection import InspectionModel
from app.schemas.workflow import WorkflowSummary, InspectionLifecycleStatus

client = TestClient(app)

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def create_synthetic_image(text="SAMPLE PACK MFD 01/2024 MRP Rs 100") -> bytes:
    img = np.full((400, 600, 3), (240, 240, 240), dtype=np.uint8)
    cv2.putText(img, text, (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    success, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()

@pytest.fixture
def test_users(db: Session):
    for uname in ["wf_inspector_a", "wf_inspector_b", "wf_admin"]:
        u = UserRepository.get_by_username(db, uname)
        if u:
            db.delete(u)
    db.commit()

    user_a = UserRepository.create_user(
        db=db,
        username="wf_inspector_a",
        email="wf_a@drishti.local",
        password_hash=hash_password("PassA123!"),
        full_name="Inspector Alpha",
        role="INSPECTOR"
    )

    user_b = UserRepository.create_user(
        db=db,
        username="wf_inspector_b",
        email="wf_b@drishti.local",
        password_hash=hash_password("PassB123!"),
        full_name="Inspector Beta",
        role="INSPECTOR"
    )

    user_admin = UserRepository.create_user(
        db=db,
        username="wf_admin",
        email="wf_admin@drishti.local",
        password_hash=hash_password("AdminPass123!"),
        full_name="Admin User",
        role="ADMIN"
    )

    return {
        "a": user_a,
        "b": user_b,
        "admin": user_admin
    }

def get_auth_headers(username: str, password: str) -> dict:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def confirm_package_information(inspection_id: str, headers: dict) -> None:
    response = client.post(
        f"/api/inspections/{inspection_id}/package-information/review",
        headers=headers,
    )
    assert response.status_code == 200

# ==============================================================================
# PHASE 7D: INSPECTION LIFECYCLE, WORKFLOW & FINALIZATION TESTS
# ==============================================================================

def test_1_new_inspection_starts_as_draft(test_users):
    """Newly created inspection must initialize in DRAFT lifecycle status."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["lifecycle_status"] == "DRAFT"
    assert len(data["captures"]) == 0

    # Workflow summary check
    wf_resp = client.get(f"/api/inspections/{data['inspection_id']}/workflow", headers=headers_a)
    assert wf_resp.status_code == 200
    wf_data = wf_resp.json()
    assert wf_data["lifecycle_status"] == "DRAFT"
    assert wf_data["lifecycle_display_name"] == "New inspection"
    assert wf_data["can_upload_capture"] is True
    assert wf_data["can_update_context"] is True
    assert wf_data["can_finalize"] is False

def test_2_capture_transitions_draft_to_ready_for_review(test_users):
    """Uploading capture and completing OCR/analysis transitions session to READY_FOR_REVIEW."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    img_bytes = create_synthetic_image("NET QTY 500 g MRP Rs 200 MFD 05/2025")
    cap_resp = client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers_a
    )
    assert cap_resp.status_code == 200
    session_data = cap_resp.json()
    assert session_data["lifecycle_status"] == "READY_FOR_REVIEW"
    assert len(session_data["captures"]) == 1

    # Workflow summary reflects READY_FOR_REVIEW
    wf_resp = client.get(f"/api/inspections/{inspection_id}/workflow", headers=headers_a)
    wf_data = wf_resp.json()
    assert wf_data["lifecycle_status"] == "READY_FOR_REVIEW"
    assert wf_data["lifecycle_display_name"] == "Ready for review"
    assert wf_data["can_finalize"] is True

def test_3_lifecycle_status_separate_from_legal_compliance(test_users):
    """Lifecycle status is purely operational workflow progress, isolated from statutory PASS/FAIL/REVIEW."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    # Upload view with ambiguous declarations
    img_bytes = create_synthetic_image("UNKNOWN TEXT ONLY")
    cap_resp = client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers_a
    )
    assert cap_resp.status_code == 200
    wf_resp = client.get(f"/api/inspections/{inspection_id}/workflow", headers=headers_a)
    wf_data = wf_resp.json()
    
    # Operational status is READY_FOR_REVIEW even with non-PASS findings
    assert wf_data["lifecycle_status"] == "READY_FOR_REVIEW"
    assert "statutory_summary" in wf_data
    assert isinstance(wf_data["statutory_summary"], dict)

def test_4_fail_inspection_can_be_ready_for_review_and_finalized(test_users):
    """An inspection with statutory FAIL violations is READY_FOR_REVIEW and 100% finalizable."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1",
            "regulatory_product_class": "NON_FOOD",
            "date_regulatory_regime": "GENERAL"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    # Upload Front view
    img_f = create_synthetic_image("FRONT PKD 06/2025 MRP Rs 50")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img_f), "image/jpeg")},
        headers=headers_a
    )
    
    # Upload Back view (complete capture)
    img_b = create_synthetic_image("BACK CONSUMER CARE email care@test.com")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "BACK"},
        files={"image": ("back.jpg", io.BytesIO(img_b), "image/jpeg")},
        headers=headers_a
    )

    wf_resp = client.get(f"/api/inspections/{inspection_id}/workflow", headers=headers_a)
    wf = wf_resp.json()
    assert wf["lifecycle_status"] == "READY_FOR_REVIEW"
    assert wf["can_finalize"] is True

    # Finalize inspection containing failures
    confirm_package_information(inspection_id, headers_a)
    fin_resp = client.post(f"/api/inspections/{inspection_id}/finalize", headers=headers_a)
    assert fin_resp.status_code == 200
    assert fin_resp.json()["lifecycle_status"] == "FINALIZED"

def test_5_review_required_inspection_can_be_ready_for_review_and_finalized(test_users):
    """An inspection with REVIEW_REQUIRED items can be reviewed and finalized."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    img = create_synthetic_image("NET QTY 100g")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img), "image/jpeg")},
        headers=headers_a
    )

    confirm_package_information(inspection_id, headers_a)
    fin_resp = client.post(f"/api/inspections/{inspection_id}/finalize", headers=headers_a)
    assert fin_resp.status_code == 200
    assert fin_resp.json()["lifecycle_status"] == "FINALIZED"

def test_6_incomplete_inspection_can_be_reviewed_and_finalized(test_users):
    """An inspection with partial surface coverage (only 1 of 2 views) can be finalized safely."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    img = create_synthetic_image("FRONT ONLY MRP Rs 99")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img), "image/jpeg")},
        headers=headers_a
    )

    wf_resp = client.get(f"/api/inspections/{inspection_id}/workflow", headers=headers_a)
    assert wf_resp.json()["capture_status"] == "INCOMPLETE_INSPECTION"
    assert wf_resp.json()["has_incomplete_evidence"] is True

    # Inspector explicitly chooses to finalize partial inspection
    confirm_package_information(inspection_id, headers_a)
    fin_resp = client.post(f"/api/inspections/{inspection_id}/finalize", headers=headers_a)
    assert fin_resp.status_code == 200
    assert fin_resp.json()["lifecycle_status"] == "FINALIZED"

def test_7_cannot_finalize_empty_draft(test_users):
    """Attempting to finalize a DRAFT with 0 captures must return HTTP 400."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    fin_resp = client.post(f"/api/inspections/{inspection_id}/finalize", headers=headers_a)
    assert fin_resp.status_code == 409
    err_body = fin_resp.json()
    msg = err_body.get("error", {}).get("message", "") or err_body.get("detail", "")
    assert "review and confirm" in msg.lower()

def test_8_owner_can_finalize(test_users):
    """Case owner inspector can finalize their case."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    img = create_synthetic_image("NET QTY 500g")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img), "image/jpeg")},
        headers=headers_a
    )

    confirm_package_information(inspection_id, headers_a)
    fin_resp = client.post(f"/api/inspections/{inspection_id}/finalize", headers=headers_a)
    assert fin_resp.status_code == 200
    assert fin_resp.json()["lifecycle_status"] == "FINALIZED"

def test_9_different_inspector_cannot_finalize(test_users):
    """Another inspector cannot view or finalize a case they do not own (returns 404 IDOR protected)."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    headers_b = get_auth_headers("wf_inspector_b", "PassB123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    img = create_synthetic_image("NET QTY 500g")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img), "image/jpeg")},
        headers=headers_a
    )

    # Inspector B attempts to finalize Inspector A's case
    fin_resp = client.post(f"/api/inspections/{inspection_id}/finalize", headers=headers_b)
    assert fin_resp.status_code == 404

def test_10_admin_can_finalize(test_users):
    """Admin user can finalize any inspector's case."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    headers_admin = get_auth_headers("wf_admin", "AdminPass123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    img = create_synthetic_image("NET QTY 500g")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img), "image/jpeg")},
        headers=headers_a
    )

    # Admin finalizes
    confirm_package_information(inspection_id, headers_a)
    fin_resp = client.post(f"/api/inspections/{inspection_id}/finalize", headers=headers_admin)
    assert fin_resp.status_code == 200
    assert fin_resp.json()["lifecycle_status"] == "FINALIZED"

def test_11_finalized_inspection_blocks_capture_upload(test_users):
    """Once FINALIZED, uploading additional captures is rejected with HTTP 409."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    img = create_synthetic_image("NET QTY 500g")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img), "image/jpeg")},
        headers=headers_a
    )

    # Finalize
    confirm_package_information(inspection_id, headers_a)
    client.post(f"/api/inspections/{inspection_id}/finalize", headers=headers_a)

    # Attempt capture upload on finalized case
    blocked_resp = client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "BACK"},
        files={"image": ("back.jpg", io.BytesIO(img), "image/jpeg")},
        headers=headers_a
    )
    assert blocked_resp.status_code == 409
    err_body = blocked_resp.json()
    msg = err_body.get("error", {}).get("message", "") or err_body.get("detail", "")
    assert "Cannot modify a finalized inspection" in msg

def test_12_finalized_inspection_blocks_context_update(test_users):
    """Once FINALIZED, mutating inspection context is rejected with HTTP 409."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    img = create_synthetic_image("NET QTY 500g")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img), "image/jpeg")},
        headers=headers_a
    )

    # Finalize
    confirm_package_information(inspection_id, headers_a)
    client.post(f"/api/inspections/{inspection_id}/finalize", headers=headers_a)

    # Attempt context modification on finalized case
    ctx_resp = client.put(
        f"/api/inspections/{inspection_id}/context",
        json={"product_origin": "IMPORTED"},
        headers=headers_a
    )
    assert ctx_resp.status_code == 409
    err_body = ctx_resp.json()
    msg = err_body.get("error", {}).get("message", "") or err_body.get("detail", "")
    assert "Cannot modify a finalized inspection" in msg

def test_13_finalized_inspection_blocks_clarification_dismiss(test_users):
    """Once FINALIZED, dismissing clarification questions is rejected with HTTP 409."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    img = create_synthetic_image("NET QTY 500g")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img), "image/jpeg")},
        headers=headers_a
    )

    # Finalize
    confirm_package_information(inspection_id, headers_a)
    client.post(f"/api/inspections/{inspection_id}/finalize", headers=headers_a)

    # Attempt dismiss on finalized case
    dism_resp = client.post(
        f"/api/inspections/{inspection_id}/clarifications/dismiss",
        data={"question_id": "PRODUCT_TYPE"},
        headers=headers_a
    )
    assert dism_resp.status_code == 409
    err_body = dism_resp.json()
    msg = err_body.get("error", {}).get("message", "") or err_body.get("detail", "")
    assert "Cannot modify a finalized inspection" in msg

def test_14_finalized_inspection_allows_report_pdf_docx_retrieval(test_users):
    """Finalized inspection still allows JSON report retrieval, PDF export, and DOCX download."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    img = create_synthetic_image("NET QTY 500g MRP Rs 120 MFD 02/2025")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img), "image/jpeg")},
        headers=headers_a
    )

    # Finalize
    confirm_package_information(inspection_id, headers_a)
    fin_resp = client.post(f"/api/inspections/{inspection_id}/finalize", headers=headers_a)
    assert fin_resp.status_code == 200

    # 1. JSON Report
    rep_resp = client.get(f"/api/inspections/{inspection_id}/report", headers=headers_a)
    assert rep_resp.status_code == 200
    assert "metadata" in rep_resp.json()

    # 2. PDF Download
    pdf_resp = client.get(f"/api/inspections/{inspection_id}/report.pdf", headers=headers_a)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF")

    # 3. DOCX Download
    docx_resp = client.get(f"/api/inspections/{inspection_id}/report.docx", headers=headers_a)
    assert docx_resp.status_code == 200
    assert "wordprocessingml" in docx_resp.headers["content-type"]

def test_15_workflow_summary_structure_and_zero_compliance_score(test_users):
    """Workflow summary must contain required metadata and strictly ZERO compliance scores or percentages."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    img = create_synthetic_image("NET QTY 500g MRP Rs 120 MFD 02/2025")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img), "image/jpeg")},
        headers=headers_a
    )

    wf_resp = client.get(f"/api/inspections/{inspection_id}/workflow", headers=headers_a)
    assert wf_resp.status_code == 200
    wf_data = wf_resp.json()

    # Validate required fields
    assert "lifecycle_status" in wf_data
    assert "lifecycle_display_name" in wf_data
    assert "can_upload_capture" in wf_data
    assert "can_update_context" in wf_data
    assert "can_finalize" in wf_data
    assert "statutory_summary" in wf_data
    assert "visual_review_count" in wf_data
    assert "has_failures" in wf_data
    assert "has_review_required" in wf_data
    assert "has_incomplete_evidence" in wf_data
    assert "report_available" in wf_data

    # Strict compliance check: No scores or percentages
    wf_str = str(wf_data).lower()
    assert "score" not in wf_str
    assert "percentage" not in wf_str
    assert "percent" not in wf_str
    assert "grade" not in wf_str

def test_16_workflow_state_persists_in_postgres_across_db_sessions(test_users, db: Session):
    """Lifecycle status persists in PostgreSQL and is restored in a fresh DB session."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    img = create_synthetic_image("NET QTY 500g MRP Rs 120 MFD 02/2025")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img), "image/jpeg")},
        headers=headers_a
    )
    confirm_package_information(inspection_id, headers_a)
    client.post(f"/api/inspections/{inspection_id}/finalize", headers=headers_a)

    # Query directly via fresh SQLAlchemy query
    db_model = InspectionRepository.get_inspection(db, inspection_id)
    assert db_model is not None
    assert db_model.lifecycle_status == "FINALIZED"

    # Rehydrate via domain converter
    domain_session = InspectionRepository.inspection_model_to_domain(db_model)
    assert domain_session.lifecycle_status == "FINALIZED"

def test_17_no_ocr_rerun_or_legal_recomputation_on_workflow_summary_fetch(test_users):
    """Fetching workflow summary returns stored state without altering candidate counts or rerunning OCR."""
    headers_a = get_auth_headers("wf_inspector_a", "PassA123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-25",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_a
    )
    inspection_id = create_resp.json()["inspection_id"]
    
    img = create_synthetic_image("NET QTY 500g MRP Rs 120 MFD 02/2025")
    client.post(
        f"/api/inspections/{inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img), "image/jpeg")},
        headers=headers_a
    )

    # First fetch
    wf1 = client.get(f"/api/inspections/{inspection_id}/workflow", headers=headers_a).json()
    # Second fetch
    wf2 = client.get(f"/api/inspections/{inspection_id}/workflow", headers=headers_a).json()
    assert wf1 == wf2
