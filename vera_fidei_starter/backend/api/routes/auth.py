from __future__ import annotations

import datetime
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func

from core.deps import get_current_user
from core.email import send_email
from core.plans import ensure_owner_access, initial_plan_for_email, normalize_email
from core.config import settings
from core.security import create_access_token, hash_password, verify_password
from models.database import EmailVerificationToken, PasswordResetToken, SessionLocal, User
from schemas.auth import (
    ContactRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter()


def _send_verification_email(user: User) -> None:
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    with SessionLocal() as db:
        db.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == user.id).delete()
        db.add(EmailVerificationToken(user_id=user.id, token_hash=token_hash))
        db.commit()
    url = f"{settings.site_url}/verificar-email?token={raw}"
    html = f"""
    <div style="font-family:Georgia,serif;max-width:500px;margin:0 auto;padding:24px;color:#333;">
      <div style="text-align:center;padding:20px 0 16px;">
        <img src="{settings.site_url}/branding/Logo-VF-seal.png" alt="Vera.Fidei" width="80" style="display:block;margin:0 auto 10px;" />
        <span style="font-family:Georgia,serif;font-size:22px;color:#8B6914;font-weight:bold;">Vera.Fidei</span>
      </div>
      <hr style="border:none;border-top:1px solid #eee;margin:0 0 20px;">
      <h2 style="color:#8B6914;margin-top:0;">Confirme seu e-mail</h2>
      <p>Olá, {user.name}. Seja bem-vindo à Biblioteca Católica Digital.</p>
      <p>Clique no botão abaixo para confirmar seu endereço de e-mail:</p>
      <p style="margin:20px 0;">
        <a href="{url}" style="background:#8B6914;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;">
          Confirmar e-mail
        </a>
      </p>
      <p style="font-size:12px;color:#999;">Se não criou uma conta no Vera.Fidei, ignore este e-mail.</p>
      <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
      <p style="font-size:11px;color:#bbb;">Vera.Fidei — Biblioteca Católica Digital</p>
    </div>
    """
    send_email(user.email, "Confirme seu e-mail — Vera.Fidei", html)


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
        user_copy = User(id=user.id, name=user.name, email=user.email, email_verified=user.email_verified)
    try:
        _send_verification_email(user_copy)
    except Exception:
        pass
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


# ─── Recuperação de senha ─────────────────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest) -> dict:
    email = normalize_email(str(payload.email))
    with SessionLocal() as db:
        user = db.query(User).filter(func.lower(User.email) == email).first()

    if not user or not user.is_active:
        return {"message": "Se o e-mail estiver cadastrado, você receberá o link em breve."}

    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

    with SessionLocal() as db:
        db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()
        db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
        db.commit()

    url = f"{settings.site_url}/redefinir-senha?token={raw}"
    html = f"""
    <div style="font-family:Georgia,serif;max-width:500px;margin:0 auto;padding:24px;color:#333;">
      <div style="text-align:center;padding:20px 0 16px;">
        <img src="{settings.site_url}/branding/Logo-VF-seal.png" alt="Vera.Fidei" width="80" style="display:block;margin:0 auto 10px;" />
        <span style="font-family:Georgia,serif;font-size:22px;color:#8B6914;font-weight:bold;">Vera.Fidei</span>
      </div>
      <hr style="border:none;border-top:1px solid #eee;margin:0 0 20px;">
      <h2 style="color:#8B6914;margin-top:0;">Redefinir senha</h2>
      <p>Olá, {user.name}.</p>
      <p>Recebemos uma solicitação para redefinir a senha da sua conta Vera.Fidei.</p>
      <p style="margin:20px 0;">
        <a href="{url}" style="background:#8B6914;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;">
          Redefinir minha senha
        </a>
      </p>
      <p style="font-size:12px;color:#999;">Este link é válido por <strong>1 hora</strong>. Se não foi você quem pediu, ignore este e-mail — sua senha permanece a mesma.</p>
      <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
      <p style="font-size:11px;color:#bbb;">Vera.Fidei — Biblioteca Católica Digital</p>
    </div>
    """
    send_email(email, "Redefinição de senha — Vera.Fidei", html)
    return {"message": "Se o e-mail estiver cadastrado, você receberá o link em breve."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest) -> dict:
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    with SessionLocal() as db:
        token = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,  # noqa: E712
            PasswordResetToken.expires_at > datetime.datetime.utcnow(),
        ).first()
        if not token:
            raise HTTPException(status_code=400, detail="Link inválido ou expirado. Solicite um novo link.")
        user = db.get(User, token.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=400, detail="Usuário não encontrado.")
        user.password_hash = hash_password(payload.password)
        token.used = True
        db.commit()
    return {"message": "Senha redefinida com sucesso."}


# ─── Verificação de e-mail ────────────────────────────────────────────────────

@router.post("/verify-email/{token}")
def verify_email(token: str) -> dict:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with SessionLocal() as db:
        vtoken = db.query(EmailVerificationToken).filter(
            EmailVerificationToken.token_hash == token_hash
        ).first()
        if not vtoken:
            raise HTTPException(status_code=400, detail="Link inválido ou já utilizado.")
        user = db.get(User, vtoken.user_id)
        if not user:
            raise HTTPException(status_code=400, detail="Usuário não encontrado.")
        user.email_verified = True
        db.delete(vtoken)
        db.commit()
    return {"message": "E-mail verificado com sucesso."}


@router.post("/resend-verification")
def resend_verification(current_user: User = Depends(get_current_user)) -> dict:
    if current_user.email_verified:
        return {"message": "E-mail já verificado."}
    try:
        _send_verification_email(current_user)
    except Exception:
        pass
    return {"message": "E-mail de verificação reenviado."}


# ─── Formulário de contato ────────────────────────────────────────────────────

@router.post("/contact")
def contact(payload: ContactRequest) -> dict:
    subject = f"[Vera.Fidei] {payload.subject} — {payload.name}"
    html = f"""
    <div style="font-family:Georgia,serif;max-width:600px;margin:0 auto;padding:24px;color:#333;">
      <h2 style="color:#8B6914;">Nova mensagem — Vera.Fidei Suporte</h2>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr><td style="padding:6px 0;color:#666;width:80px;">Nome</td><td style="padding:6px 0;font-weight:bold;">{payload.name}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">E-mail</td><td style="padding:6px 0;"><a href="mailto:{payload.email}">{payload.email}</a></td></tr>
        <tr><td style="padding:6px 0;color:#666;">Assunto</td><td style="padding:6px 0;">{payload.subject}</td></tr>
      </table>
      <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
      <div style="background:#f9f7f2;border-radius:6px;padding:16px;font-size:14px;line-height:1.7;white-space:pre-wrap;">{payload.message}</div>
      <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
      <p style="font-size:11px;color:#bbb;">Mensagem enviada via formulário do Vera.Fidei</p>
    </div>
    """
    send_email(settings.support_email, subject, html)
    return {"message": "Mensagem enviada. Responderemos em breve no e-mail informado."}
