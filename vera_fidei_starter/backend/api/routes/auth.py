from __future__ import annotations

import datetime
import hashlib
import json
import logging
import re
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import func

from core.deps import get_current_user, require_owner
from core.email import send_email
from core.plans import ensure_owner_access, initial_plan_for_email, is_owner_email, normalize_email
from core.config import settings
from core.security import create_access_token, hash_password, verify_password
from models.database import (
    ApiKey,
    BillingEvent,
    BillingRateLimit,
    BillingRequest,
    BillingSubscription,
    BillingSubscriptionItem,
    EmailVerificationToken,
    Institution,
    InstitutionMember,
    PasswordResetToken,
    SearchUsage,
    SessionLocal,
    User,
    UserFavorite,
    UserReadingProgress,
    VerificationHistory,
)
from services.billing_entitlements import (
    google_subscription_blocks_deletion,
    lock_user_for_billing_mutation,
    recompute_user_plan,
    sanitized_subscriptions_for_export,
)
from services.google_play_billing import (
    GooglePlayAPIError,
    decrypt_purchase_token,
    get_google_play_client,
    parse_verified_subscription,
    persist_verified_purchase,
    product_catalog_by_id,
    validate_google_play_configuration,
)
from schemas.auth import (
    ContactRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MobileWebSessionRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter()
SESSION_COOKIE = "vf_token"
MOBILE_WEB_SESSION_MINUTES = 15
_MOBILE_REDIRECT_RE = re.compile(r"^/visualizar/([1-9][0-9]*)\?page=([1-9][0-9]*)$")
_MOBILE_ACCOUNT_REDIRECTS = frozenset({"/perfil", "/planos"})
logger = logging.getLogger(__name__)
AVATAR_MAX_BYTES = 700 * 1024
_AVATAR_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})

BLOCKING_STRIPE_SUBSCRIPTION_STATUSES = {
    "active",
    "trialing",
    "past_due",
    "unpaid",
    "incomplete",
    "paused",
    "checkout_open",
    "checkout_unresolved",
}


def _avatar_url(user: User) -> str | None:
    updated_at = getattr(user, "avatar_updated_at", None)
    if updated_at is None or not getattr(user, "avatar_content_type", None):
        return None
    # Include microseconds so two photo changes made within the same second do
    # not reuse a browser-cached URL.
    version = int(updated_at.replace(tzinfo=datetime.timezone.utc).timestamp() * 1_000_000)
    return f"/api/auth/avatar?v={version}"


def _validate_avatar_payload(payload: bytes, content_type: str | None) -> str:
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if media_type not in _AVATAR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Use uma imagem JPEG, PNG ou WebP.",
        )
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A imagem está vazia.",
        )
    if len(payload) > AVATAR_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Use uma imagem com até 700 KB.",
        )

    valid_signature = (
        (media_type == "image/jpeg" and payload.startswith(b"\xff\xd8\xff"))
        or (media_type == "image/png" and payload.startswith(b"\x89PNG\r\n\x1a\n"))
        or (
            media_type == "image/webp"
            and len(payload) >= 12
            and payload.startswith(b"RIFF")
            and payload[8:12] == b"WEBP"
        )
    )
    if not valid_signature:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O conteúdo enviado não corresponde ao formato da imagem.",
        )
    return media_type


def _session_cookie_secure() -> bool:
    return settings.vera_environment.strip().lower() in {"production", "prod"}


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=max(60, int(settings.jwt_expire_minutes) * 60),
        path="/",
        secure=_session_cookie_secure(),
        httponly=True,
        samesite="lax",
    )


def _validate_mobile_redirect(value: str) -> str:
    """Accept only the one relative viewer shape understood by the mobile app."""
    match = _MOBILE_REDIRECT_RE.fullmatch(value)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Destino do visualizador inválido.",
        )
    file_id, page = (int(part) for part in match.groups())
    if not (0 < file_id <= 2_147_483_647 and 0 < page <= 1_000_000):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Destino do visualizador inválido.",
        )
    return f"/visualizar/{file_id}?page={page}"


def _validate_mobile_account_redirect(value: str) -> str:
    """Accept only the two authenticated account pages exposed by the app."""
    if value not in _MOBILE_ACCOUNT_REDIRECTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Destino da conta inválido.",
        )
    return value


