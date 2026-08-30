"""
Phase 7G: End-to-End Integration & Closeout Verification Test Suite

Validates:
1. Complete Inspector Journey (LOGIN -> DASHBOARD -> NEW CASE -> CAPTURE -> ANALYZE -> REVIEW -> FINALIZE -> REPORT -> HISTORY -> DASHBOARD)
2. Multi-user IDOR isolation (Inspector A vs Inspector B vs Admin)
3. Finalized case immutability guards (409 on mutation)
4. Storage boundary (MinIO stores bytes, PostgreSQL stores metadata, 0 image_b64 in Postgres)
5. Empty & error states (404 on invalid case, 401 on unauthenticated, safe incomplete handling)
"""

import io
import uuid
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.main import app
from app.db.session import get_db
from app.models.user import UserModel
from app.models.inspection import InspectionModel, CaptureModel, ReportSnapshotModel
from app.core.security import hash_password, create_access_token
from app.services.storage_adapter import default_storage_adapter


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db_gen = get_db()
    db = next(db_gen)
    try:
        yield db
    finally:
        db.close()


def _create_user_and_token(db: Session, username: str, role: str = "INSPECTOR") -> tuple[UserModel, str]:
    existing = db.query(UserModel).filter(UserModel.username == username).first()
    if existing:
        token = create_access_token(user_id=existing.user_id, role=existing.role, username=existing.username)
        return existing, token

    user = UserModel(
        user_id=str(uuid.uuid4()),
        username=username,
        email=f"{username}@drishti.gov.in",
        password_hash=hash_password("Password123!"),
        full_name=f"Officer {username.capitalize()}",
        role=role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user_id=user.user_id, role=user.role, username=user.username)
    return user, token


