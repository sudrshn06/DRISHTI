import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal, get_db
from app.models.user import UserModel
from app.repositories.user_repository import UserRepository
from app.core.security import hash_password, verify_password

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


# ==============================================================================
# 1. PUBLIC REGISTRATION & ARGON2ID SECURITY
# ==============================================================================

def test_1_register_inspector_successfully(client: TestClient, db_session: Session):
    """
    Verifies that a new inspector can register via POST /api/auth/register
    and receives a 201 response with valid UserResponse.
    """
    uname = f"reg_insp_{uuid.uuid4().hex[:6]}"
    email = f"{uname}@drishti.gov.in"
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Inspector Rahul Varma",
            "username": uname,
            "email": email,
            "password": "SecurePassword123!"
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == uname
    assert data["email"] == email
    assert data["full_name"] == "Inspector Rahul Varma"
    assert data["role"] == "INSPECTOR"
    assert data["is_active"] is True
    assert "user_id" in data
    assert "password" not in data
    assert "password_hash" not in data


def test_2_password_stored_as_argon2id_hash(client: TestClient, db_session: Session):
    """
    Verifies that the password is cryptographically hashed with Argon2id
    and stored in PostgreSQL users.password_hash.
    """
    uname = f"argon_user_{uuid.uuid4().hex[:6]}"
    email = f"{uname}@drishti.gov.in"
    password = "InspectorSecret123!"
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Officer Priya",
            "username": uname,
            "email": email,
            "password": password
        }
    )
    assert res.status_code == 201

    # Verify directly in PostgreSQL
    user_row = db_session.query(UserModel).filter(UserModel.username == uname).first()
    assert user_row is not None
    assert user_row.password_hash.startswith("$argon2id$")
    assert verify_password(password, user_row.password_hash) is True


def test_3_plaintext_password_never_stored_or_returned(client: TestClient, db_session: Session):
    """
    Verifies that plaintext passwords are never stored in DB columns
    and never exposed in API outputs.
    """
    uname = f"noptext_{uuid.uuid4().hex[:6]}"
    email = f"{uname}@drishti.gov.in"
    password = "SuperSecretPlainText99!"
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Officer Plaintext Guard",
            "username": uname,
            "email": email,
            "password": password
        }
    )
    assert res.status_code == 201
    payload = res.json()
    assert password not in str(payload)

    user_row = db_session.query(UserModel).filter(UserModel.username == uname).first()
    assert user_row.password_hash != password
    assert password not in user_row.password_hash


# ==============================================================================
# 2. ROLE SECURITY & PRIVILEGE ELEVATION GUARDS
# ==============================================================================

def test_4_registration_strictly_creates_inspector_role(client: TestClient, db_session: Session):
    """
    Verifies that public registration always assigns role=INSPECTOR.
    """
    uname = f"role_insp_{uuid.uuid4().hex[:6]}"
    email = f"{uname}@drishti.gov.in"
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Field Inspector A",
            "username": uname,
            "email": email,
            "password": "ValidPassword123!"
        }
    )
    assert res.status_code == 201
    assert res.json()["role"] == "INSPECTOR"

    user_row = db_session.query(UserModel).filter(UserModel.username == uname).first()
    assert user_row.role == "INSPECTOR"


def test_5_client_cannot_register_admin_role(client: TestClient, db_session: Session):
    """
    Verifies that if a client attempts to pass 'role': 'ADMIN' in the registration body,
    the server ignores it and assigns role=INSPECTOR.
    """
    uname = f"spoof_admin_{uuid.uuid4().hex[:6]}"
    email = f"{uname}@drishti.gov.in"
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Attacker Trying Admin",
            "username": uname,
            "email": email,
            "password": "AttackPassword123!",
            "role": "ADMIN"
        }
    )
    assert res.status_code == 201
    assert res.json()["role"] == "INSPECTOR"

    user_row = db_session.query(UserModel).filter(UserModel.username == uname).first()
    assert user_row.role == "INSPECTOR"
    assert user_row.role != "ADMIN"


# ==============================================================================
# 3. DUPLICATES & VALIDATION
# ==============================================================================

