import logging
from typing import Optional, Callable
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import UserModel
from app.schemas.inspection import InspectionSession
from app.repositories.user_repository import UserRepository
from app.core.security import decode_access_token

logger = logging.getLogger(__name__)

# HTTP Bearer security scheme
http_bearer = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: Session = Depends(get_db)
) -> UserModel:
    """
    FastAPI dependency that extracts and validates the JWT Bearer token
    from the Authorization header, loading the active authenticated UserModel from PostgreSQL.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.warning(f"Unexpected token decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload claims.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user

def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: Session = Depends(get_db)
) -> Optional[UserModel]:
    """
    Optional authentication dependency.
    If Bearer token is provided in the Authorization header, validates and loads the UserModel.
    If no token is provided, returns None.
    If an invalid/expired token is provided, raises HTTP 401.
    """
    if not credentials or not credentials.credentials:
        return None
    return get_current_user(credentials=credentials, db=db)

def require_role(*allowed_roles: str) -> Callable:
    """
    Role-Based Access Control (RBAC) dependency factory.
    """
    def role_checker(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of roles {list(allowed_roles)}."
            )
        return current_user
    return role_checker

require_admin = require_role("ADMIN")
require_inspector_or_admin = require_role("INSPECTOR", "ADMIN")

def get_authorized_inspection(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_current_user_optional)
) -> InspectionSession:
    """
    Dependency that enforces ownership authorization:
    - Unauthenticated callers are rejected with HTTP 401.
    - If inspection has an owner (`created_by_user_id`):
      - ADMIN users can access all inspections.
      - INSPECTOR users can only access inspections they created.
      - If unauthorized inspector, returns HTTP 404 (prevent IDOR).
    - If inspection has no owner (`created_by_user_id is None` - legacy NULL-owner):
      - ADMIN users can access for audit/continuity.
      - INSPECTOR users are denied with IDOR-safe HTTP 404.
    """
    from app.api.routes.inspections import _get_or_load_session

    session = _get_or_load_session(inspection_id, db)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")

    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access this inspection.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if session.created_by_user_id:
        if current_user.role != "ADMIN" and session.created_by_user_id != current_user.user_id:
            logger.warning(
                f"Unauthorized access attempt to inspection {inspection_id} by user {current_user.username} (owner: {session.created_by_user_id})"
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")
    else:
        # Legacy NULL-owner inspection: strictly ADMIN only
        if current_user.role != "ADMIN":
            logger.warning(
                f"Unauthorized access attempt to legacy NULL-owner inspection {inspection_id} by non-admin user {current_user.username}"
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")

    return session
