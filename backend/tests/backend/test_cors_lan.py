"""Focused regression coverage for credentialed LAN development CORS."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.29.207:3000",
    ],
)
def test_login_preflight_allows_configured_development_origins(origin: str) -> None:
    response = TestClient(app).options(
        "/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"

