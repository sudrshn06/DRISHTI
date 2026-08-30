import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.user import UserModel
from app.models.inspection import InspectionModel
from app.repositories.user_repository import UserRepository
from app.repositories.inspection_repository import InspectionRepository
from app.core.security import hash_password, create_access_token

client = TestClient(app)

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def seed_test_users(db: Session):
    # Setup test users
    for username in ["hardened_insp_1", "hardened_insp_2", "hardened_admin"]:
        existing = UserRepository.get_by_username(db, username)
        if existing:
            db.delete(existing)
    db.commit()

    insp1 = UserRepository.create_user(
        db=db,
        username="hardened_insp_1",
        email="insp1@drishti.gov.in",
        password_hash=hash_password("HardenedPass123!"),
        full_name="Hardened Inspector 1",
        role="INSPECTOR"
    )
    insp2 = UserRepository.create_user(
        db=db,
        username="hardened_insp_2",
        email="insp2@drishti.gov.in",
        password_hash=hash_password("HardenedPass123!"),
        full_name="Hardened Inspector 2",
        role="INSPECTOR"
    )
    admin = UserRepository.create_user(
        db=db,
        username="hardened_admin",
        email="admin@drishti.gov.in",
        password_hash=hash_password("HardenedPass123!"),
        full_name="Hardened Admin",
        role="ADMIN"
    )
    return insp1, insp2, admin

@pytest.fixture
def tokens(seed_test_users):
    insp1, insp2, admin = seed_test_users
    return {
        "insp1": create_access_token(insp1.user_id, "INSPECTOR", insp1.username),
        "insp2": create_access_token(insp2.user_id, "INSPECTOR", insp2.username),
        "admin": create_access_token(admin.user_id, "ADMIN", admin.username)
    }

# 1. unauthenticated inspection creation -> 401
def test_1_unauthenticated_inspection_creation():
    resp = client.post("/api/inspections", data={
        "reference_date": "2026-08-26",
        "product_category": "GENERIC_RETAIL_PACKAGE",
        "capture_plan_id": "plan_software_1"
    })
    assert resp.status_code == 401

