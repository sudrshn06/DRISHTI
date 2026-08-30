import io
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import numpy as np
import cv2

from app.main import app
from app.db.session import SessionLocal
from app.core.security import hash_password, create_access_token
from app.repositories.user_repository import UserRepository
from app.repositories.inspection_repository import InspectionRepository
from app.models.inspection import InspectionModel
from app.services.storage_adapter import default_storage_adapter

client = TestClient(app)

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def create_synthetic_image(text="E2E PACK MFD 01/2024 MRP Rs 50") -> bytes:
    img = np.full((400, 600, 3), (240, 240, 240), dtype=np.uint8)
    cv2.putText(img, text, (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    success, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()

@pytest.fixture
def e2e_users(db: Session):
    for uname in ["e2e_inspector_a", "e2e_inspector_b", "e2e_admin"]:
        u = UserRepository.get_by_username(db, uname)
        if u:
            inspections = db.query(InspectionModel).filter(InspectionModel.created_by_user_id == u.user_id).all()
            for insp in inspections:
                db.delete(insp)
            db.delete(u)
    db.commit()

    user_a = UserRepository.create_user(
        db=db,
        username="e2e_inspector_a",
        email="e2e_a@drishti.local",
        password_hash=hash_password("PassA123!"),
        full_name="Inspector Alpha",
        role="INSPECTOR"
    )

    user_b = UserRepository.create_user(
        db=db,
        username="e2e_inspector_b",
        email="e2e_b@drishti.local",
        password_hash=hash_password("PassB123!"),
        full_name="Inspector Beta",
        role="INSPECTOR"
    )

    user_admin = UserRepository.create_user(
        db=db,
        username="e2e_admin",
        email="e2e_admin@drishti.local",
        password_hash=hash_password("AdminPass123!"),
        full_name="Admin User",
        role="ADMIN"
    )

    return {
        "a": user_a,
        "b": user_b,
        "admin": user_admin
    }

def get_auth_token(username: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]

def get_auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

# ==============================================================================
# PHASE 7E: REAL OPERATIONAL E2E VERIFICATION
# ==============================================================================

def test_e2e_full_operational_verification(e2e_users, db: Session):
    """
    Executes the complete operational verification required by Phase 7E:
    1. INSPECTOR A (Login, history listing, filtering, sorting, pagination, DRAFT/REVIEW/FINALIZED resumption, real PDF/DOCX downloads)
    2. INSPECTOR B (Zero visibility into Inspector A cases, search returns 0)
    3. ADMIN (Global scope visibility across Inspector A and B)
    4. PERFORMANCE & BEHAVIOR (Zero OCR, zero legal, zero MinIO on listing; immutability on reopen)
    5. FINALIZED IMMUTABILITY (Mutation guards remain strictly locked)
    """
    token_a = get_auth_token("e2e_inspector_a", "PassA123!")
    headers_a = get_auth_headers(token_a)

    token_b = get_auth_token("e2e_inspector_b", "PassB123!")
    headers_b = get_auth_headers(token_b)

    token_admin = get_auth_token("e2e_admin", "AdminPass123!")
    headers_admin = get_auth_headers(token_admin)

    # -------------------------------------------------------------------------
    # STEP 1: INSPECTOR A SETS UP CASES (DRAFT, READY_FOR_REVIEW, FINALIZED)
    # -------------------------------------------------------------------------
    # Case 1: DRAFT (No captures)
    resp_c1 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "SNACK_CHIPS", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    assert resp_c1.status_code == 200
    id_draft = resp_c1.json()["inspection_id"]
    assert resp_c1.json()["lifecycle_status"] == "DRAFT"

    # Case 2: READY_FOR_REVIEW (1 capture uploaded, analysis completed, not finalized)
    resp_c2 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "BEVERAGE_JUICE", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    assert resp_c2.status_code == 200
    id_review = resp_c2.json()["inspection_id"]

    img_bytes = create_synthetic_image("JUICE MFD 02/2024 MRP Rs 40")
    up_res = client.post(
        f"/api/inspections/{id_review}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers_a
    )
    assert up_res.status_code == 200
    assert up_res.json()["lifecycle_status"] == "READY_FOR_REVIEW"

    # Case 3: FINALIZED (1 capture uploaded, finalized, immutable report generated)
    resp_c3 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "BISCUIT_PACK", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    assert resp_c3.status_code == 200
    id_fin = resp_c3.json()["inspection_id"]

    up_fin_res = client.post(
        f"/api/inspections/{id_fin}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("front.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers_a
    )
    assert up_fin_res.status_code == 200

    review_res = client.post(
        f"/api/inspections/{id_fin}/package-information/review",
        headers=headers_a,
    )
    assert review_res.status_code == 200
    fin_res = client.post(f"/api/inspections/{id_fin}/finalize", headers=headers_a)
    assert fin_res.status_code == 200
    assert fin_res.json()["lifecycle_status"] == "FINALIZED"
    fin_disp = fin_res.json()["report_snapshot"]["overall_disposition"]

    # -------------------------------------------------------------------------
    # 1. INSPECTOR A: VERIFY HISTORY & FILTERS
    # -------------------------------------------------------------------------
    # History page loads successfully and shows all 3 Inspector A cases
    h_res = client.get("/api/inspections", headers=headers_a)
    assert h_res.status_code == 200
    h_data = h_res.json()
    assert h_data["total"] == 3
    a_listed_ids = [i["inspection_id"] for i in h_data["items"]]
    assert id_draft in a_listed_ids
    assert id_review in a_listed_ids
    assert id_fin in a_listed_ids

    # Search by inspection ID
    s_res = client.get(f"/api/inspections?search={id_draft[:8]}", headers=headers_a)
    assert s_res.status_code == 200
    assert len(s_res.json()["items"]) == 1
    assert s_res.json()["items"][0]["inspection_id"] == id_draft

    # Lifecycle filter
    f_draft = client.get("/api/inspections?lifecycle_status=DRAFT", headers=headers_a)
    assert f_draft.status_code == 200
    assert [i["inspection_id"] for i in f_draft.json()["items"]] == [id_draft]

    f_review = client.get("/api/inspections?lifecycle_status=READY_FOR_REVIEW", headers=headers_a)
    assert f_review.status_code == 200
    assert [i["inspection_id"] for i in f_review.json()["items"]] == [id_review]

    f_fin = client.get("/api/inspections?lifecycle_status=FINALIZED", headers=headers_a)
    assert f_fin.status_code == 200
    assert [i["inspection_id"] for i in f_fin.json()["items"]] == [id_fin]

    # Disposition filter
    f_disp = client.get(f"/api/inspections?disposition={fin_disp}", headers=headers_a)
    assert f_disp.status_code == 200
    assert id_fin in [i["inspection_id"] for i in f_disp.json()["items"]]

    # Date filter
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tomorrow_str = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    f_date = client.get(f"/api/inspections?date_from={today_str}&date_to={tomorrow_str}", headers=headers_a)
    assert f_date.status_code == 200
    assert f_date.json()["total"] == 3

    # Sorting newest / oldest
    s_new = client.get("/api/inspections?sort=newest", headers=headers_a)
    assert s_new.status_code == 200
    new_ids = [i["inspection_id"] for i in s_new.json()["items"]]
    assert new_ids[0] == id_fin  # latest created
    assert new_ids[-1] == id_draft  # first created

    s_old = client.get("/api/inspections?sort=oldest", headers=headers_a)
    assert s_old.status_code == 200
    old_ids = [i["inspection_id"] for i in s_old.json()["items"]]
    assert old_ids[0] == id_draft
    assert old_ids[-1] == id_fin

    # Pagination
    p1 = client.get("/api/inspections?page=1&page_size=2", headers=headers_a)
    assert p1.status_code == 200
    assert len(p1.json()["items"]) == 2
    assert p1.json()["total"] == 3
    assert p1.json()["total_pages"] == 2

    # Open DRAFT -> resumes existing session
    open_draft = client.get(f"/api/inspections/{id_draft}", headers=headers_a)
    assert open_draft.status_code == 200
    assert open_draft.json()["lifecycle_status"] == "DRAFT"

    # Open READY_FOR_REVIEW -> opens review
    open_rev = client.get(f"/api/inspections/{id_review}", headers=headers_a)
    assert open_rev.status_code == 200
    assert open_rev.json()["lifecycle_status"] == "READY_FOR_REVIEW"
    assert len(open_rev.json()["captures"]) == 1

    # Open FINALIZED -> read only
    open_fin = client.get(f"/api/inspections/{id_fin}", headers=headers_a)
    assert open_fin.status_code == 200
    assert open_fin.json()["lifecycle_status"] == "FINALIZED"

    # -------------------------------------------------------------------------
    # DOWNLOAD PDF / DOCX WITH AUTHENTICATION VERIFICATION
    # -------------------------------------------------------------------------
    # A) Bearer Header Download
    pdf_resp_hdr = client.get(f"/api/inspections/{id_fin}/report.pdf", headers=headers_a)
    assert pdf_resp_hdr.status_code == 200
    assert pdf_resp_hdr.headers["content-type"] == "application/pdf"
    assert pdf_resp_hdr.content.startswith(b"%PDF-")
    assert len(pdf_resp_hdr.content) > 1000

    docx_resp_hdr = client.get(f"/api/inspections/{id_fin}/report.docx", headers=headers_a)
    assert docx_resp_hdr.status_code == 200
    assert "wordprocessingml" in docx_resp_hdr.headers["content-type"]
    assert docx_resp_hdr.content.startswith(b"PK\x03\x04")
    assert len(docx_resp_hdr.content) > 1000

    # B) URL Query Param (?token=...) MUST NOT authenticate (Query JWT removed for security)
    pdf_resp_tok = client.get(f"/api/inspections/{id_fin}/report.pdf?token={token_a}")
    assert pdf_resp_tok.status_code == 401

    docx_resp_tok = client.get(f"/api/inspections/{id_fin}/report.docx?token={token_a}")
    assert docx_resp_tok.status_code == 401

    # -------------------------------------------------------------------------
    # 2. INSPECTOR B: ZERO VISIBILITY & COMPLETE IDOR ISOLATION
    # -------------------------------------------------------------------------
    # Create 1 inspection for Inspector B
    resp_b1 = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "BETA_TEA", "capture_plan_id": "plan_software_1"},
        headers=headers_b
    )
    assert resp_b1.status_code == 200
    id_b = resp_b1.json()["inspection_id"]

    # Inspector B history shows ONLY id_b (0 of Inspector A's cases)
    h_b = client.get("/api/inspections", headers=headers_b)
    assert h_b.status_code == 200
    b_listed_ids = [i["inspection_id"] for i in h_b.json()["items"]]
    assert b_listed_ids == [id_b]
    assert id_draft not in b_listed_ids
    assert id_review not in b_listed_ids
    assert id_fin not in b_listed_ids

    # Searching Inspector A's ID as Inspector B returns 0
    s_b = client.get(f"/api/inspections?search={id_draft}", headers=headers_b)
    assert s_b.status_code == 200
    assert s_b.json()["total"] == 0
    assert s_b.json()["items"] == []

    # Direct report download attempt by Inspector B on Inspector A's case -> 404
    pdf_b_denied = client.get(f"/api/inspections/{id_fin}/report.pdf", headers=headers_b)
    assert pdf_b_denied.status_code == 404

    # -------------------------------------------------------------------------
    # 3. ADMIN: GLOBAL VISIBILITY
    # -------------------------------------------------------------------------
    h_admin = client.get("/api/inspections?page_size=50", headers=headers_admin)
    assert h_admin.status_code == 200
    admin_listed_ids = [i["inspection_id"] for i in h_admin.json()["items"]]
    assert h_admin.json()["total"] >= 4
    assert id_draft in admin_listed_ids
    assert id_review in admin_listed_ids
    assert id_fin in admin_listed_ids
    assert id_b in admin_listed_ids

    # Admin search across both Inspector A and B
    s_adm_a = client.get(f"/api/inspections?search={id_draft}", headers=headers_admin)
    assert s_adm_a.status_code == 200
    assert len(s_adm_a.json()["items"]) == 1
    assert s_adm_a.json()["items"][0]["created_by_username"] == "e2e_inspector_a"

    s_adm_b = client.get(f"/api/inspections?search={id_b}", headers=headers_admin)
    assert s_adm_b.status_code == 200
    assert len(s_adm_b.json()["items"]) == 1
    assert s_adm_b.json()["items"][0]["created_by_username"] == "e2e_inspector_b"

    # Admin direct report download on Inspector A's case -> 200 valid PDF
    pdf_admin = client.get(f"/api/inspections/{id_fin}/report.pdf", headers=headers_admin)
    assert pdf_admin.status_code == 200
    assert pdf_admin.content.startswith(b"%PDF-")

    # -------------------------------------------------------------------------
    # 4. PERFORMANCE & BEHAVIOR: ZERO OCR, ZERO LEGAL, ZERO MINIO ON LISTING
    # -------------------------------------------------------------------------
    with patch.object(default_storage_adapter, "retrieve", wraps=default_storage_adapter.retrieve) as mock_minio, \
         patch("app.api.routes.inspections.analyze_image") as mock_ocr, \
         patch("app.api.routes.inspections.orchestrate_compliance") as mock_legal:
        
        resp_perf = client.get("/api/inspections", headers=headers_admin)
        assert resp_perf.status_code == 200
        assert mock_minio.call_count == 0
        assert mock_ocr.call_count == 0
        assert mock_legal.call_count == 0

    # -------------------------------------------------------------------------
    # 5. FINALIZED IMMUTABILITY: RESTRICTIONS REMAIN INTACT
    # -------------------------------------------------------------------------
    # Mutation 1: Upload capture on finalized case -> 409 Conflict
    up_mut = client.post(
        f"/api/inspections/{id_fin}/captures",
        data={"view_id": "BACK"},
        files={"image": ("back.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers_a
    )
    assert up_mut.status_code == 409

    # Mutation 2: Context update on finalized case -> 409 Conflict
    ctx_mut = client.put(
        f"/api/inspections/{id_fin}/context",
        json={"product_origin": "IMPORTED"},
        headers=headers_a
    )
    assert ctx_mut.status_code == 409
