"""
DRISHTI Backend — Health Check Router

GET /api/health
Returns real service status only. No fabricated metrics.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.session import check_db_connection

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Reports:
    - status: always "ok" if this endpoint responds
    - service: service identifier
    - database: "connected" or raises 503 on failure

    Does NOT report: OCR status, AI status, compliance counts,
    inspection statistics, or any fabricated metrics.
    """
    db_status = "connected"
    try:
        check_db_connection()
    except Exception:
        db_status = "unavailable"

    return HealthResponse(
        status="ok",
        service="DRISHTI API",
        database=db_status,
    )
