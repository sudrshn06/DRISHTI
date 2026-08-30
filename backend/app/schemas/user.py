import re
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator

class UserRole(str, Enum):
    INSPECTOR = "INSPECTOR"
    ADMIN = "ADMIN"

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: str = Field(..., description="User email address")
    full_name: str = Field(..., min_length=1, max_length=100, description="Full name of the user")
    role: UserRole = Field(default=UserRole.INSPECTOR, description="System role: INSPECTOR or ADMIN")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Plaintext password for account creation")

class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: str = Field(..., description="Valid user email address")
    full_name: str = Field(..., min_length=1, max_length=100, description="Full name of the user")
    password: str = Field(..., min_length=8, description="Plaintext password (minimum 8 characters)")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean):
            raise ValueError("Invalid email address format.")
        return clean

class UserResponse(UserBase):
    user_id: str = Field(..., description="Unique UUID of the user")
    is_active: bool = Field(True, description="Whether the user account is active")
    created_at: datetime = Field(..., description="Account creation timestamp")

    model_config = {"from_attributes": True}

class LoginRequest(BaseModel):
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT Bearer access token")
    token_type: str = Field(default="bearer", description="Token type")
    user: UserResponse = Field(..., description="Authenticated user profile")
