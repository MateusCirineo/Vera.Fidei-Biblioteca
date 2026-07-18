from __future__ import annotations

import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    plan: str
    is_active: bool
    billing_provider: str | None = None
    billing_status: str | None = None
    billing_current_period_end: datetime.datetime | None = None
    billing_cancel_at_period_end: bool | None = False

    model_config = {"from_attributes": True}