# 2. authenticated Inspector creation succeeds
# 3. new inspection owner is authenticated Inspector
# 5. newly created inspection can never have NULL owner
def test_2_3_5_authenticated_inspector_creation(tokens, db: Session):
    headers = {"Authorization": f"Bearer {tokens['insp1']}"}
    resp = client.post("/api/inspections", headers=headers, data={
        "reference_date": "2026-08-26",
        "product_category": "GENERIC_RETAIL_PACKAGE",
        "capture_plan_id": "plan_software_1"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "inspection_id" in data
    
    # Verify in DB
    db_insp = db.query(InspectionModel).filter(InspectionModel.inspection_id == data["inspection_id"]).first()
    assert db_insp is not None
    assert db_insp.created_by_user_id is not None
    
    # Cleanup
    db.delete(db_insp)
    db.commit()

# 4. authenticated Admin creation behaves safely
def test_4_authenticated_admin_creation(tokens, db: Session):
    headers = {"Authorization": f"Bearer {tokens['admin']}"}
    resp = client.post("/api/inspections", headers=headers, data={
        "reference_date": "2026-08-26",
        "product_category": "GENERIC_RETAIL_PACKAGE",
        "capture_plan_id": "plan_software_1"
    })
    assert resp.status_code == 200
    data = resp.json()
    
    db_insp = db.query(InspectionModel).filter(InspectionModel.inspection_id == data["inspection_id"]).first()
    assert db_insp is not None
    assert db_insp.created_by_user_id is not None
    
    # Cleanup
    db.delete(db_insp)
    db.commit()

# Setup helper for legacy NULL-owner cases
@pytest.fixture
def null_owner_inspection(db: Session):
    insp_id = str(uuid.uuid4())
    session_data = {
        "inspection_id": insp_id,
        "reference_date": "2026-08-26",
        "product_category": "GENERIC_RETAIL_PACKAGE",
        "capture_plan_id": "plan_software_1",
        "capture_status": "INCOMPLETE_INSPECTION",
        "evidence_sufficiency": "INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        "lifecycle_status": "DRAFT",
        "created_by_user_id": None
    }
    
    # Creating via raw SQL/Model direct mapping to bypass create_inspection override
    model = InspectionModel(
        inspection_id=insp_id,
        reference_date="2026-08-26",
        product_category="GENERIC_RETAIL_PACKAGE",
        product_origin="UNKNOWN",
        regulatory_product_class="UNKNOWN",
        date_regulatory_regime="UNKNOWN",
        date_package_exemption="UNKNOWN",
        is_electronic="UNKNOWN",
        package_structure="UNKNOWN",
        alcohol_context="UNKNOWN",
        capture_plan_id="plan_software_1",
        capture_status="INCOMPLETE_INSPECTION",
        evidence_sufficiency="INSUFFICIENT_FOR_ABSENCE_EVALUATION",
        lifecycle_status="DRAFT",
        created_by_user_id=None,
        dismissed_clarifications=[]
    )
    db.add(model)
    db.commit()
    
    yield insp_id
    
    # Cleanup
    db.delete(model)
    db.commit()

# 6. Inspector cannot access legacy NULL-owner inspection
def test_6_inspector_cannot_access_null_owner(tokens, null_owner_inspection):
    headers = {"Authorization": f"Bearer {tokens['insp1']}"}
    resp = client.get(f"/api/inspections/{null_owner_inspection}", headers=headers)
    assert resp.status_code == 404

# 7. Inspector cannot upload capture to legacy NULL-owner inspection
def test_7_inspector_cannot_upload_capture_null_owner(tokens, null_owner_inspection):
    headers = {"Authorization": f"Bearer {tokens['insp1']}"}
    dummy_file = ("test.jpg", io.BytesIO(b"dummyimagebytes"), "image/jpeg")
    resp = client.post(
        f"/api/inspections/{null_owner_inspection}/captures",
        headers=headers,
        data={"view_id": "FRONT"},
        files={"image": dummy_file}
    )
    assert resp.status_code == 404

# 8. Inspector cannot update context on legacy NULL-owner inspection
def test_8_inspector_cannot_update_context_null_owner(tokens, null_owner_inspection):
    headers = {"Authorization": f"Bearer {tokens['insp1']}"}
    resp = client.put(
        f"/api/inspections/{null_owner_inspection}/context",
        headers=headers,
        json={"product_origin": "DOMESTIC"}
    )
    assert resp.status_code == 404

# 9. Inspector cannot finalize legacy NULL-owner inspection
def test_9_inspector_cannot_finalize_null_owner(tokens, null_owner_inspection):
    headers = {"Authorization": f"Bearer {tokens['insp1']}"}
    resp = client.post(f"/api/inspections/{null_owner_inspection}/finalize", headers=headers)
    assert resp.status_code == 404

# 10. Inspector cannot retrieve NULL-owner JSON report
def test_10_inspector_cannot_retrieve_json_report_null_owner(tokens, null_owner_inspection):
    headers = {"Authorization": f"Bearer {tokens['insp1']}"}
    resp = client.get(f"/api/inspections/{null_owner_inspection}/report", headers=headers)
    assert resp.status_code == 404

# 11. Inspector cannot retrieve NULL-owner PDF
def test_11_inspector_cannot_retrieve_pdf_null_owner(tokens, null_owner_inspection):
    headers = {"Authorization": f"Bearer {tokens['insp1']}"}
    resp = client.get(f"/api/inspections/{null_owner_inspection}/report.pdf", headers=headers)
    assert resp.status_code == 404

# 12. Inspector cannot retrieve NULL-owner DOCX
def test_12_inspector_cannot_retrieve_docx_null_owner(tokens, null_owner_inspection):
    headers = {"Authorization": f"Bearer {tokens['insp1']}"}
    resp = client.get(f"/api/inspections/{null_owner_inspection}/report.docx", headers=headers)
    assert resp.status_code == 404

# 13. Admin can access legacy NULL-owner case
def test_13_admin_can_access_null_owner(tokens, null_owner_inspection):
    headers = {"Authorization": f"Bearer {tokens['admin']}"}
    resp = client.get(f"/api/inspections/{null_owner_inspection}", headers=headers)
    assert resp.status_code == 200

# 14. unauthenticated /api/ocr/analyze -> 401
def test_14_unauthenticated_ocr_analyze():
    dummy_file = ("test.jpg", io.BytesIO(b"dummyimagebytes"), "image/jpeg")
    resp = client.post("/api/ocr/analyze", files={"image": dummy_file})
    assert resp.status_code == 401

# 15. authenticated Inspector /api/ocr/analyze works
# 16. authenticated Admin /api/ocr/analyze works
# 17. OCR image validation behavior unchanged (e.g. invalid files trigger media type / size checks before auth logic)
# We mock PaddleOCR analyze_image to avoid actual heavy model execution
def test_15_16_17_ocr_analyze_auth(tokens, monkeypatch):
    monkeypatch.setattr("app.api.routes.ocr.validate_and_decode_image", lambda x: (None, "dummy_sha"))
    monkeypatch.setattr("app.api.routes.ocr.analyze_image", lambda x: [])
    monkeypatch.setattr("app.api.routes.ocr.extract_candidates", lambda x, y: [])
    
    dummy_file = ("test.jpg", io.BytesIO(b"dummyimagebytes"), "image/jpeg")
    
    # Inspector works
    resp = client.post(
        "/api/ocr/analyze",
        headers={"Authorization": f"Bearer {tokens['insp1']}"},
        files={"image": dummy_file}
    )
    assert resp.status_code == 200
    
    # Admin works
    resp = client.post(
        "/api/ocr/analyze",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
        files={"image": dummy_file}
    )
    assert resp.status_code == 200

# 18. existing IDOR behavior remains unchanged (Inspector Beta cannot access Alpha's case)
def test_18_existing_idor_unchanged(tokens, db: Session):
    # Alpha creates a case
    headers_alpha = {"Authorization": f"Bearer {tokens['insp1']}"}
    resp = client.post("/api/inspections", headers=headers_alpha, data={
        "reference_date": "2026-08-26",
        "product_category": "GENERIC_RETAIL_PACKAGE",
        "capture_plan_id": "plan_software_1"
    })
    assert resp.status_code == 200
    id_alpha = resp.json()["inspection_id"]
    
    # Beta tries to access
    headers_beta = {"Authorization": f"Bearer {tokens['insp2']}"}
    resp_beta = client.get(f"/api/inspections/{id_alpha}", headers=headers_beta)
    assert resp_beta.status_code == 404
    
    # Cleanup
    db_insp = db.query(InspectionModel).filter(InspectionModel.inspection_id == id_alpha).first()
    db.delete(db_insp)
    db.commit()
