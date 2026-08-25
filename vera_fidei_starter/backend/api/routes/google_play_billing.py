from __future__ import annotations

import base64
import dataclasses
import datetime
import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from core.config import settings
from core.deps import get_current_user
from core.plans import is_owner_email
from models.database import BillingEvent, BillingSubscription, BillingSubscriptionItem, SessionLocal, User
from services.billing_entitlements import (
    BillingOwnershipConflict,
    BillingRateLimitExceeded,
    consume_billing_rate_limit,
    effective_billing_status,
    has_recoverable_provider_subscription,
    lock_user_for_billing_mutation,
    recompute_user_plan,
)
from services.google_play_billing import (
    GooglePlayAPIError,
    GooglePlayConfigurationError,
    GooglePlayProduct,
    VerifiedGooglePlaySubscription,
    account_id_matches,
    get_google_play_client,
    load_product_catalog,
    obfuscated_account_id,
    parse_rfc3339,
    parse_verified_subscription,
    persist_verified_purchase,
    product_catalog_by_id,
    purchase_token_fingerprint,
    validate_google_play_configuration,
)


router = APIRouter()
MAX_PURCHASES_PER_REQUEST = 10
MAX_PUBSUB_BODY_BYTES = 64 * 1024


class GooglePlayPurchaseInput(BaseModel):
    purchase_token: str = Field(min_length=10, max_length=4096)
    product_id: str | None = Field(default=None, min_length=1, max_length=255)


class GooglePlayPurchaseBatch(BaseModel):
    purchases: list[GooglePlayPurchaseInput] = Field(
        min_length=1,
        max_length=MAX_PURCHASES_PER_REQUEST,
    )


class GooglePlayCatalogProductResponse(BaseModel):
    product_id: str
    plan: str
    base_plan_id: str | None = None


class GooglePlayCatalogResponse(BaseModel):
    enabled: bool
    package_name: str
    obfuscated_account_id: str | None
    products: list[GooglePlayCatalogProductResponse]


class GooglePlayPurchaseResult(BaseModel):
    index: int
    accepted: bool
    entitlement_granted: bool
    finish_transaction: bool
    state: str
    message: str | None = None


class GooglePlaySyncResponse(BaseModel):
    synced: bool
    plan: str
    billing_status: str | None
    active_product_id: str | None
    results: list[GooglePlayPurchaseResult]


class GooglePlayRestoreResponse(BaseModel):
    restored: bool
    plan: str
    billing_status: str | None
    active_product_id: str | None
    results: list[GooglePlayPurchaseResult]


class BillingStatusResponse(BaseModel):
    plan: str
    billing_provider: str | None
    billing_status: str | None
    active_product_id: str | None
    current_period_end: datetime.datetime | None


def _native_bearer_user(authorization: str = Header(default="")) -> User:
    if not authorization.startswith("Bearer ") or not authorization.removeprefix("Bearer ").strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Bearer ausente ou mal formatado.",
        )
    return get_current_user(authorization=authorization, vf_token=None)


def _require_enabled() -> None:
    if not settings.google_play_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Play Billing ainda nao esta habilitado.",
        )
    try:
        validate_google_play_configuration()
    except GooglePlayConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Play Billing ainda nao esta configurado.",
        ) from exc


def _catalog_response(products: list[GooglePlayProduct]) -> list[GooglePlayCatalogProductResponse]:
    return [
        GooglePlayCatalogProductResponse(
            product_id=product.product_id,
            plan=product.plan,
            base_plan_id=product.base_plan_id,
        )
        for product in products
    ]


def _mark_private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, max-age=0"


