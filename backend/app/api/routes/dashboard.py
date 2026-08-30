from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import UserModel
from app.schemas.dashboard import DashboardSummary
from app.repositories.inspection_repository import InspectionRepository

router = APIRouter(prefix="", tags=["dashboard"])

@router.get("/dashboard", response_model=DashboardSummary)
def get_operational_dashboard(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DashboardSummary:
    """
    Returns the single authoritative operational dashboard summary for the authenticated inspector / admin.
    - Scoped strictly by user ownership for INSPECTOR role.
    - Organization-wide metrics for ADMIN role.
    - High-performance scalar aggregate queries with strictly 0 MinIO/OCR overhead.
    """
    return InspectionRepository.get_dashboard_summary(db=db, user=current_user)