def _mobile_bearer_user(authorization: str = Header(default="")) -> User:
    """Require an explicit native Bearer token; a browser cookie is insufficient."""
    if not authorization.startswith("Bearer ") or not authorization.removeprefix("Bearer ").strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Bearer ausente ou mal formatado.",
        )
    return get_current_user(authorization=authorization, vf_token=None)


def _mobile_pdf_user(current_user: User = Depends(_mobile_bearer_user)) -> User:
    """Every authenticated account, including Fiel, has full library PDF access."""
    return current_user


def _issue_mobile_web_session(redirect_path: str, current_user: User) -> RedirectResponse:
    token = create_access_token(
        current_user.id,
        int(current_user.session_version or 0),
        expires_minutes=MOBILE_WEB_SESSION_MINUTES,
    )
    response = RedirectResponse(
        url=redirect_path,
        status_code=status.HTTP_303_SEE_OTHER,
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer",
        },
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=MOBILE_WEB_SESSION_MINUTES * 60,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return response


def _mobile_web_session_response(redirect_value: str, current_user: User) -> RedirectResponse:
    return _issue_mobile_web_session(_validate_mobile_redirect(redirect_value), current_user)


def _mobile_account_session_response(redirect_value: str, current_user: User) -> RedirectResponse:
    return _issue_mobile_web_session(_validate_mobile_account_redirect(redirect_value), current_user)


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        secure=_session_cookie_secure(),
        httponly=True,
        samesite="lax",
    )


def _stripe_live_subscription_statuses(
    user: User,
    terminal_failed_checkout_ids: set[str] | frozenset[str] = frozenset(),
) -> set[str]:
    """Read all Stripe subscriptions linked to an account without mutating them."""
    import stripe

    from api.routes.billing import _configure_stripe, _stripe_get, _stripe_id

    _configure_stripe()
    subscriptions: dict[str, object] = {}

    def items_from(page: object):
        auto_paging_iter = getattr(page, "auto_paging_iter", None)
        if callable(auto_paging_iter):
            return auto_paging_iter()
        return iter(_stripe_get(page, "data") or [])

    def remember(subscription: object) -> None:
        subscription_id = _stripe_id(subscription)
        if subscription_id:
            subscriptions[subscription_id] = subscription

    stored_subscription_id = (user.billing_subscription_id or "").strip()
    if stored_subscription_id.startswith("sub_"):
        try:
            remember(stripe.Subscription.retrieve(stored_subscription_id))
        except stripe.error.InvalidRequestError:
            logger.info(
                "stripe_subscription_missing_during_account_deletion user_id=%s subscription_suffix=%s",
                user.id,
                stored_subscription_id[-8:],
            )

    customer_ids: set[str] = set()
    if user.billing_customer_id:
        customer_ids.add(user.billing_customer_id)

    normalized_email = normalize_email(user.email)

    def remember_customer(customer: object) -> None:
        customer_id = _stripe_id(customer)
        if not customer_id:
            return
        metadata = _stripe_get(customer, "metadata") or {}
        metadata_user_id = str(_stripe_get(metadata, "user_id") or "")
        customer_email = normalize_email(str(_stripe_get(customer, "email") or ""))
        if metadata_user_id == str(user.id) or customer_email == normalized_email:
            customer_ids.add(customer_id)

    # Existing accounts may predate email normalization. Query both spellings
    # so a mixed-case legacy email cannot leave a paid Stripe customer behind.
    for lookup_email in {str(user.email).strip(), normalized_email}:
        for customer in items_from(stripe.Customer.list(email=lookup_email, limit=100)):
            remember_customer(customer)

    customer_search = getattr(stripe.Customer, "search", None)
    if callable(customer_search):
        metadata_query = f"metadata['user_id']:'{int(user.id)}'"
        for customer in items_from(customer_search(query=metadata_query, limit=100)):
            remember_customer(customer)

    for customer_id in customer_ids:
        try:
            page = stripe.Subscription.list(customer=customer_id, status="all", limit=100)
        except stripe.error.InvalidRequestError:
            logger.info(
                "stripe_customer_missing_during_account_deletion user_id=%s customer_suffix=%s",
                user.id,
                customer_id[-8:],
            )
            continue
        for subscription in items_from(page):
            remember(subscription)

        for checkout_status in ("open", "complete"):
            try:
                checkout_page = stripe.checkout.Session.list(
                    customer=customer_id,
                    status=checkout_status,
                    limit=100,
                )
            except stripe.error.InvalidRequestError:
                logger.info(
                    "stripe_customer_missing_during_checkout_deletion_check user_id=%s customer_suffix=%s",
                    user.id,
                    customer_id[-8:],
                )
                break
            for checkout in items_from(checkout_page):
                checkout_id = _stripe_id(checkout) or customer_id
                if checkout_status == "open":
                    subscriptions[f"checkout-open:{checkout_id}"] = {
                        "status": "checkout_open"
                    }
                    continue

                payment_status = str(
                    _stripe_get(checkout, "payment_status") or ""
                ).strip().lower()
                subscription_id = _stripe_id(_stripe_get(checkout, "subscription"))
                verified_terminal_failure = bool(
                    checkout_id in terminal_failed_checkout_ids
                    and payment_status == "unpaid"
                )
                if not subscription_id:
                    if verified_terminal_failure:
                        continue
                    subscriptions[f"checkout-unresolved:{checkout_id}"] = {
                        "status": "checkout_unresolved"
                    }
                    continue
                try:
                    remember(stripe.Subscription.retrieve(subscription_id))
                except stripe.error.InvalidRequestError:
                    if not verified_terminal_failure:
                        subscriptions[f"checkout-unresolved:{checkout_id}"] = {
                            "status": "checkout_unresolved"
                        }
                    continue
                if payment_status not in {"paid", "no_payment_required"} and not verified_terminal_failure:
                    subscriptions[f"checkout-unresolved:{checkout_id}"] = {
                        "status": "checkout_unresolved"
                    }

    statuses: set[str] = set()
    for subscription in subscriptions.values():
        status_value = str(_stripe_get(subscription, "status") or "").strip().lower()
        if not status_value:
            raise RuntimeError("Stripe returned a subscription without status")
        statuses.add(status_value)
    return statuses