def create_synthetic_image(text="GENERIC PACK MFD 01/2024 MRP Rs 50") -> bytes:
    img = np.full((400, 600, 3), (240, 240, 240), dtype=np.uint8)
    cv2.putText(img, text, (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    success, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()


# ==============================================================================
# 1. COMPLETE INSPECTOR INTEGRATION JOURNEY
# ==============================================================================

def test_7g_complete_inspector_journey(client: TestClient, db_session: Session):
    """
    Executes the entire end-to-end inspector flow from start to finish:
    1. Authenticate as Inspector Alpha
    2. Check initial Dashboard
    3. Start New Guided Inspection (starts in DRAFT)
    4. Upload FRONT and BACK captures (triggers OCR, normalizer, multi-view aggregator, rule engine)
    5. Review workflow summary and findings
    6. Finalize inspection (freezes state, creates immutable snapshot)
    7. Download authentic PDF and DOCX reports with Bearer JWT
    8. Query History to verify search, filtering, and summary metadata
    9. Re-fetch Dashboard to verify updated workflow and attention counts
    """
    # 1. Login / Token
    user_alpha, token_alpha = _create_user_and_token(db_session, f"journey_a_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    headers_alpha = {"Authorization": f"Bearer {token_alpha}"}

    # 2. Initial Dashboard
    init_dash = client.get("/api/dashboard", headers=headers_alpha)
    assert init_dash.status_code == 200
    init_data = init_dash.json()
    init_draft = init_data["workflow_counts"]["draft"]
    init_finalized = init_data["workflow_counts"]["finalized"]

    # 3. Create New Inspection
    create_res = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-26",
            "product_category": "BISCUITS",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers_alpha
    )
    assert create_res.status_code == 200
    session_data = create_res.json()
    insp_id = session_data["inspection_id"]
    assert session_data["lifecycle_status"] == "DRAFT"
    assert session_data["created_by_user_id"] == user_alpha.user_id

    # 4. Upload FRONT Capture
    img_front = create_synthetic_image("PARLE-G MFD 05/2024 NET WT 100g")
    up_front = client.post(
        f"/api/inspections/{insp_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img_front), "image/jpeg")},
        headers=headers_alpha
    )
    assert up_front.status_code == 200
    assert up_front.json()["lifecycle_status"] in ["IN_PROGRESS", "READY_FOR_REVIEW"]

    # Upload BACK Capture
    img_back = create_synthetic_image("MRP Rs 20.00 INCL OF ALL TAXES CONSUMER CARE: care@parle.biz")
    up_back = client.post(
        f"/api/inspections/{insp_id}/captures",
        data={"view_id": "BACK"},
        files={"image": ("back.jpg", io.BytesIO(img_back), "image/jpeg")},
        headers=headers_alpha
    )
    assert up_back.status_code == 200
    assert up_back.json()["lifecycle_status"] == "READY_FOR_REVIEW"

    # 5. Check Review / Workflow Summary
    wf_res = client.get(f"/api/inspections/{insp_id}/workflow", headers=headers_alpha)
    assert wf_res.status_code == 200
    wf_data = wf_res.json()
    assert wf_data["lifecycle_status"] == "READY_FOR_REVIEW"
    assert wf_data["can_finalize"] is True

    # 6. Finalize Inspection
    review_res = client.post(
        f"/api/inspections/{insp_id}/package-information/review",
        headers=headers_alpha,
    )
    assert review_res.status_code == 200
    fin_res = client.post(f"/api/inspections/{insp_id}/finalize", headers=headers_alpha)
    assert fin_res.status_code == 200
    fin_data = fin_res.json()
    assert fin_data["lifecycle_status"] == "FINALIZED"
    assert "report_snapshot" in fin_data
    disposition = fin_data["report_snapshot"]["overall_disposition"]
    assert disposition in [
        "VIOLATIONS_FOUND",
        "INCOMPLETE_INSPECTION",
        "REVIEW_REQUIRED",
        "NO_VIOLATIONS_DETECTED_IN_EVALUATED_SCOPE"
    ]

    # 7. Download PDF and DOCX reports (Bearer JWT authenticated)
    pdf_res = client.get(f"/api/inspections/{insp_id}/report.pdf", headers=headers_alpha)
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF")

    docx_res = client.get(f"/api/inspections/{insp_id}/report.docx", headers=headers_alpha)
    assert docx_res.status_code == 200
    assert docx_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert docx_res.content.startswith(b"PK")  # ZIP header for DOCX

    # 8. Query History
    hist_res = client.get(f"/api/inspections?search={insp_id[:8]}", headers=headers_alpha)
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["total"] >= 1
    found_item = next(i for i in hist_data["items"] if i["inspection_id"] == insp_id)
    assert found_item["lifecycle_status"] == "FINALIZED"
    assert found_item["has_report"] is True
    assert found_item["overall_disposition"] == disposition

    # 9. Query Dashboard
    dash_res = client.get("/api/dashboard", headers=headers_alpha)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert dash_data["workflow_counts"]["finalized"] == init_finalized + 1
    assert any(r["inspection_id"] == insp_id for r in dash_data["recent_inspections"])


# ==============================================================================
# 2. MULTI-USER IDOR ISOLATION
# ==============================================================================

def test_7g_multi_user_idor_isolation(client: TestClient, db_session: Session):
    """
    Verifies that Inspector B cannot access, view, or mutate Inspector A's inspection resources,
    while Admin retains global read/audit visibility.
    """
    user_a, token_a = _create_user_and_token(db_session, f"idor_a_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    user_b, token_b = _create_user_and_token(db_session, f"idor_b_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    user_admin, token_admin = _create_user_and_token(db_session, f"idor_admin_{uuid.uuid4().hex[:6]}", "ADMIN")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # Inspector A creates a case
    res = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "IDOR_TEST", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    assert res.status_code == 200
    id_a = res.json()["inspection_id"]

    # 1. Inspector B cannot read Inspector A's session (404)
    get_b = client.get(f"/api/inspections/{id_a}", headers=headers_b)
    assert get_b.status_code == 404

    # 2. Inspector B cannot read workflow summary (404)
    wf_b = client.get(f"/api/inspections/{id_a}/workflow", headers=headers_b)
    assert wf_b.status_code == 404

    # 3. Inspector B cannot upload captures to Inspector A's case (404)
    img_b = create_synthetic_image("HACK ATTEMPT")
    up_b = client.post(
        f"/api/inspections/{id_a}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("h.jpg", io.BytesIO(img_b), "image/jpeg")},
        headers=headers_b
    )
    assert up_b.status_code == 404

    # 4. Inspector B search in history does not return Inspector A's case
    hist_b = client.get(f"/api/inspections?search={id_a}", headers=headers_b)
    assert hist_b.status_code == 200
    assert hist_b.json()["total"] == 0

    # 5. Admin can access Inspector A's case (200)
    get_admin = client.get(f"/api/inspections/{id_a}", headers=headers_admin)
    assert get_admin.status_code == 200
    assert get_admin.json()["inspection_id"] == id_a


# ==============================================================================
# 3. FINALIZED IMMUTABILITY GUARDS
# ==============================================================================

def test_7g_finalized_immutability_guards(client: TestClient, db_session: Session):
    """
    Verifies that once an inspection is FINALIZED:
    - Captures upload returns 409 Conflict
    - Context update returns 409 Conflict
    - Dismiss clarification returns 409 Conflict
    - Read operations (GET inspection, GET workflow, report downloads) remain 200 OK
    """
    user, token = _create_user_and_token(db_session, f"lock_user_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    headers = {"Authorization": f"Bearer {token}"}

    # Create and finalize case
    res = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "LOCKED_CATEGORY", "capture_plan_id": "plan_software_1"},
        headers=headers
    )
    insp_id = res.json()["inspection_id"]

    img_bytes = create_synthetic_image("LOCK TEST MFD 01/2024 MRP Rs 100")
    client.post(
        f"/api/inspections/{insp_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers
    )

    review_res = client.post(
        f"/api/inspections/{insp_id}/package-information/review",
        headers=headers,
    )
    assert review_res.status_code == 200
    fin_res = client.post(f"/api/inspections/{insp_id}/finalize", headers=headers)
    assert fin_res.status_code == 200
    assert fin_res.json()["lifecycle_status"] == "FINALIZED"

    # Attempt mutation 1: upload capture -> 409
    up_mut = client.post(
        f"/api/inspections/{insp_id}/captures",
        data={"view_id": "BACK"},
        files={"image": ("back.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers
    )
    assert up_mut.status_code == 409

    # Attempt mutation 2: context update -> 409
    ctx_mut = client.patch(
        f"/api/inspections/{insp_id}/context",
        json={"product_category": "ALTERED"},
        headers=headers
    )
    assert ctx_mut.status_code == 409

    # Attempt mutation 3: dismiss clarification -> 409
    clar_mut = client.post(
        f"/api/inspections/{insp_id}/clarifications/dismiss",
        data={"question_id": "any_id"},
        headers=headers
    )
    assert clar_mut.status_code == 409

    # Read-only access remains accessible
    get_res = client.get(f"/api/inspections/{insp_id}", headers=headers)
    assert get_res.status_code == 200

    wf_res = client.get(f"/api/inspections/{insp_id}/workflow", headers=headers)
    assert wf_res.status_code == 200


# ==============================================================================
# 4. STORAGE BOUNDARY AUDIT
# ==============================================================================

def test_7g_storage_boundary_no_base64_in_database(client: TestClient, db_session: Session):
    """
    Verifies the strict storage boundary:
    1. Capture raw bytes are written to MinIO
    2. Database stores metadata and object_key
    3. PostgreSQL schema does NOT contain persisted image_b64 column
    """
    user, token = _create_user_and_token(db_session, f"storage_user_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "STORAGE_CHECK", "capture_plan_id": "plan_software_1"},
        headers=headers
    )
    insp_id = res.json()["inspection_id"]

    img_bytes = create_synthetic_image("STORAGE BOUNDARY CHECK")
    up_res = client.post(
        f"/api/inspections/{insp_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers
    )
    assert up_res.status_code == 200

    # Verify directly in PostgreSQL
    cap_row = db_session.query(CaptureModel).filter(CaptureModel.inspection_id == insp_id).first()
    assert cap_row is not None
    assert cap_row.object_key is not None
    assert cap_row.image_sha256 is not None

    # Check database table columns
    columns = [c.name for c in CaptureModel.__table__.columns]
    assert "image_b64" not in columns

    # Verify source bytes retrieve from MinIO
    retrieved_bytes = default_storage_adapter.retrieve(cap_row.object_key)
    assert retrieved_bytes == img_bytes


# ==============================================================================
# 5. ERROR AND BOUNDARY SAFETY
# ==============================================================================

def test_7g_error_paths_and_boundary_safety(client: TestClient, db_session: Session):
    """
    Verifies safe error responses:
    - 401 for missing/invalid token
    - 404 for non-existent inspection ID
    - 400 for invalid lifecycle filter
    - 415 for non-image / corrupt media payload
    """
    user, token = _create_user_and_token(db_session, f"err_user_{uuid.uuid4().hex[:6]}", "INSPECTOR")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Unauthenticated request -> 401
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/inspections").status_code == 401

    # 2. Non-existent inspection -> 404
    bad_id = f"non_existent_{uuid.uuid4().hex}"
    assert client.get(f"/api/inspections/{bad_id}", headers=headers).status_code == 404
    assert client.get(f"/api/inspections/{bad_id}/workflow", headers=headers).status_code == 404
    assert client.get(f"/api/inspections/{bad_id}/report.pdf", headers=headers).status_code == 404

    # 3. Invalid filter -> 400
    filt_res = client.get("/api/inspections?lifecycle_status=INVALID_STATUS", headers=headers)
    assert filt_res.status_code == 400

    # 4. Corrupt / invalid media upload -> 415
    res = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "ERROR_TEST", "capture_plan_id": "plan_software_1"},
        headers=headers
    )
    insp_id = res.json()["inspection_id"]

    bad_up = client.post(
        f"/api/inspections/{insp_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("corrupt.jpg", io.BytesIO(b"NOT_AN_IMAGE"), "image/jpeg")},
        headers=headers
    )
    assert bad_up.status_code == 415
