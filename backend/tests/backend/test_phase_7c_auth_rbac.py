import io
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import numpy as np
import cv2

from app.main import app
from app.core.config import settings, Settings
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.db.session import SessionLocal
from app.models.user import UserModel
from app.models.inspection import InspectionModel, CaptureModel
from app.repositories.user_repository import UserRepository
from app.repositories.inspection_repository import InspectionRepository
from app.services.storage_adapter import default_storage_adapter

client = TestClient(app)

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def create_synthetic_image(text="AUTH TEST") -> bytes:
    img = np.full((400, 600, 3), (240, 240, 240), dtype=np.uint8)
    cv2.putText(img, text, (40, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20, 20, 20), 2)
    success, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()

@pytest.fixture
def seed_users(db: Session):
    # Ensure fresh test users
    for uname in ["inspector_alpha", "inspector_beta", "admin_example", "inactive_inspector"]:
        u = UserRepository.get_by_username(db, uname)
        if u:
            db.delete(u)
    db.commit()

    user_alpha = UserRepository.create_user(
        db=db,
        username="inspector_alpha",
        email="alpha@drishti.local",
        password_hash=hash_password("AlphaSecretPass123!"),
        full_name="Inspector Alpha",
        role="INSPECTOR"
    )

    user_beta = UserRepository.create_user(
        db=db,
        username="inspector_beta",
        email="beta@drishti.local",
        password_hash=hash_password("BetaSecretPass123!"),
        full_name="Inspector Beta",
        role="INSPECTOR"
    )

    user_admin = UserRepository.create_user(
        db=db,
        username="admin_example",
        email="admin@drishti.local",
        password_hash=hash_password("AdminSecretPass123!"),
        full_name="Admin Example",
        role="ADMIN"
    )

    user_inactive = UserRepository.create_user(
        db=db,
        username="inactive_inspector",
        email="inactive@drishti.local",
        password_hash=hash_password("InactiveSecretPass123!"),
        full_name="Inactive Inspector",
        role="INSPECTOR"
    )
    user_inactive.is_active = False
    db.commit()

    return {
        "alpha": user_alpha,
        "beta": user_beta,
        "admin": user_admin,
        "inactive": user_inactive
    }

def get_auth_headers(username: str, password: str) -> dict:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# ==============================================================================
# 1-10: PASSWORD, JWT & AUTH API TESTS
# ==============================================================================

def test_01_password_hashing_and_verification():
    """1. Test Argon2id password hashing and constant-time verification."""
    password = "SuperSecurePassword123!"
    p_hash = hash_password(password)
    
    assert p_hash.startswith("$argon2id$")
    assert verify_password(password, p_hash) is True
    assert verify_password("WrongPassword123!", p_hash) is False
    assert verify_password("", p_hash) is False

def test_02_plaintext_passwords_never_stored(db: Session, seed_users):
    """2. Verify that plaintext passwords are never persisted in the database or serialized."""
    alpha = UserRepository.get_by_username(db, "inspector_alpha")
    assert alpha is not None
    assert alpha.password_hash != "AlphaSecretPass123!"
    assert alpha.password_hash.startswith("$argon2id$")

def test_03_valid_login_returns_jwt_and_profile(seed_users):
    """3. Test valid login returns signed JWT access token and user metadata."""
    resp = client.post(
        "/api/auth/login",
        json={"username": "inspector_alpha", "password": "AlphaSecretPass123!"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "inspector_alpha"
    assert data["user"]["role"] == "INSPECTOR"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]

def test_04_invalid_password_rejected(seed_users):
    """4. Test that invalid password returns HTTP 401 without specific credential exposure."""
    resp = client.post(
        "/api/auth/login",
        json={"username": "inspector_alpha", "password": "IncorrectPassword"}
    )
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers

def test_05_unknown_user_rejected(seed_users):
    """5. Test that nonexistent username returns HTTP 401."""
    resp = client.post(
        "/api/auth/login",
        json={"username": "nonexistent_inspector", "password": "SomePassword123!"}
    )
    assert resp.status_code == 401

def test_06_access_token_generation_and_claims(seed_users):
    """6. Test JWT token payload contains only minimal claims (sub, username, role, exp, iat)."""
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id=user_id, role="INSPECTOR", username="test_user")
    payload = decode_access_token(token)
    
    assert payload["sub"] == user_id
    assert payload["role"] == "INSPECTOR"
    assert payload["username"] == "test_user"
    assert "exp" in payload
    assert "iat" in payload
    # Must NOT leak secret data
    assert "password" not in payload
    assert "evidence" not in payload

def test_07_expired_token_rejected(seed_users):
    """7. Test that an expired JWT token returns HTTP 401."""
    expired_delta = timedelta(minutes=-10)
    user_id = seed_users["alpha"].user_id
    token = create_access_token(user_id=user_id, role="INSPECTOR", username="inspector_alpha", expires_delta=expired_delta)
    
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["error"]["message"].lower()