def _ensure_no_live_stripe_subscription(db, user: User) -> None:
    has_local_stripe_ledger = (
        db.query(BillingSubscription.id)
        .filter(
            BillingSubscription.user_id == user.id,
            BillingSubscription.provider == "stripe",
        )
        .first()
        is not None
    )
    has_stripe_link = bool(
        user.billing_provider == "stripe"
        or user.billing_customer_id
        or (user.billing_subscription_id or "").startswith("sub_")
        or has_local_stripe_ledger
    )
    # A delayed or previously failed webhook can leave a real Stripe customer
    # without local billing ids.  When Stripe is configured, always perform the
    # email/metadata lookup as a final fail-closed check before deleting data.
    # Development installations without Stripe keep the ordinary free-account
    # deletion flow available.
    if not has_stripe_link and not settings.stripe_secret_key.strip():
        return

    try:
        from api.routes.billing import _configure_stripe, _refresh_pending_checkout_intents

        if has_local_stripe_ledger:
            _configure_stripe()
        completed_checkout_found, unresolved_complete_found = _refresh_pending_checkout_intents(
            db,
            user,
        )
        terminal_failed_checkout_ids = {
            str(row.external_subscription_id)
            for row in db.query(BillingSubscription)
            .filter(
                BillingSubscription.user_id == user.id,
                BillingSubscription.provider == "stripe",
                BillingSubscription.provider_status == "checkout_failed",
                BillingSubscription.entitlement_state == "inactive",
                BillingSubscription.external_subscription_id.is_not(None),
            )
            .all()
            if str(row.external_subscription_id).startswith("cs_")
        }
        live_statuses = _stripe_live_subscription_statuses(
            user,
            terminal_failed_checkout_ids,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("stripe_account_deletion_check_failed user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível confirmar o cancelamento da assinatura agora. Tente novamente em instantes.",
        ) from exc

    if (
        unresolved_complete_found
        or (completed_checkout_found and not live_statuses)
        or live_statuses & BLOCKING_STRIPE_SUBSCRIPTION_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cancele a assinatura no portal de cobrança antes de excluir a conta.",
        )


def _ensure_no_live_google_play_subscription(db, user: User) -> list[BillingSubscription]:
    """Revalidate every stored Play token before allowing destructive deletion."""
    subscriptions = (
        db.query(BillingSubscription)
        .filter(
            BillingSubscription.user_id == user.id,
            BillingSubscription.provider == "google_play",
        )
        .order_by(BillingSubscription.id.asc())
        .all()
    )
    if not subscriptions:
        return []

    try:
        if not settings.google_play_enabled:
            raise RuntimeError("google_play_disabled")
        validate_google_play_configuration()
        client = get_google_play_client()
        catalog = product_catalog_by_id(strict=True)
        for subscription in subscriptions:
            if not subscription.purchase_token_ciphertext:
                raise RuntimeError("missing_encrypted_purchase_token")
            purchase_token = decrypt_purchase_token(subscription.purchase_token_ciphertext)
            try:
                provider_payload = client.get_subscription(purchase_token)
            except GooglePlayAPIError as exc:
                if (
                    exc.status_code in {404, 410}
                    and subscription.entitlement_state in {"inactive", "revoked", "replaced"}
                ):
                    continue
                raise
            verified = parse_verified_subscription(provider_payload, catalog)
            persist_verified_purchase(
                db,
                user=user,
                purchase_token=purchase_token,
                verified=verified,
            )
        recompute_user_plan(db, user)
        db.flush()
    except Exception as exc:
        db.rollback()
        logger.exception("google_play_account_deletion_check_failed user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Nao foi possivel confirmar o cancelamento da assinatura no Google Play agora. "
                "Tente novamente em instantes."
            ),
        ) from exc

    refreshed = (
        db.query(BillingSubscription)
        .filter(
            BillingSubscription.user_id == user.id,
            BillingSubscription.provider == "google_play",
        )
        .order_by(BillingSubscription.id.asc())
        .all()
    )
    if any(google_subscription_blocks_deletion(row) for row in refreshed):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cancele a assinatura no Google Play e aguarde a confirmacao "
                "antes de excluir a conta."
            ),
        )
    return refreshed