@router.get("/billing/google-play/catalog", response_model=GooglePlayCatalogResponse)
def google_play_catalog(
    response: Response,
    current_user: User = Depends(_native_bearer_user),
) -> GooglePlayCatalogResponse:
    _mark_private_response(response)
    if is_owner_email(current_user.email):
        return GooglePlayCatalogResponse(
            enabled=False,
            package_name=settings.google_play_package_name.strip(),
            obfuscated_account_id=None,
            products=[],
        )
    if not settings.google_play_enabled:
        return GooglePlayCatalogResponse(
            enabled=False,
            package_name=settings.google_play_package_name.strip(),
            obfuscated_account_id=None,
            products=[],
        )
    _require_enabled()
    products = load_product_catalog(strict=True)
    account_id = obfuscated_account_id(current_user.id)
    with SessionLocal() as db:
        user = lock_user_for_billing_mutation(db, current_user.id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Conta invalida.")
        if user.google_play_account_id and not account_id_matches(
            account_id,
            user.google_play_account_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Identidade de faturamento inconsistente.",
            )
        user.google_play_account_id = account_id
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Identidade de faturamento ja vinculada.",
            ) from exc
    return GooglePlayCatalogResponse(
        enabled=True,
        package_name=settings.google_play_package_name.strip(),
        obfuscated_account_id=account_id,
        products=_catalog_response(products),
    )


