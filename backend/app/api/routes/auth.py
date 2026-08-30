import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import UserModel
from app.schemas.user import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    UserCreate,
    UserRegisterRequest
)
from app.repositories.user_repository import UserRepository
from app.core.security import hash_password, verify_password, create_access_token
from app.api.deps import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Public registration endpoint for Legal Metrology Inspectors.
    - Strictly creates accounts with role = INSPECTOR.
    - Enforces unique username and email.
    - Password is automatically hashed with Argon2id.
    """
    # Seed bootstrap admin if DB is empty
    UserRepository.bootstrap_admin_if_empty(db)

    # Check username uniqueness
    if UserRepository.get_by_username(db, user_in.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{user_in.username}' is already taken."
        )

    # Check email uniqueness
    if UserRepository.get_by_email(db, user_in.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{user_in.email}' is already registered."
        )

    p_hash = hash_password(user_in.password)
    user = UserRepository.create_user(
        db=db,
        username=user_in.username,
        email=user_in.email,
        password_hash=p_hash,
        full_name=user_in.full_name,
        role="INSPECTOR"
    )

    return UserResponse.model_validate(user)

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates a user with username/email and password.
    Returns a signed JWT access token.
    """
    # Seed bootstrap admin if DB is empty on first login attempt
    UserRepository.bootstrap_admin_if_empty(db)

    user = UserRepository.get_by_username_or_email(db, request.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Generate JWT token
    token = create_access_token(
        user_id=user.user_id,
        role=user.role,
        username=user.username
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserModel = Depends(get_current_user)):
    """
    Returns the authenticated user's profile.
    """
    return UserResponse.model_validate(current_user)

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    admin: UserModel = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Administrative endpoint to register new Inspectors or Admins.
    Guarded strictly by ADMIN role.
    """
    # Check username uniqueness
    if UserRepository.get_by_username(db, user_in.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user_in.username}' is already taken."
        )

    # Check email uniqueness
    if UserRepository.get_by_email(db, user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{user_in.email}' is already registered."
        )

    p_hash = hash_password(user_in.password)
    user = UserRepository.create_user(
        db=db,
        username=user_in.username,
        email=user_in.email,
        password_hash=p_hash,
        full_name=user_in.full_name,
        role=user_in.role.value if hasattr(user_in.role, "value") else str(user_in.role)
    )

    return UserResponse.model_validate(user)

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    admin: UserModel = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Administrative endpoint to list system users.
    """
    users = UserRepository.list_users(db, skip=skip, limit=limit)
    return [UserResponse.model_validate(u) for u in users]