def _send_verification_email(user: User) -> bool:
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
    sent = send_email(user.email, "Confirme seu e-mail — Vera.Fidei", html)
    if not sent:
        logger.warning("verification_email_not_sent user_id=%s", user.id)
    return sent


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
        token = create_access_token(user.id, int(user.session_version or 0))
        user_copy = User(id=user.id, name=user.name, email=user.email, email_verified=user.email_verified)
    try:
        _send_verification_email(user_copy)
    except Exception:
        logger.exception("verification_email_failed_after_registration user_id=%s", user_copy.id)
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
        session_version = int(user.session_version or 0)
    return TokenResponse(access_token=create_access_token(user_id, session_version))


@router.post("/web-register", status_code=status.HTTP_201_CREATED)
def web_register(payload: RegisterRequest, response: Response) -> dict[str, bool]:
    """Register a browser session without exposing its JWT to JavaScript."""
    token = register(payload).access_token
    _set_session_cookie(response, token)
    return {"authenticated": True}


@router.post("/web-login")
def web_login(payload: LoginRequest, response: Response) -> dict[str, bool]:
    """Authenticate the web app with a Secure, HttpOnly session cookie."""
    token = login(payload).access_token
    _set_session_cookie(response, token)
    return {"authenticated": True}


@router.post(
    "/mobile-web-session",
    response_class=RedirectResponse,
    status_code=status.HTTP_303_SEE_OTHER,
)
def mobile_web_session(
    payload: MobileWebSessionRequest,
    current_user: User = Depends(_mobile_pdf_user),
) -> RedirectResponse:
    """Exchange a native Bearer session for a short-lived, host-only web cookie."""
    return _mobile_web_session_response(payload.redirect, current_user)


@router.get(
    "/mobile-web-session",
    response_class=RedirectResponse,
    status_code=status.HTTP_303_SEE_OTHER,
)
def mobile_web_session_webview(
    redirect: str = Header(alias="X-Vera-Fidei-Redirect", min_length=1, max_length=200),
    current_user: User = Depends(_mobile_pdf_user),
) -> RedirectResponse:
    """Android WebView bridge: GET is required because POST drops custom headers."""
    return _mobile_web_session_response(redirect, current_user)


@router.post(
    "/mobile-account-session",
    response_class=RedirectResponse,
    status_code=status.HTTP_303_SEE_OTHER,
)
def mobile_account_session(
    payload: MobileWebSessionRequest,
    current_user: User = Depends(_mobile_bearer_user),
) -> RedirectResponse:
    """Open one allowlisted account page from the authenticated native app."""
    return _mobile_account_session_response(payload.redirect, current_user)


