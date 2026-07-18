from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func

from core.deps import get_current_user
from core.plans import ensure_owner_access, initial_plan_for_email, normalize_email
from core.security import create_access_token, hash_password, verify_password
from models.database import SessionLocal, User
from schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> TokenResponse:
    email = normalize_email(str(payload.email))
    with SessionLocal() as db:
        existing = db.query(User).filter(func.lower(User.email) == email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado.")
        user = User(
            name=payload.name,
            email=email,
            password_hash=hash_password(payload.password),
            plan=initial_plan_for_email(email),
        )
        ensure_owner_access(user)
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    email = normalize_email(str(payload.email))
    with SessionLocal() as db:
        user = db.query(User).filter(func.lower(User.email) == email).first()
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha incorretos.")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conta inativa.")
        if ensure_owner_access(user):
            db.commit()
            db.refresh(user)
        user_id = user.id
    return TokenResponse(access_token=create_access_token(user_id))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