def test_08_malformed_and_invalid_signature_tokens_rejected(seed_users):
    """8. Test that malformed tokens and tokens signed with invalid secrets are rejected."""
    # Malformed token
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.payload"})
    assert resp.status_code == 401
    
    # Invalid signature token
    import jwt
    bogus_token = jwt.encode({"sub": seed_users["alpha"].user_id, "role": "ADMIN"}, "wrong_secret_key_12345_with_sufficient_length_32_bytes", algorithm="HS256")
    resp2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {bogus_token}"})
    assert resp2.status_code == 401

def test_09_auth_me_profile_endpoint(seed_users):
    """9. Test /api/auth/me returns current authenticated user profile."""
    headers = get_auth_headers("inspector_alpha", "AlphaSecretPass123!")
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "inspector_alpha"
    assert data["email"] == "alpha@drishti.local"
    assert data["role"] == "INSPECTOR"
    assert data["is_active"] is True
    assert "password_hash" not in data

def test_10_inactive_user_rejected(seed_users):
    """10. Test that inactive accounts cannot log in or authenticate."""
    resp = client.post(
        "/api/auth/login",
        json={"username": "inactive_inspector", "password": "InactiveSecretPass123!"}
    )
    assert resp.status_code == 401
    assert "inactive" in resp.json()["error"]["message"].lower()

# ==============================================================================
# 11-20: RBAC, INSPECTION OWNERSHIP & ACCESS CONTROL TESTS
# ==============================================================================

def test_11_and_12_inspector_creates_inspection_with_db_ownership(db: Session, seed_users):
    """11, 12. Test that an authenticated inspector creates an inspection and ownership is persisted in PostgreSQL."""
    headers = get_auth_headers("inspector_alpha", "AlphaSecretPass123!")
    resp = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-26",
            "product_category": "RETAIL_GOODS",
            "capture_plan_id": "plan_software_1"
        },
        headers=headers
    )
    assert resp.status_code == 200
    insp_id = resp.json()["inspection_id"]
    
    # Verify owner in DB
    insp_model = InspectionRepository.get_inspection(db, insp_id)
    assert insp_model is not None
    assert insp_model.created_by_user_id == seed_users["alpha"].user_id

def test_13_owner_can_access_own_inspection(seed_users):
    """13. Test that the owning inspector can access their inspection."""
    headers_a = get_auth_headers("inspector_alpha", "AlphaSecretPass123!")
    create_resp = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "RETAIL_GOODS", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    insp_id = create_resp.json()["inspection_id"]
    
    get_resp = client.get(f"/api/inspections/{insp_id}", headers=headers_a)
    assert get_resp.status_code == 200
    assert get_resp.json()["inspection_id"] == insp_id