def test_6_duplicate_username_rejected_409(client: TestClient, db_session: Session):
    """
    Verifies that registering a pre-existing username returns 409 Conflict.
    """
    uname = f"dup_uname_{uuid.uuid4().hex[:6]}"
    email1 = f"{uname}_1@drishti.gov.in"
    email2 = f"{uname}_2@drishti.gov.in"

    res1 = client.post(
        "/api/auth/register",
        json={
            "full_name": "User One",
            "username": uname,
            "email": email1,
            "password": "Password123!"
        }
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/api/auth/register",
        json={
            "full_name": "User Two",
            "username": uname,
            "email": email2,
            "password": "Password123!"
        }
    )
    assert res2.status_code == 409
    assert "already taken" in res2.json()["detail"].lower()


def test_7_duplicate_email_rejected_409(client: TestClient, db_session: Session):
    """
    Verifies that registering a pre-existing email returns 409 Conflict.
    """
    shared_email = f"shared_{uuid.uuid4().hex[:6]}@drishti.gov.in"
    uname1 = f"user1_{uuid.uuid4().hex[:6]}"
    uname2 = f"user2_{uuid.uuid4().hex[:6]}"

    res1 = client.post(
        "/api/auth/register",
        json={
            "full_name": "User One",
            "username": uname1,
            "email": shared_email,
            "password": "Password123!"
        }
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/api/auth/register",
        json={
            "full_name": "User Two",
            "username": uname2,
            "email": shared_email,
            "password": "Password123!"
        }
    )
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"].lower()


def test_8_invalid_email_format_rejected_422(client: TestClient, db_session: Session):
    """
    Verifies that malformed email addresses are rejected with 422 Unprocessable Entity.
    """
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Bad Email User",
            "username": f"bad_mail_{uuid.uuid4().hex[:6]}",
            "email": "not-an-email-address",
            "password": "Password123!"
        }
    )
    assert res.status_code == 422


def test_9_short_password_rejected_422(client: TestClient, db_session: Session):
    """
    Verifies that passwords under 8 characters are rejected with 422 Unprocessable Entity.
    """
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Short Pass User",
            "username": f"short_pass_{uuid.uuid4().hex[:6]}",
            "email": f"short_{uuid.uuid4().hex[:6]}@drishti.gov.in",
            "password": "short"
        }
    )
    assert res.status_code == 422


# ==============================================================================
# 4. LOGIN & AUTHENTICATION
# ==============================================================================

def test_10_login_after_registration_succeeds(client: TestClient, db_session: Session):
    """
    Verifies that a newly registered user can immediately log in
    and receives a valid JWT access token.
    """
    uname = f"login_test_{uuid.uuid4().hex[:6]}"
    email = f"{uname}@drishti.gov.in"
    password = "LoginSuccessPass123!"

    # 1. Register
    reg_res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Login Tester",
            "username": uname,
            "email": email,
            "password": password
        }
    )
    assert reg_res.status_code == 201

    # 2. Login via username
    login_res = client.post(
        "/api/auth/login",
        json={"username": uname, "password": password}
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["user"]["username"] == uname

    # 3. Login via email
    email_login_res = client.post(
        "/api/auth/login",
        json={"username": email, "password": password}
    )
    assert email_login_res.status_code == 200
    assert "access_token" in email_login_res.json()

    # 4. Access /api/auth/me with JWT
    token = token_data["access_token"]
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == uname


def test_11_wrong_password_returns_401(client: TestClient, db_session: Session):
    """
    Verifies that attempting to log in with an incorrect password returns 401 Unauthorized.
    """
    uname = f"wrong_pass_{uuid.uuid4().hex[:6]}"
    email = f"{uname}@drishti.gov.in"
    password = "CorrectPassword123!"

    client.post(
        "/api/auth/register",
        json={
            "full_name": "Password Guard Tester",
            "username": uname,
            "email": email,
            "password": password
        }
    )

    bad_login = client.post(
        "/api/auth/login",
        json={"username": uname, "password": "WrongPassword999!"}
    )
    assert bad_login.status_code == 401
    assert "invalid username or password" in bad_login.json()["detail"].lower()


def test_12_registered_account_survives_new_db_session(client: TestClient, db_session: Session):
    """
    Verifies that the registered user is persistently stored in PostgreSQL
    and rehydrates across completely fresh database sessions.
    """
    uname = f"persist_user_{uuid.uuid4().hex[:6]}"
    email = f"{uname}@drishti.gov.in"
    password = "DurablePass123!"

    reg_res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Persistent Officer",
            "username": uname,
            "email": email,
            "password": password
        }
    )
    assert reg_res.status_code == 201

    # Open a completely fresh DB session
    fresh_db = SessionLocal()
    try:
        user_in_db = UserRepository.get_by_username(fresh_db, uname)
        assert user_in_db is not None
        assert user_in_db.email == email
        assert user_in_db.role == "INSPECTOR"
        assert verify_password(password, user_in_db.password_hash) is True
    finally:
        fresh_db.close()


