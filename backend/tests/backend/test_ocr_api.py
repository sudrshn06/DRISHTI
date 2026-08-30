import os
import hashlib
from unittest import mock
import numpy as np
import cv2
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.rate_limit import ocr_rate_limiter

from app.api.deps import get_current_user
from app.models.user import UserModel

# Create a test client
client = TestClient(app)

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
    yield
    app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture(autouse=True)
def reset_rate_limit():
    ocr_rate_limiter._history.clear()
    yield

# Helper function to generate an image
def create_dummy_image_bytes(format=".jpg", size=(100, 100), color=(255, 255, 255)):
    img = np.ones((size[0], size[1], 3), dtype=np.uint8)
    img[:] = color
    _, encoded = cv2.imencode(format, img)
    return encoded.tobytes()

def test_01_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "connected"

def test_ocr_api_backward_compatible_no_orchestration():
    """
    12. existing OCR endpoint response remains backward-compatible
    """
    with open("tests/fixtures/real_world/coke_can.jpg", "rb") as f:
        response = client.post(
            "/api/ocr/analyze",
            files={"image": ("coke_can.jpg", f, "image/jpeg")}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["capture_status"] == "INCOMPLETE_INSPECTION"
    assert data.get("rule_evaluations") is None

def test_ocr_api_with_orchestration_inputs():
    """
    13. API rule_evaluations are returned when compliance evaluation inputs are explicitly provided
    14. overall inspection_status remains INCOMPLETE_INSPECTION even when all current individual rules PASS
    """
    with open("tests/fixtures/real_world/coke_can.jpg", "rb") as f:
        response = client.post(
            "/api/ocr/analyze",
            files={"image": ("coke_can.jpg", f, "image/jpeg")},
            data={"reference_date": "2026-08-24", "product_category": "GENERIC_RETAIL_PACKAGE"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["capture_status"] == "INCOMPLETE_INSPECTION"
    assert data.get("rule_evaluations") is not None
    assert isinstance(data["rule_evaluations"], list)
    
    # Check that at least the MRP rule is returned (it might be REVIEW_REQUIRED depending on the image)
    rule_ids = [r["rule_id"] for r in data["rule_evaluations"]]
    assert "MRP_DECLARATION_PRESENCE" in rule_ids

def test_02_valid_jpeg_accepted():
    img_bytes = create_dummy_image_bytes(".jpg")
    res = client.post("/api/ocr/analyze", files={"image": ("test.jpg", img_bytes, "image/jpeg")})
    # Will fail OCR with NO_USABLE_TEXT_DETECTED, but it WAS accepted by the validator
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "NO_USABLE_TEXT_DETECTED"

def test_03_valid_png_accepted():
    img_bytes = create_dummy_image_bytes(".png")
    res = client.post("/api/ocr/analyze", files={"image": ("test.png", img_bytes, "image/png")})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "NO_USABLE_TEXT_DETECTED"

def test_04_unsupported_mime_rejected():
    res = client.post("/api/ocr/analyze", files={"image": ("test.txt", b"dummytext", "text/plain")})
    assert res.status_code == 415
    assert res.json()["error"]["code"] == "INVALID_FILE_TYPE"

def test_05_fake_jpeg_png_bytes_rejected():
    # Sending a file that says it's image/jpeg but lacks magic bytes
    res = client.post("/api/ocr/analyze", files={"image": ("test.jpg", b"not_an_image", "image/jpeg")})
    assert res.status_code == 415
    assert res.json()["error"]["code"] == "INVALID_FILE_TYPE"

def test_06_corrupt_image_rejected():
    # Valid JPEG magic bytes but invalid image content
    corrupt_bytes = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00junkdata'
    res = client.post("/api/ocr/analyze", files={"image": ("corrupt.jpg", corrupt_bytes, "image/jpeg")})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_IMAGE"

def test_07_zero_byte_upload_rejected():
    res = client.post("/api/ocr/analyze", files={"image": ("empty.jpg", b"", "image/jpeg")})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_IMAGE"

@mock.patch("app.core.config.settings.max_upload_size_mb", 0.001) # 1 KB limit
def test_08_size_limit_rejected():
    # Create an image > 1KB
    img_bytes = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01' + b'A' * 2000
    res = client.post("/api/ocr/analyze", files={"image": ("large.jpg", img_bytes, "image/jpeg")})
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "IMAGE_TOO_LARGE"

@mock.patch("app.services.image_validator.cv2.imdecode")
def test_09_max_dimensions_rejected(mock_imdecode):
    # Mock cv2 to return an image that is 5000x5000 = 25MP > 20MP limit
    mock_imdecode.return_value = np.zeros((5000, 5000, 3), dtype=np.uint8)
    # Give valid magic bytes
    valid_bytes = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01'
    res = client.post("/api/ocr/analyze", files={"image": ("large_dim.jpg", valid_bytes, "image/jpeg")})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "IMAGE_DIMENSIONS_TOO_LARGE"

# We must use real PaddleOCR for tests 10-15 and 18-19. We have a readable fixture available at /app/tests/fixtures/readable_test_label.jpg
def get_readable_fixture():
    fixture_path = "/app/tests/fixtures/readable_test_label.jpg"
    if not os.path.exists(fixture_path):
        # Fallback for local run
        pytest.skip("Readable fixture not found")
    with open(fixture_path, "rb") as f:
        return f.read()

def test_10_to_15_18_19_successful_ocr():
    img_bytes = get_readable_fixture()
    res = client.post("/api/ocr/analyze", files={"image": ("test.jpg", img_bytes, "image/jpeg")})
    
    # 22. Public API errors do not use detail wrapper - this is checked by previous tests returning 400/415
    # For success:
    assert res.status_code == 200
    data = res.json()
    
    # 10. SHA-256 matches
    expected_hash = hashlib.sha256(img_bytes).hexdigest()
    assert data["image_sha256"] == expected_hash
    
    # 11, 12. IDs generated
    assert "inspection_id" in data
    assert "image_id" in data
    
    # 13. Evidence ID generated
    assert len(data["evidence"]) > 0
    assert "evidence_id" in data["evidence"][0]
    
    # 14. MRP Candidate
    candidates = data["field_candidates"]
    mrp_cand = next(c for c in candidates if c["field"] == "MRP")
    assert mrp_cand["status"] == "DETECTED"
    assert mrp_cand["normalized_value"]["amount"] == 120.0
    
    # 15. NET_QUANTITY Candidate
    net_cand = next(c for c in candidates if c["field"] == "NET_QUANTITY")
    assert net_cand["status"] == "DETECTED"
    assert net_cand["normalized_value"]["value"] == 500.0
    assert net_cand["normalized_value"]["unit"] == "g"
    
    # 18. Incomplete Inspection
    assert data["capture_status"] == "INCOMPLETE_INSPECTION"
    
    # 19. No PASS/FAIL claims
    response_str = res.text
    assert "PASS" not in response_str
    assert "FAIL" not in response_str
    assert "COMPLIANT" not in response_str
    assert "NON_COMPLIANT" not in response_str

def test_16_blank_image_returns_no_text():
    # Use blank fixture
    fixture_path = "/app/tests/fixtures/blank_image.jpg"
    if not os.path.exists(fixture_path):
        pytest.skip("Blank fixture not found")
    with open(fixture_path, "rb") as f:
        img_bytes = f.read()
    res = client.post("/api/ocr/analyze", files={"image": ("blank.jpg", img_bytes, "image/jpeg")})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "NO_USABLE_TEXT_DETECTED"

@mock.patch("app.services.ocr_engine.get_ocr_model")
def test_17_ocr_exception(mock_get_ocr):
    # Mock OCR engine to raise Exception
    mock_ocr = mock.MagicMock()
    mock_ocr.ocr.side_effect = Exception("Forced OCR crash")
    mock_get_ocr.return_value = mock_ocr
    
    img_bytes = create_dummy_image_bytes()
    res = client.post("/api/ocr/analyze", files={"image": ("test.jpg", img_bytes, "image/jpeg")})
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "OCR_PROCESSING_FAILED"

def test_20_21_rate_limit_and_health():
    # Rate limit is 10/min. Wait, earlier tests consumed some tokens! 
    # To reliably hit it, we just loop until 429.
    img_bytes = create_dummy_image_bytes()
    status_429_seen = False
    for _ in range(20):
        res = client.post("/api/ocr/analyze", files={"image": ("test.jpg", img_bytes, "image/jpeg")})
        if res.status_code == 429:
            status_429_seen = True
            break
            
    assert status_429_seen, "Rate limit was never reached"
    assert res.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    
    # 21. Health endpoint remains usable
    h_res = client.get("/api/health")
    assert h_res.status_code == 200

def test_22_public_api_errors_structure():
    # Send bad data to validation error
    res = client.post("/api/ocr/analyze") # no file
    assert res.status_code == 422
    data = res.json()
    assert "error" in data
    assert "code" in data["error"]
    assert "detail" not in data