@router.get(
    "/mobile-account-session",
    response_class=RedirectResponse,
    status_code=status.HTTP_303_SEE_OTHER,
)
def mobile_account_session_webview(
    redirect: str = Header(alias="X-Vera-Fidei-Redirect", min_length=1, max_length=200),
    current_user: User = Depends(_mobile_bearer_user),
) -> RedirectResponse:
    """Android WebView bridge for the two allowlisted account pages."""
    return _mobile_account_session_response(redirect, current_user)


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    _clear_session_cookie(response)
    return {"authenticated": False}


@router.get("/avatar", response_class=Response)
def profile_avatar(current_user: User = Depends(get_current_user)) -> Response:
    with SessionLocal() as db:
        user = db.get(User, current_user.id)
        if user is None or user.avatar_updated_at is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto não encontrada.")
        payload = bytes(user.avatar_data or b"")
        media_type = (user.avatar_content_type or "").strip().lower()
        if not payload or media_type not in _AVATAR_TYPES:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto não encontrada.")

    return Response(
        content=payload,
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Security-Policy": "default-src 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.put("/avatar")
async def update_profile_avatar(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    declared_size = request.headers.get("content-length")
    if declared_size:
        try:
            if int(declared_size) > AVATAR_MAX_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Use uma imagem com até 700 KB.",
                )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tamanho de imagem inválido.",
            ) from exc

    # Do not buffer an unbounded chunked request before enforcing the limit.
    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > AVATAR_MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Use uma imagem com até 700 KB.",
            )
        chunks.append(chunk)
    payload = b"".join(chunks)
    media_type = _validate_avatar_payload(payload, request.headers.get("content-type"))
    with SessionLocal() as db:
        user = db.get(User, current_user.id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada.")
        user.avatar_data = payload
        user.avatar_content_type = media_type
        user.avatar_updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(user)
        avatar_url = _avatar_url(user)

    if avatar_url is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Falha ao salvar a foto.")
    return {"avatar_url": avatar_url}


@router.delete("/avatar")
def delete_profile_avatar(current_user: User = Depends(get_current_user)) -> dict[str, bool]:
    with SessionLocal() as db:
        user = db.get(User, current_user.id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada.")
        user.avatar_data = None
        user.avatar_content_type = None
        user.avatar_updated_at = None
        db.commit()
    return {"removed": True}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user).model_copy(
        update={
            "is_owner": is_owner_email(current_user.email),
            "avatar_url": _avatar_url(current_user),
        }
    )


@router.get("/admin", response_model=UserResponse)
def admin_session(current_user: User = Depends(require_owner)) -> UserResponse:
    return UserResponse.model_validate(current_user).model_copy(
        update={"is_owner": True, "avatar_url": _avatar_url(current_user)}
    )


def _iso(value: datetime.date | datetime.datetime | None) -> str | None:
    if value is None:
        return None
    rendered = value.isoformat()
    if isinstance(value, datetime.datetime) and value.tzinfo is None:
        rendered += "Z"
    return rendered


def _stored_json(value: str | None):
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


@router.get("/data-export")
def export_personal_data(current_user: User = Depends(get_current_user)) -> JSONResponse:
    """Return the signed-in user's portable data without credentials or secrets."""
    with SessionLocal() as db:
        user = db.get(User, current_user.id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada.")

        favorites = db.query(UserFavorite).filter(UserFavorite.user_id == user.id).order_by(UserFavorite.id).all()
        reading_progress = (
            db.query(UserReadingProgress)
            .filter(UserReadingProgress.user_id == user.id)
            .order_by(UserReadingProgress.last_read_at.desc(), UserReadingProgress.id.desc())
            .all()
        )
        history = (
            db.query(VerificationHistory)
            .filter(VerificationHistory.user_id == user.id)
            .order_by(VerificationHistory.id)
            .all()
        )
        usage = db.query(SearchUsage).filter(SearchUsage.user_id == user.id).order_by(SearchUsage.usage_date).all()
        billing = db.query(BillingRequest).filter(BillingRequest.user_id == user.id).order_by(BillingRequest.id).all()
        billing_subscriptions = sanitized_subscriptions_for_export(db, user.id)
        api_keys = db.query(ApiKey).filter(ApiKey.user_id == user.id).order_by(ApiKey.id).all()
        memberships = (
            db.query(InstitutionMember, Institution.name)
            .join(Institution, Institution.id == InstitutionMember.institution_id)
            .filter(InstitutionMember.user_id == user.id)
            .order_by(InstitutionMember.id)
            .all()
        )
        administered = db.query(Institution).filter(Institution.admin_user_id == user.id).order_by(Institution.id).all()

        payload = {
            "exported_at": _iso(datetime.datetime.utcnow()),
            "format": "vera-fidei-personal-data-v1",
            "account": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "email_verified": bool(user.email_verified),
                "plan": user.plan,
                "is_active": bool(user.is_active),
                "created_at": _iso(user.created_at),
                "profile_photo": {
                    "present": user.avatar_updated_at is not None,
                    "content_type": user.avatar_content_type,
                    "updated_at": _iso(user.avatar_updated_at),
                },
                "billing": {
                    "provider": user.billing_provider,
                    "status": user.billing_status,
                    "current_period_end": _iso(user.billing_current_period_end),
                    "cancel_at_period_end": bool(user.billing_cancel_at_period_end),
                },
            },
            "favorites": [
                {
                    "kind": row.kind,
                    "item_id": row.item_id,
                    "title": row.title,
                    "subtitle": row.subtitle,
                    "href": row.href,
                    "source": row.source,
                    "metadata": _stored_json(row.metadata_json),
                    "created_at": _iso(row.created_at),
                    "updated_at": _iso(row.updated_at),
                }
                for row in favorites
            ],
            "reading_progress": [
                {
                    "book_id": row.book_id,
                    "book_file_id": row.book_file_id,
                    "book_title": row.book.title,
                    "book_author": row.book.author,
                    "file_name": row.book_file.original_filename,
                    "current_page": row.current_page,
                    "total_pages": row.total_pages,
                    "completed": bool(row.completed),
                    "revision": row.revision,
                    "first_opened_at": _iso(row.first_opened_at),
                    "last_read_at": _iso(row.last_read_at),
                }
                for row in reading_progress
            ],
            "citation_verifications": [
                {
                    "citation_text": row.citation_text,
                    "attributed_to": row.attributed_to,
                    "status_code": row.status_code,
                    "label": row.label,
                    "confidence": row.confidence,
                    "author": row.author,
                    "work": row.work,
                    "reference": _stored_json(row.reference_json),
                    "matched_excerpt": row.matched_excerpt,
                    "explanation": row.explanation,
                    "response": _stored_json(row.response_json),
                    "created_at": _iso(row.created_at),
                }
                for row in history
            ],
            "search_usage": [
                {"date": _iso(row.usage_date), "count": row.count}
                for row in usage
            ],
            "billing_requests": [
                {
                    "plan": row.plan,
                    "amount_cents": row.amount_cents,
                    "status": row.status,
                    "provider": row.provider,
                    "reference_code": row.reference_code,
                    "created_at": _iso(row.created_at),
                    "updated_at": _iso(row.updated_at),
                }
                for row in billing
            ],
            "billing_subscriptions": billing_subscriptions,
            "api_keys": [
                {
                    "label": row.label,
                    "is_active": bool(row.is_active),
                    "usage_count": row.usage_count,
                    "created_at": _iso(row.created_at),
                    "last_used_at": _iso(row.last_used_at),
                }
                for row in api_keys
            ],
            "institutions": {
                "administered": [{"id": row.id, "name": row.name} for row in administered],
                "memberships": [
                    {
                        "institution_id": member.institution_id,
                        "institution_name": institution_name,
                        "role": member.role,
                        "joined_at": _iso(member.joined_at),
                    }
                    for member, institution_name in memberships
                ],
            },
        }

    stamp = datetime.datetime.utcnow().strftime("%Y%m%d")
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": f'attachment; filename="vera-fidei-dados-{stamp}.json"',
            "Cache-Control": "no-store, max-age=0",
        },
    )


