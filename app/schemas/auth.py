from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.base import StrictBaseModel


class UserPreferences(StrictBaseModel):
    topics: list[str] = Field(default_factory=list, max_length=20)
    compactMode: bool = False
    notifications: bool = True


class UserRecord(StrictBaseModel):
    id: str
    name: str
    email: str
    password_hash: str
    created_at: datetime
    updated_at: datetime


class UserPublic(StrictBaseModel):
    id: str
    name: str
    email: str
    created_at: datetime
    updated_at: datetime


class RegisterRequest(StrictBaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(StrictBaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class PasswordUpdateRequest(StrictBaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class AccountDeletionRequest(StrictBaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    confirmation: str = Field(min_length=1, max_length=20)


class AuthResponse(StrictBaseModel):
    token: str
    user: UserPublic


class AuthSessionResponse(StrictBaseModel):
    user: UserPublic