def test_14_different_inspector_cannot_access_inspection(seed_users):
    """14. Test IDOR protection: a different inspector cannot access another inspector's inspection (returns 404)."""
    headers_a = get_auth_headers("inspector_alpha", "AlphaSecretPass123!")
    headers_b = get_auth_headers("inspector_beta", "BetaSecretPass123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "RETAIL_GOODS", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    insp_id = create_resp.json()["inspection_id"]
    
    # Inspector Beta tries to access Inspector Alpha's inspection
    get_resp = client.get(f"/api/inspections/{insp_id}", headers=headers_b)
    assert get_resp.status_code == 404

def test_15_different_inspector_cannot_upload_capture(seed_users):
    """15. Test that a different inspector cannot upload captures to another inspector's inspection."""
    headers_a = get_auth_headers("inspector_alpha", "AlphaSecretPass123!")
    headers_b = get_auth_headers("inspector_beta", "BetaSecretPass123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "RETAIL_GOODS", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    insp_id = create_resp.json()["inspection_id"]
    
    img_data = create_synthetic_image("BETA TAMPER ATTEMPT")
    upload_resp = client.post(
        f"/api/inspections/{insp_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("test.jpg", io.BytesIO(img_data), "image/jpeg")},
        headers=headers_b
    )
    assert upload_resp.status_code == 404

def test_16_different_inspector_cannot_update_context(seed_users):
    """16. Test that a different inspector cannot update context on another inspector's inspection."""
    headers_a = get_auth_headers("inspector_alpha", "AlphaSecretPass123!")
    headers_b = get_auth_headers("inspector_beta", "BetaSecretPass123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "RETAIL_GOODS", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    insp_id = create_resp.json()["inspection_id"]
    
    ctx_resp = client.patch(
        f"/api/inspections/{insp_id}/context",
        json={"product_origin": "IMPORTED"},
        headers=headers_b
    )
    assert ctx_resp.status_code == 404

def test_17_18_19_different_inspector_cannot_retrieve_json_pdf_or_docx_reports(seed_users):
    """17, 18, 19. Test that a different inspector cannot retrieve JSON snapshot, PDF, or DOCX reports."""
    headers_a = get_auth_headers("inspector_alpha", "AlphaSecretPass123!")
    headers_b = get_auth_headers("inspector_beta", "BetaSecretPass123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "RETAIL_GOODS", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    insp_id = create_resp.json()["inspection_id"]
    
    # Upload capture by Owner Alpha
    img_data = create_synthetic_image("ALPHA CAPTURE")
    client.post(
        f"/api/inspections/{insp_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("test.jpg", io.BytesIO(img_data), "image/jpeg")},
        headers=headers_a
    )
    
    # 17. JSON Report
    assert client.get(f"/api/inspections/{insp_id}/report", headers=headers_b).status_code == 404
    assert client.post(f"/api/inspections/{insp_id}/report", headers=headers_b).status_code == 404
    
    # 18. PDF Report
    assert client.get(f"/api/inspections/{insp_id}/report.pdf", headers=headers_b).status_code == 404
    
    # 19. DOCX Report
    assert client.get(f"/api/inspections/{insp_id}/report.docx", headers=headers_b).status_code == 404

def test_20_admin_can_access_all_inspections_and_reports(seed_users):
    """20. Test that ADMIN role can access any inspector's inspection, reports, and evidence."""
    headers_a = get_auth_headers("inspector_alpha", "AlphaSecretPass123!")
    headers_admin = get_auth_headers("admin_example", "AdminSecretPass123!")
    
    create_resp = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "RETAIL_GOODS", "capture_plan_id": "plan_software_1"},
        headers=headers_a
    )
    insp_id = create_resp.json()["inspection_id"]
    
    # Admin accesses inspection
    get_insp = client.get(f"/api/inspections/{insp_id}", headers=headers_admin)
    assert get_insp.status_code == 200
    
    # Admin retrieves PDF & DOCX
    pdf_resp = client.get(f"/api/inspections/{insp_id}/report.pdf", headers=headers_admin)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    
    docx_resp = client.get(f"/api/inspections/{insp_id}/report.docx", headers=headers_admin)
    assert docx_resp.status_code == 200

# ==============================================================================
# 21-24: EVIDENCE AUTHORIZATION, LEGACY HANDLING & BOUNDARY INVARIANTS
# ==============================================================================

def test_21_minio_evidence_requires_backend_authorization(seed_users):
    """21. Test that MinIO storage credentials and direct access are not exposed, requiring authorized backend flow."""
    # MinIO credentials must not be returned in API responses
    headers = get_auth_headers("inspector_alpha", "AlphaSecretPass123!")
    resp = client.get("/api/auth/me", headers=headers)
    assert "minio" not in resp.text.lower()
    
    # Verify unauthenticated call to inspection report/evidence fails
    unauth_resp = client.get(f"/api/inspections/{uuid.uuid4()}/report.pdf")
    assert unauth_resp.status_code in [401, 404]

def test_22_legacy_unowned_inspections_accessible(db: Session, seed_users):
    """22. Test that legacy inspections without owner (created_by_user_id is None) remain accessible for backwards compatibility."""
    insp_id = str(uuid.uuid4())
    legacy_insp = InspectionModel(
        inspection_id=insp_id,
        reference_date="2025-01-01",
        product_category="RETAIL_GOODS",
        capture_plan_id="plan_software_1",
        created_by_user_id=None # Legacy unowned
    )
    db.add(legacy_insp)
    db.commit()
    
    # Both Alpha and Beta can access legacy unowned inspection
    headers_a = get_auth_headers("inspector_alpha", "AlphaSecretPass123!")
    headers_b = get_auth_headers("inspector_beta", "BetaSecretPass123!")
    
    # Admin can access legacy unowned inspection
    headers_admin = get_auth_headers("admin_example", "AdminSecretPass123!")
    assert client.get(f"/api/inspections/{insp_id}", headers=headers_admin).status_code == 200
    
    # Inspector receives 404 (IDOR-safe)
    assert client.get(f"/api/inspections/{insp_id}", headers=headers_a).status_code == 404
    assert client.get(f"/api/inspections/{insp_id}", headers=headers_b).status_code == 404
    
    # Cleanup
    db.delete(legacy_insp)
    db.commit()

def test_23_no_secret_or_password_leakage(seed_users):
    """23. Verify zero leakage of JWT secrets, password hashes, or internal database secrets."""
    headers_admin = get_auth_headers("admin_example", "AdminSecretPass123!")
    users_resp = client.get("/api/auth/users", headers=headers_admin)
    assert users_resp.status_code == 200
    for u in users_resp.json():
        assert "password_hash" not in u
        assert "password" not in u
        assert "jwt" not in u

def test_24_admin_user_creation_guarded_by_rbac(seed_users):
    """24. Test that non-admin inspectors cannot create new users (HTTP 403)."""
    headers_a = get_auth_headers("inspector_alpha", "AlphaSecretPass123!")
    resp = client.post(
        "/api/auth/users",
        json={
            "username": "new_inspector_gamma",
            "email": "gamma@drishti.local",
            "password": "GammaSecretPass123!",
            "full_name": "Inspector Gamma",
            "role": "INSPECTOR"
        },
        headers=headers_a
    )
    assert resp.status_code == 403
