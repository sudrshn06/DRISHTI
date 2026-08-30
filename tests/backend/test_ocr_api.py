import os
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200

def test_rate_limit():
    # Attempt 11 requests to trigger rate limit (assuming limit is 10/min)
    import time
    for _ in range(10):
        res = client.post("/api/ocr/analyze", files={"image": ("test.txt", b"dummy", "image/jpeg")})
        # Note: Even if it fails validation, it still consumes a rate limit token.
        # Wait, the dependency check happens before the route logic, so it will consume.
        
    res = client.post("/api/ocr/analyze", files={"image": ("test.txt", b"dummy", "image/jpeg")})
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