@router.get("/billing/status", response_model=BillingStatusResponse)
def billing_status(
    response: Response,
    current_user: User = Depends(_native_bearer_user),
) -> BillingStatusResponse:
    _mark_private_response(response)
    with SessionLocal() as db:
        user = lock_user_for_billing_mutation(db, current_user.id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Conta invalida.")
        resolved = recompute_user_plan(db, user)
        db.commit()
        return BillingStatusResponse(
            plan=resolved.plan,
            billing_provider=resolved.provider,
            billing_status=resolved.billing_status,
            active_product_id=resolved.active_product_id,
            current_period_end=resolved.current_period_end,
        )


def _verified_product_ids(verified: VerifiedGooglePlaySubscription) -> set[str]:
    return {item.product_id for item in verified.items}


def _process_purchase(
    db,
    *,
    user: User,
    purchase: GooglePlayPurchaseInput,
    client,
) -> tuple[GooglePlayPurchaseResult, User]:
    payload = client.get_subscription(purchase.purchase_token)
    catalog = product_catalog_by_id(strict=True)
    verified = parse_verified_subscription(payload, catalog)
    if purchase.product_id and purchase.product_id not in _verified_product_ids(verified):
        return (
            GooglePlayPurchaseResult(
                index=0,
                accepted=False,
                entitlement_granted=False,
                finish_transaction=False,
                state="product_mismatch",
                message="O produto informado nao corresponde a compra validada.",
            ),
            user,
        )

    subscription = persist_verified_purchase(
        db,
        user=user,
        purchase_token=purchase.purchase_token,
        verified=verified,
    )
    recompute_user_plan(db, user)
    db.flush()

    finish_transaction = not verified.requires_acknowledgement
    message: str | None = None
    if verified.entitlement_granted and verified.requires_acknowledgement:
        try:
            client.acknowledge_subscription(
                purchase.purchase_token,
                verified.items[0].product_id,
            )
        except GooglePlayAPIError:
            message = "A compra foi validada, mas a confirmacao sera repetida automaticamente."
        else:
            subscription = db.get(BillingSubscription, subscription.id)
            if subscription is not None:
                subscription.acknowledgement_state = "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"
                subscription.updated_at = datetime.datetime.utcnow()
                db.flush()
            finish_transaction = True

    return (
        GooglePlayPurchaseResult(
            index=0,
            accepted=True,
            entitlement_granted=verified.entitlement_granted,
            finish_transaction=finish_transaction,
            state=verified.entitlement_state,
            message=message,
        ),
        user,
    )


def _sync_batch(
    payload: GooglePlayPurchaseBatch,
    current_user: User,
) -> tuple[list[GooglePlayPurchaseResult], str, str | None, str | None]:
    if is_owner_email(current_user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A conta proprietaria ja possui acesso integral e nao pode comprar no Google Play.",
        )
    _require_enabled()
    try:
        client = get_google_play_client()
    except GooglePlayConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Play Billing temporariamente indisponivel.",
        ) from exc

    results: list[GooglePlayPurchaseResult] = []
    seen_hashes: set[str] = set()
    with SessionLocal() as db:
        user = lock_user_for_billing_mutation(db, current_user.id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Conta invalida.")
        try:
            consume_billing_rate_limit(
                db,
                user_id=user.id,
                scope="google_play_sync_restore",
                limit=int(settings.google_play_sync_rate_limit),
                window_seconds=int(settings.google_play_sync_rate_window_seconds),
                cost=len(payload.purchases),
            )
        except BillingRateLimitExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas sincronizacoes de compra. Tente novamente em instantes.",
                headers={"Retry-After": str(exc.retry_after_seconds)},
            ) from exc
        for index, purchase in enumerate(payload.purchases):
            fingerprint = purchase_token_fingerprint(purchase.purchase_token)
            if fingerprint in seen_hashes:
                results.append(
                    GooglePlayPurchaseResult(
                        index=index,
                        accepted=False,
                        entitlement_granted=False,
                        finish_transaction=False,
                        state="duplicate_input",
                        message="A mesma compra foi enviada mais de uma vez.",
                    )
                )
                continue
            seen_hashes.add(fingerprint)
            existing_google_purchase = (
                db.query(BillingSubscription.id)
                .filter(
                    BillingSubscription.provider == "google_play",
                    BillingSubscription.package_name == settings.google_play_package_name.strip(),
                    BillingSubscription.purchase_token_hash == fingerprint,
                    BillingSubscription.user_id == user.id,
                )
                .first()
            )
            if (
                existing_google_purchase is None
                and has_recoverable_provider_subscription(
                    db,
                    user_id=user.id,
                    provider="stripe",
                )
            ):
                results.append(
                    GooglePlayPurchaseResult(
                        index=index,
                        accepted=False,
                        entitlement_granted=False,
                        finish_transaction=False,
                        state="provider_conflict",
                        message=(
                            "Existe uma assinatura ativa por outro provedor. "
                            "Gerencie-a antes de iniciar uma assinatura Google Play."
                        ),
                    )
                )
                continue
            try:
                with db.begin_nested():
                    result, user = _process_purchase(
                        db,
                        user=user,
                        purchase=purchase,
                        client=client,
                    )
            except BillingOwnershipConflict:
                result = GooglePlayPurchaseResult(
                    index=index,
                    accepted=False,
                    entitlement_granted=False,
                    finish_transaction=False,
                    state="ownership_conflict",
                    message="Esta compra nao pode ser vinculada a esta conta.",
                )
            except GooglePlayAPIError as exc:
                result = GooglePlayPurchaseResult(
                    index=index,
                    accepted=False,
                    entitlement_granted=False,
                    finish_transaction=False,
                    state="temporarily_unavailable" if exc.retryable else "rejected",
                    message=(
                        "Nao foi possivel confirmar esta compra agora."
                        if exc.retryable
                        else "A compra nao foi reconhecida pelo Google Play."
                    ),
                )
            except GooglePlayConfigurationError:
                result = GooglePlayPurchaseResult(
                    index=index,
                    accepted=False,
                    entitlement_granted=False,
                    finish_transaction=False,
                    state="temporarily_unavailable",
                    message="Nao foi possivel confirmar esta compra agora.",
                )
            except IntegrityError:
                result = GooglePlayPurchaseResult(
                    index=index,
                    accepted=False,
                    entitlement_granted=False,
                    finish_transaction=False,
                    state="ownership_conflict",
                    message="Esta compra nao pode ser vinculada a esta conta.",
                )
            result.index = index
            results.append(result)

        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Conta invalida.")
        resolved = recompute_user_plan(db, user)
        db.commit()
        return results, resolved.plan, resolved.billing_status, resolved.active_product_id