# ==============================================================================
# 5. BACKWARDS COMPATIBILITY & RBAC ISOLATION
# ==============================================================================

def test_13_existing_admin_login_still_works(client: TestClient, db_session: Session):
    """
    Verifies that existing or bootstrap admin accounts can log in and access admin endpoints.
    """
    admin_uname = f"admin_{uuid.uuid4().hex[:6]}"
    admin_pass = "AdminPassword123!"
    admin_p_hash = hash_password(admin_pass)
    UserRepository.create_user(
        db=db_session,
        username=admin_uname,
        email=f"{admin_uname}@drishti.gov.in",
        password_hash=admin_p_hash,
        full_name="Administrator",
        role="ADMIN"
    )

    login_res = client.post(
        "/api/auth/login",
        json={"username": admin_uname, "password": admin_pass}
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Admin accesses admin-only user listing
    users_res = client.get("/api/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert users_res.status_code == 200
    assert isinstance(users_res.json(), list)


def test_14_existing_inspector_login_still_works(client: TestClient, db_session: Session):
    """
    Verifies that pre-existing inspector accounts continue functioning seamlessly.
    """
    insp_uname = f"legacy_insp_{uuid.uuid4().hex[:6]}"
    insp_pass = "LegacyPass123!"
    insp_p_hash = hash_password(insp_pass)
    UserRepository.create_user(
        db=db_session,
        username=insp_uname,
        email=f"{insp_uname}@drishti.gov.in",
        password_hash=insp_p_hash,
        full_name="Legacy Inspector",
        role="INSPECTOR"
    )

    login_res = client.post(
        "/api/auth/login",
        json={"username": insp_uname, "password": insp_pass}
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    dash_res = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert dash_res.status_code == 200


def test_15_registered_inspector_cannot_access_other_inspector_case(client: TestClient, db_session: Session):
    """
    Verifies IDOR isolation for a newly registered inspector.
    """
    # 1. Inspector A creates an inspection
    uname_a = f"insp_a_{uuid.uuid4().hex[:6]}"
    client.post("/api/auth/register", json={"full_name": "Inspector A", "username": uname_a, "email": f"{uname_a}@drishti.gov.in", "password": "Password123!"})
    token_a = client.post("/api/auth/login", json={"username": uname_a, "password": "Password123!"}).json()["access_token"]
    
    insp_res = client.post(
        "/api/inspections",
        data={"reference_date": "2026-08-26", "product_category": "BISCUITS", "capture_plan_id": "plan_software_1"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    insp_id = insp_res.json()["inspection_id"]

    # 2. Inspector B registers
    uname_b = f"insp_b_{uuid.uuid4().hex[:6]}"
    client.post("/api/auth/register", json={"full_name": "Inspector B", "username": uname_b, "email": f"{uname_b}@drishti.gov.in", "password": "Password123!"})
    token_b = client.post("/api/auth/login", json={"username": uname_b, "password": "Password123!"}).json()["access_token"]

    # 3. Inspector B attempts to access Inspector A's case -> 404
    idor_res = client.get(f"/api/inspections/{insp_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert idor_res.status_code == 404


def test_16_registered_inspector_cannot_use_admin_user_management(client: TestClient, db_session: Session):
    """
    Verifies that a newly registered inspector receives 403 Forbidden
    when attempting to use administrative user-management endpoints.
    """
    uname = f"field_insp_{uuid.uuid4().hex[:6]}"
    client.post("/api/auth/register", json={"full_name": "Field Inspector", "username": uname, "email": f"{uname}@drishti.gov.in", "password": "Password123!"})
    token = client.post("/api/auth/login", json={"username": uname, "password": "Password123!"}).json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # 1. Attempt to list users -> 403
    list_res = client.get("/api/auth/users", headers=headers)
    assert list_res.status_code == 403

    # 2. Attempt to create user via admin endpoint -> 403
    create_res = client.post(
        "/api/auth/users",
        json={
            "full_name": "Escalated User",
            "username": f"esc_{uuid.uuid4().hex[:6]}",
            "email": f"esc_{uuid.uuid4().hex[:6]}@drishti.gov.in",
            "password": "Password123!",
            "role": "ADMIN"
        },
        headers=headers
    )
    assert create_res.status_code == 403