@router.delete("/account")
def delete_account(
    payload: DeleteAccountRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Permanently remove a non-owner account after fresh password confirmation."""
    if payload.confirmation.strip().upper() != "EXCLUIR":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Digite "EXCLUIR" para confirmar.',
        )
    if is_owner_email(current_user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A conta proprietária não pode ser excluída por este fluxo.",
        )

    with SessionLocal() as db:
        user = lock_user_for_billing_mutation(db, current_user.id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada.")
        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Senha incorreta.")

        _ensure_no_live_stripe_subscription(db, user)
        google_subscriptions = _ensure_no_live_google_play_subscription(db, user)

        administered_ids = [
            row.id
            for row in db.query(Institution.id).filter(Institution.admin_user_id == user.id).all()
        ]
        if administered_ids:
            db.query(InstitutionMember).filter(
                InstitutionMember.institution_id.in_(administered_ids)
            ).delete(synchronize_session=False)
            db.query(Institution).filter(Institution.id.in_(administered_ids)).delete(synchronize_session=False)

        db.query(InstitutionMember).filter(InstitutionMember.user_id == user.id).delete(synchronize_session=False)
        db.query(ApiKey).filter(ApiKey.user_id == user.id).delete(synchronize_session=False)
        db.query(BillingRateLimit).filter(BillingRateLimit.user_id == user.id).delete(
            synchronize_session=False
        )
        subscription_ids = [row.id for row in google_subscriptions]
        subscription_ids.extend(
            row.id
            for row in db.query(BillingSubscription.id)
            .filter(BillingSubscription.user_id == user.id)
            .all()
            if row.id not in subscription_ids
        )
        if subscription_ids:
            db.query(BillingSubscriptionItem).filter(
                BillingSubscriptionItem.billing_subscription_id.in_(subscription_ids)
            ).delete(synchronize_session=False)
            db.query(BillingSubscription).filter(
                BillingSubscription.id.in_(subscription_ids)
            ).delete(synchronize_session=False)
        db.query(BillingEvent).filter(BillingEvent.user_id == user.id).update(
            {BillingEvent.user_id: None},
            synchronize_session=False,
        )
        db.query(BillingRequest).filter(BillingRequest.user_id == user.id).delete(synchronize_session=False)
        db.query(SearchUsage).filter(SearchUsage.user_id == user.id).delete(synchronize_session=False)
        db.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == user.id).delete(synchronize_session=False)
        db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete(synchronize_session=False)
        db.query(UserFavorite).filter(UserFavorite.user_id == user.id).delete(synchronize_session=False)
        db.query(UserReadingProgress).filter(UserReadingProgress.user_id == user.id).delete(
            synchronize_session=False
        )
        db.query(VerificationHistory).filter(VerificationHistory.user_id == user.id).delete(synchronize_session=False)
        db.delete(user)
        db.commit()

    _clear_session_cookie(response)
    return {"message": "Conta e dados pessoais excluídos."}


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
    try:
        sent = send_email(email, "Redefinição de senha — Vera.Fidei", html)
        if not sent:
            logger.warning("password_reset_email_not_sent user_id=%s", user.id)
    except Exception:
        # Preserve the generic public response while making delivery failures
        # visible to production monitoring and logs.
        logger.exception("password_reset_email_failed user_id=%s", user.id)
    return {"message": "Se o e-mail estiver cadastrado, você receberá o link em breve."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest) -> dict:
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    with SessionLocal() as db:
        token = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used == False,  # noqa: E712
                PasswordResetToken.expires_at > datetime.datetime.utcnow(),
            )
            .with_for_update()
            .first()
        )
        if not token:
            raise HTTPException(status_code=400, detail="Link inválido ou expirado. Solicite um novo link.")
        user = db.get(User, token.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=400, detail="Usuário não encontrado.")
        user.password_hash = hash_password(payload.password)
        user.session_version = int(user.session_version or 0) + 1
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
        sent = _send_verification_email(current_user)
    except Exception as exc:
        logger.exception("verification_email_resend_failed user_id=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível reenviar o e-mail agora. Tente novamente em instantes.",
        ) from exc
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível reenviar o e-mail agora. Tente novamente em instantes.",
        )
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
    try:
        sent = send_email(settings.support_email, subject, html)
    except Exception as exc:
        logger.exception("contact_email_failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível enviar a mensagem agora. Tente novamente em instantes.",
        ) from exc
    if not sent:
        logger.warning("contact_email_not_sent")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível enviar a mensagem agora. Tente novamente em instantes.",
        )
    return {"message": "Mensagem enviada. Responderemos em breve no e-mail informado."}