@router.post(
    "/billing/google-play/subscriptions/sync",
    response_model=GooglePlaySyncResponse,
)
def sync_google_play_subscriptions(
    payload: GooglePlayPurchaseBatch,
    response: Response,
    current_user: User = Depends(_native_bearer_user),
) -> GooglePlaySyncResponse:
    _mark_private_response(response)
    results, plan, billing_state, product_id = _sync_batch(payload, current_user)
    return GooglePlaySyncResponse(
        synced=all(result.accepted for result in results),
        plan=plan,
        billing_status=billing_state,
        active_product_id=product_id,
        results=results,
    )


@router.post(
    "/billing/google-play/subscriptions/restore",
    response_model=GooglePlayRestoreResponse,
)
def restore_google_play_subscriptions(
    payload: GooglePlayPurchaseBatch,
    response: Response,
    current_user: User = Depends(_native_bearer_user),
) -> GooglePlayRestoreResponse:
    _mark_private_response(response)
    results, plan, billing_state, product_id = _sync_batch(payload, current_user)
    return GooglePlayRestoreResponse(
        restored=all(result.accepted for result in results),
        plan=plan,
        billing_status=billing_state,
        active_product_id=product_id,
        results=results,
    )


def _verify_pubsub_oidc(authorization: str) -> dict[str, Any]:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticacao invalida.")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticacao invalida.")
    try:
        from google.auth.transport.requests import Request as GoogleAuthRequest
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(
            token,
            GoogleAuthRequest(),
            audience=settings.google_play_pubsub_audience.strip(),
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticacao invalida.") from exc
    expected_email = settings.google_play_pubsub_service_account_email.strip().lower()
    email = str(claims.get("email") or "").strip().lower()
    email_verified = claims.get("email_verified") in {True, "true", "True"}
    if not expected_email or not email_verified or email != expected_email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origem nao autorizada.")
    return claims


def _decode_pubsub_body(raw_body: bytes) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    if not raw_body or len(raw_body) > MAX_PUBSUB_BODY_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Notificacao invalida.")
    try:
        envelope = json.loads(raw_body)
        message = envelope["message"]
        event_id = str(message["messageId"]).strip()
        encoded = message["data"]
        decoded_bytes = base64.b64decode(encoded, validate=True)
        notification = json.loads(decoded_bytes)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Notificacao invalida.") from exc
    if not isinstance(envelope, dict) or not isinstance(message, dict) or not isinstance(notification, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Notificacao invalida.")
    if not event_id or len(event_id) > 255:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Notificacao invalida.")
    # Pub/Sub may add delivery metadata on retries. Idempotency is bound to the
    # decoded provider payload so harmless envelope changes do not look like a
    # message-id collision, while a changed notification is still rejected.
    return envelope, notification, event_id, hashlib.sha256(decoded_bytes).hexdigest()


def _notification_fields(notification: dict[str, Any]) -> tuple[str, str | None, str | None]:
    subscription_notification = notification.get("subscriptionNotification")
    if isinstance(subscription_notification, dict):
        event_type = f"subscription:{subscription_notification.get('notificationType', 'unknown')}"
        return (
            event_type,
            str(subscription_notification.get("purchaseToken") or "").strip() or None,
            None,
        )
    voided = notification.get("voidedPurchaseNotification")
    if isinstance(voided, dict):
        return (
            "voided_purchase",
            str(voided.get("purchaseToken") or "").strip() or None,
            None,
        )
    if isinstance(notification.get("testNotification"), dict):
        return "test", None, None
    return "ignored", None, None


def _revoke_local_purchase(
    db,
    *,
    event_id: int,
    package_name: str,
    token_hash: str,
    provider_status: str,
    entitlement_state: str = "revoked",
) -> bool:
    subscription = (
        db.query(BillingSubscription)
        .filter(
            BillingSubscription.provider == "google_play",
            BillingSubscription.package_name == package_name,
            BillingSubscription.purchase_token_hash == token_hash,
        )
        .first()
    )
    event = db.get(BillingEvent, event_id)
    if event is None:
        return False
    if subscription is None:
        event.status = "unmatched"
        event.processed_at = datetime.datetime.utcnow()
        db.commit()
        return False
    user = lock_user_for_billing_mutation(db, subscription.user_id)
    if user is None:
        event.status = "unmatched"
        event.processed_at = datetime.datetime.utcnow()
        db.commit()
        return False
    subscription.provider_status = provider_status
    subscription.entitlement_state = entitlement_state
    subscription.auto_renew_enabled = False
    subscription.cancel_at_period_end = False
    subscription.last_verified_at = datetime.datetime.utcnow()
    db.query(BillingSubscriptionItem).filter(
        BillingSubscriptionItem.billing_subscription_id == subscription.id
    ).update({BillingSubscriptionItem.entitled: False}, synchronize_session=False)
    recompute_user_plan(db, user)
    event.user_id = user.id
    event.status = "processed"
    event.processed_at = datetime.datetime.utcnow()
    db.commit()
    return True


def _rtdn_identity_user(
    db,
    *,
    package_name: str,
    token_hash: str,
    verified: VerifiedGooglePlaySubscription,
) -> User | None:
    """Resolve all provider identity signals and reject cross-account conflicts."""
    user_ids: set[int] = set()
    identity_hashes = {token_hash}
    for raw_token in (verified.linked_purchase_token, verified.expired_purchase_token):
        if raw_token:
            identity_hashes.add(purchase_token_fingerprint(raw_token))
    rows = (
        db.query(BillingSubscription.user_id)
        .filter(
            BillingSubscription.provider == "google_play",
            BillingSubscription.package_name == package_name,
            BillingSubscription.purchase_token_hash.in_(identity_hashes),
        )
        .all()
    )
    user_ids.update(row.user_id for row in rows)
    account_ids = {
        account_id
        for account_id in (
            verified.obfuscated_account_id,
            verified.expired_obfuscated_account_id,
        )
        if account_id
    }
    if account_ids:
        account_rows = (
            db.query(User.id)
            .filter(User.google_play_account_id.in_(account_ids))
            .all()
        )
        user_ids.update(row.id for row in account_rows)
    if len(user_ids) > 1:
        raise BillingOwnershipConflict("Identidades Google Play conflitantes.")
    if not user_ids:
        return None
    user = lock_user_for_billing_mutation(db, next(iter(user_ids)))
    return user if user is not None and user.is_active else None


def _process_google_play_rtdn(raw_body: bytes, authorization: str) -> Response:
    _require_enabled()
    _verify_pubsub_oidc(authorization)
    envelope, notification, event_id, payload_hash = _decode_pubsub_body(raw_body)
    if envelope.get("subscription") != settings.google_play_pubsub_subscription.strip():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origem nao autorizada.")

    package_name = str(notification.get("packageName") or "").strip()
    event_type, purchase_token, _ = _notification_fields(notification)
    occurred_at = parse_rfc3339(notification.get("eventTimeMillis"))
    if occurred_at is None:
        millis = notification.get("eventTimeMillis")
        try:
            occurred_at = datetime.datetime.utcfromtimestamp(int(millis) / 1000)
        except (TypeError, ValueError, OSError):
            occurred_at = None

    with SessionLocal() as db:
        event = (
            db.query(BillingEvent)
            .filter(BillingEvent.provider == "google_play", BillingEvent.event_id == event_id)
            .first()
        )
        if event is not None and event.status in {"processed", "ignored", "unmatched"}:
            if event.payload_sha256 != payload_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Identificador de notificacao reutilizado.",
                )
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        if event is not None and event.payload_sha256 != payload_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Identificador de notificacao reutilizado.",
            )
        if event is None:
            event = BillingEvent(
                provider="google_play",
                event_id=event_id,
                event_type=event_type,
                package_name=package_name or None,
                purchase_token_hash=purchase_token_fingerprint(purchase_token) if purchase_token else None,
                payload_sha256=payload_hash,
                occurred_at=occurred_at,
                attempts=1,
            )
            db.add(event)
        else:
            event.attempts += 1
            event.last_error = None

        if package_name != settings.google_play_package_name.strip() or event_type == "ignored":
            event.status = "ignored"
            event.processed_at = datetime.datetime.utcnow()
            db.commit()
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        if event_type == "test":
            event.status = "processed"
            event.processed_at = datetime.datetime.utcnow()
            db.commit()
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        if not purchase_token:
            event.status = "ignored"
            event.processed_at = datetime.datetime.utcnow()
            db.commit()
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        db.commit()

        token_hash = purchase_token_fingerprint(purchase_token)
        if event_type == "voided_purchase":
            _revoke_local_purchase(
                db,
                event_id=event.id,
                package_name=package_name,
                token_hash=token_hash,
                provider_status="VOIDED_PURCHASE",
            )
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        try:
            client = get_google_play_client()
            api_payload = client.get_subscription(purchase_token)
            verified = parse_verified_subscription(api_payload, product_catalog_by_id(strict=True))
            if event_type == "subscription:12":
                verified = dataclasses.replace(
                    verified,
                    entitlement_state="revoked",
                    auto_renew_enabled=False,
                    items=[dataclasses.replace(item, entitled=False) for item in verified.items],
                )
        except (GooglePlayAPIError, GooglePlayConfigurationError) as exc:
            terminal_event = (
                event_type == "subscription:12"
                and isinstance(exc, GooglePlayAPIError)
                and exc.status_code in {404, 410}
            ) or (
                event_type == "subscription:13"
                and isinstance(exc, GooglePlayAPIError)
                and exc.status_code == 410
            )
            if terminal_event:
                _revoke_local_purchase(
                    db,
                    event_id=event.id,
                    package_name=package_name,
                    token_hash=token_hash,
                    provider_status=(
                        "SUBSCRIPTION_REVOKED"
                        if event_type == "subscription:12"
                        else "SUBSCRIPTION_EXPIRED"
                    ),
                    entitlement_state=(
                        "revoked" if event_type == "subscription:12" else "inactive"
                    ),
                )
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            event = db.get(BillingEvent, event.id)
            if event is not None:
                event.status = "failed"
                event.last_error = "provider_temporarily_unavailable"
                db.commit()
            if isinstance(exc, GooglePlayAPIError) and not exc.retryable:
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Provedor temporariamente indisponivel.",
            ) from exc

        event = db.get(BillingEvent, event.id)
        try:
            user = _rtdn_identity_user(
                db,
                package_name=package_name,
                token_hash=token_hash,
                verified=verified,
            )
        except BillingOwnershipConflict:
            if event is not None:
                event.status = "rejected"
                event.last_error = "ownership_conflict"
                event.processed_at = datetime.datetime.utcnow()
                db.commit()
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        if user is None or event is None:
            if event is not None:
                event.status = "unmatched"
                event.processed_at = datetime.datetime.utcnow()
                db.commit()
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        try:
            stored = persist_verified_purchase(
                db,
                user=user,
                purchase_token=purchase_token,
                verified=verified,
            )
            recompute_user_plan(db, user)
            event.user_id = user.id
            event.status = "processed"
            event.processed_at = datetime.datetime.utcnow()
            db.commit()
        except (BillingOwnershipConflict, IntegrityError):
            db.rollback()
            event = db.get(BillingEvent, event.id)
            if event is not None:
                event.status = "rejected"
                event.last_error = "ownership_conflict"
                event.processed_at = datetime.datetime.utcnow()
                db.commit()
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        if verified.entitlement_granted and verified.requires_acknowledgement:
            try:
                client.acknowledge_subscription(purchase_token, verified.items[0].product_id)
            except GooglePlayAPIError:
                pass
            else:
                stored = db.get(BillingSubscription, stored.id)
                if stored is not None:
                    stored.acknowledgement_state = "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"
                    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/billing/google-play/rtdn", status_code=status.HTTP_204_NO_CONTENT)
async def google_play_rtdn(
    request: Request,
    authorization: str = Header(default=""),
) -> Response:
    raw_body = await request.body()
    return await run_in_threadpool(_process_google_play_rtdn, raw_body, authorization)
