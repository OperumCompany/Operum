from datetime import datetime

from pydantic import BaseModel, Field


class UserPreferences(BaseModel):
    topics: list[str] = []
    compactMode: bool = False
    notifications: bool = True


class UserRecord(BaseModel):
    id: str
    name: str
    email: str
    password_hash: str
    created_at: datetime
    updated_at: datetime


class UserPublic(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime
    updated_at: datetime


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2)
    email: str
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)


class PasswordUpdateRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


class AuthResponse(BaseModel):
    token: str
    user: UserPublic
