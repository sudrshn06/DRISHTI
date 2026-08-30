import uuid
import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.user import UserModel
from app.core.config import settings
from app.core.security import hash_password

logger = logging.getLogger(__name__)

class UserRepository:
    """
    Repository layer for PostgreSQL persistence operations on Users.
    """

    @staticmethod
    def create_user(
        db: Session,
        username: str,
        email: str,
        password_hash: str,
        full_name: str,
        role: str = "INSPECTOR"
    ) -> UserModel:
        """Persists a new user record."""
        user = UserModel(
            user_id=str(uuid.uuid4()),
            username=username.strip(),
            email=email.strip().lower(),
            password_hash=password_hash,
            full_name=full_name.strip(),
            role=role.upper(),
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_by_id(db: Session, user_id: str) -> Optional[UserModel]:
        """Looks up a user by UUID."""
        stmt = select(UserModel).where(UserModel.user_id == user_id)
        return db.scalars(stmt).first()

    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[UserModel]:
        """Looks up a user by username."""
        stmt = select(UserModel).where(func.lower(UserModel.username) == username.strip().lower())
        return db.scalars(stmt).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[UserModel]:
        """Looks up a user by email."""
        stmt = select(UserModel).where(func.lower(UserModel.email) == email.strip().lower())
        return db.scalars(stmt).first()

    @staticmethod
    def get_by_username_or_email(db: Session, identifier: str) -> Optional[UserModel]:
        """Looks up a user by either username or email."""
        clean = identifier.strip().lower()
        stmt = select(UserModel).where(
            (func.lower(UserModel.username) == clean) | (func.lower(UserModel.email) == clean)
        )
        return db.scalars(stmt).first()

    @staticmethod
    def list_users(db: Session, skip: int = 0, limit: int = 50) -> List[UserModel]:
        """Lists users with pagination."""
        stmt = select(UserModel).order_by(UserModel.created_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def bootstrap_admin_if_empty(db: Session) -> Optional[UserModel]:
        """
        Safely seeds a bootstrap administrator if users table is empty and
        bootstrap credentials are provided via environment configuration.
        """
        count = db.scalar(select(func.count(UserModel.user_id)))
        if count == 0:
            username = settings.admin_bootstrap_username
            password = settings.admin_bootstrap_password
            email = settings.admin_bootstrap_email or f"{username}@drishti.local"
            if username and password:
                logger.info(f"Bootstrapping initial admin user from environment: {username}")
                p_hash = hash_password(password)
                return UserRepository.create_user(
                    db=db,
                    username=username,
                    email=email,
                    password_hash=p_hash,
                    full_name="System Administrator",
                    role="ADMIN"
                )
        return None
