import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Argon2id password hasher (RFC 9106 recommended defaults)
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32
)

def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using Argon2id.
    Never stores or returns plaintext.
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    return _hasher.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against an Argon2id hash.
    Safe against timing attacks.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception as e:
        logger.warning(f"Unexpected error during password verification: {e}")
        return False

def create_access_token(
    user_id: str,
    role: str,
    username: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Generates a cryptographically signed JWT access token containing only minimal necessary claims.
    Contains no passwords, secret keys, or inspection payloads.
    """
    secret = settings.jwt_secret_key
    if not secret:
        raise ValueError("JWT_SECRET_KEY is not configured in settings/environment.")

    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }

    algorithm = settings.jwt_algorithm or "HS256"
    return jwt.encode(payload, secret, algorithm=algorithm)

def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and verifies a JWT token against the configured secret key.
    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    secret = settings.jwt_secret_key
    if not secret:
        raise ValueError("JWT_SECRET_KEY is not configured in settings/environment.")

    algorithm = settings.jwt_algorithm or "HS256"
    return jwt.decode(token, secret, algorithms=[algorithm])
