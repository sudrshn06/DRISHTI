import pytest
from fastapi.testclient import TestClient
import io
from app.main import app

from app.api.deps import get_current_user
from app.db.session import SessionLocal
from app.models.user import UserModel

client = TestClient(app)

import base64


@pytest.fixture(scope="module", autouse=True)
def persist_mock_user():
    """The authenticated principal must exist when PostgreSQL enforces ownership FKs."""
    with SessionLocal() as db:
        if db.get(UserModel, "test-inspector-uuid-001") is None:
            db.add(UserModel(
                user_id="test-inspector-uuid-001",
                username="test_inspector",
                email="inspector@drishti.local",
                password_hash="hash",
                full_name="Test Inspector",
                role="INSPECTOR",
                is_active=True,
            ))
            db.commit()
    yield

@pytest.fixture(autouse=True)
def override_auth():
    mock_user = UserModel(
        user_id="test-inspector-uuid-001",
        username="test_inspector",
        email="inspector@drishti.local",
        password_hash="hash",
        full_name="Test Inspector",
        role="INSPECTOR",
        is_active=True
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    from app.api.deps import get_current_user_optional
    app.dependency_overrides[get_current_user_optional] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_optional, None)

def get_dummy_image():
    # 1x1 transparent PNG valid base64
    b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    return base64.b64decode(b64)

@pytest.fixture
def dummy_image_file():
    return ("test.png", io.BytesIO(get_dummy_image()), "image/png")

def test_1_create_inspection_successfully():
    response = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-24",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "inspection_id" in data
    assert data["capture_status"] == "INCOMPLETE_INSPECTION"

def test_2_explicit_reference_date_required():
    response = client.post(
        "/api/inspections",
        data={
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        }
    )
    assert response.status_code == 422 # Validation error

def test_3_explicit_product_category_required():
    response = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-24",
            "capture_plan_id": "plan_software_1"
        }
    )
    assert response.status_code == 422

def test_4_invalid_capture_plan_rejected():
    response = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-24",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "invalid_plan_id"
        }
    )
    assert response.status_code == 400

@pytest.fixture
def new_inspection_id():
    response = client.post(
        "/api/inspections",
        data={
            "reference_date": "2026-08-24",
            "product_category": "GENERIC_RETAIL_PACKAGE",
            "capture_plan_id": "plan_software_1"
        }
    )
    return response.json()["inspection_id"]

def test_5_upload_valid_capture_for_valid_view(new_inspection_id, dummy_image_file):
    response = client.post(
        f"/api/inspections/{new_inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": dummy_image_file}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["captures"]) == 1
    assert data["captures"][0]["view_id"] == "FRONT"

def test_6_invalid_view_id_rejected(new_inspection_id, dummy_image_file):
    response = client.post(
        f"/api/inspections/{new_inspection_id}/captures",
        data={"view_id": "UNKNOWN_VIEW"},
        files={"image": dummy_image_file}
    )
    assert response.status_code == 400

def test_7_capture_preserves_identity(new_inspection_id, dummy_image_file):
    response = client.post(
        f"/api/inspections/{new_inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": dummy_image_file}
    )
    data = response.json()
    capture = data["captures"][0]
    assert capture["capture_id"] is not None
    assert capture["image_sha256"] is not None
    assert capture["evidence_id"] is not None

def test_8_9_quality_result_and_retake_preserved(new_inspection_id, dummy_image_file):
    # Dummy image is 1x1, which fails heuristics and results in RETAKE_RECOMMENDED
    response = client.post(
        f"/api/inspections/{new_inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": dummy_image_file}
    )
    data = response.json()
    capture = data["captures"][0]
    assert capture["quality_assessment"] is not None
    assert capture["status"] == "RETAKE_RECOMMENDED"
    # Even if retake is recommended, the capture is preserved
    assert len(data["captures"]) == 1

def test_10_second_capture_does_not_delete_first(new_inspection_id, dummy_image_file):
    client.post(
        f"/api/inspections/{new_inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": dummy_image_file}
    )
    # Upload again for same view
    response = client.post(
        f"/api/inspections/{new_inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": ("test2.png", io.BytesIO(get_dummy_image()), "image/png")}
    )
    data = response.json()
    assert len(data["captures"]) == 2
    assert data["captures"][0]["view_id"] == "FRONT"
    assert data["captures"][1]["view_id"] == "FRONT"
    assert data["captures"][0]["capture_id"] != data["captures"][1]["capture_id"]

def test_11_aggregation_updates(new_inspection_id, dummy_image_file):
    response = client.post(
        f"/api/inspections/{new_inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": dummy_image_file}
    )
    data = response.json()
    # Dummy image yields no OCR text, so fields should be aggregated to NOT_DETECTED or empty
    # For OCR returning empty, the extractor behavior dictates this.
    # At minimum, aggregated_candidates should exist.
    assert "aggregated_candidates" in data

def test_12_13_14_required_progress_and_completion(new_inspection_id, dummy_image_file):
    # 14. Missing required views (BACK is missing)
    response = client.post(
        f"/api/inspections/{new_inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": dummy_image_file}
    )
    data = response.json()
    assert data["capture_status"] == "INCOMPLETE_INSPECTION"

    # 13. Completing all required views (FRONT and BACK)
    response = client.post(
        f"/api/inspections/{new_inspection_id}/captures",
        data={"view_id": "BACK"},
        files={"image": ("test2.png", io.BytesIO(get_dummy_image()), "image/png")}
    )
    data = response.json()
    assert data["capture_status"] == "COMPLETE_EVIDENCE_CAPTURE"

def test_15_get_inspection_reproduces_state(new_inspection_id, dummy_image_file):
    client.post(
        f"/api/inspections/{new_inspection_id}/captures",
        data={"view_id": "FRONT"},
        files={"image": dummy_image_file}
    )
    response = client.get(f"/api/inspections/{new_inspection_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["inspection_id"] == new_inspection_id
    assert len(data["captures"]) == 1
