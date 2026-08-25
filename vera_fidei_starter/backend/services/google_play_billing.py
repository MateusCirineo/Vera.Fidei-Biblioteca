from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import http.client
import json
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from core.config import settings
from models.database import BillingSubscription, BillingSubscriptionItem, User
from services.billing_entitlements import (
    ACCESS_STATES,
    PAID_PLAN_NAMES,
    BillingOwnershipConflict,
    SubscriptionItemInput,
    upsert_subscription,
)


ANDROID_PUBLISHER_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
EXPECTED_GOOGLE_PLAY_PRODUCTS = {
    "catequista": "vf.sub.catequista",
    "apologeta": "vf.sub.apologeta",
    "patristico": "vf.sub.patristico",
    "magisterio": "vf.sub.magisterio",
}
EXPECTED_GOOGLE_PLAY_BASE_PLAN = "monthly"


class GooglePlayConfigurationError(RuntimeError):
    pass


class GooglePlayAPIError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


@dataclass(frozen=True)
class GooglePlayProduct:
    product_id: str
    plan: str
    base_plan_id: str | None = None


@dataclass(frozen=True)
class VerifiedGooglePlaySubscription:
    provider_status: str
    entitlement_state: str
    acknowledgement_state: str
    items: list[SubscriptionItemInput]
    current_period_end: datetime.datetime | None
    auto_renew_enabled: bool
    linked_purchase_token: str | None
    obfuscated_account_id: str | None
    expired_purchase_token: str | None
    expired_obfuscated_account_id: str | None
    test_purchase: bool
    latest_order_id: str | None
    provider_event_at: datetime.datetime | None

    @property
    def entitlement_granted(self) -> bool:
        return self.entitlement_state in ACCESS_STATES and any(item.entitled for item in self.items)

    @property
    def requires_acknowledgement(self) -> bool:
        return self.acknowledgement_state != "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"


def _clean(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def load_product_catalog(*, strict: bool = True) -> list[GooglePlayProduct]:
    raw = (settings.google_play_products_json or "").strip()
    if not raw:
        if strict:
            raise GooglePlayConfigurationError("Catalogo Google Play nao configurado.")
        return []
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError) as exc:
        if strict:
            raise GooglePlayConfigurationError("Catalogo Google Play invalido.") from exc
        return []

    rows: list[dict[str, Any]] = []
    if isinstance(decoded, list):
        rows = [row for row in decoded if isinstance(row, dict)]
        if len(rows) != len(decoded):
            rows = []
    elif isinstance(decoded, dict):
        for plan, value in decoded.items():
            if isinstance(value, str):
                rows.append({"plan": plan, "product_id": value})
            elif isinstance(value, dict):
                rows.append({"plan": plan, **value})

    products: list[GooglePlayProduct] = []
    seen_products: set[str] = set()
    seen_plans: set[str] = set()
    for row in rows:
        plan = (_clean(row.get("plan")) or "").lower()
        product_id = _clean(row.get("product_id"))
        base_plan_id = _clean(row.get("base_plan_id"))
        if (
            plan not in PAID_PLAN_NAMES
            or not product_id
            or len(product_id) > 255
            or product_id in seen_products
            or plan in seen_plans
        ):
            products = []
            break
        seen_products.add(product_id)
        seen_plans.add(plan)
        products.append(
            GooglePlayProduct(
                product_id=product_id,
                plan=plan,
                base_plan_id=base_plan_id,
            )
        )

    if strict and (
        not products
        or {product.plan for product in products} != set(PAID_PLAN_NAMES)
        or any(
            EXPECTED_GOOGLE_PLAY_PRODUCTS.get(product.plan) != product.product_id
            or product.base_plan_id != EXPECTED_GOOGLE_PLAY_BASE_PLAN
            for product in products
        )
    ):
        raise GooglePlayConfigurationError(
            "Catalogo Google Play deve corresponder aos quatro produtos e planos-base oficiais."
        )
    return products


def product_catalog_by_id(*, strict: bool = True) -> dict[str, GooglePlayProduct]:
    return {product.product_id: product for product in load_product_catalog(strict=strict)}


def purchase_token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _fernet() -> Fernet:
    key = (settings.google_play_token_encryption_key or "").strip().encode("ascii")
    try:
        return Fernet(key)
    except (TypeError, ValueError) as exc:
        raise GooglePlayConfigurationError("Chave de criptografia Google Play invalida.") from exc


def encrypt_purchase_token(token: str) -> str:
    return _fernet().encrypt(token.encode("utf-8")).decode("ascii")


def decrypt_purchase_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise GooglePlayConfigurationError("Token Google Play armazenado nao pode ser decriptado.") from exc


def obfuscated_account_id(user_id: int) -> str:
    secret = (settings.google_play_account_hmac_secret or "").strip().encode("utf-8")
    if len(secret) < 32:
        raise GooglePlayConfigurationError("Segredo de conta Google Play nao configurado.")
    digest = hmac.new(secret, f"vera-fidei:user:{user_id}".encode("utf-8"), hashlib.sha256).digest()
    return "vf_" + base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def account_id_matches(expected: str, received: str | None) -> bool:
    return bool(received) and hmac.compare_digest(expected, received or "")


def persist_verified_purchase(
    db: Session,
    *,
    user: User,
    purchase_token: str,
    verified: VerifiedGooglePlaySubscription,
) -> BillingSubscription:
    expected_account_id = obfuscated_account_id(user.id)
    token_hash = purchase_token_fingerprint(purchase_token)
    linked_hash = (
        purchase_token_fingerprint(verified.linked_purchase_token)
        if verified.linked_purchase_token
        else None
    )
    expired_hash = (
        purchase_token_fingerprint(verified.expired_purchase_token)
        if verified.expired_purchase_token
        else None
    )

    identity_proven = False
    if verified.obfuscated_account_id:
        if not account_id_matches(expected_account_id, verified.obfuscated_account_id):
            raise BillingOwnershipConflict("A compra pertence a outra conta.")
        identity_proven = True
    if verified.expired_obfuscated_account_id:
        if not account_id_matches(expected_account_id, verified.expired_obfuscated_account_id):
            raise BillingOwnershipConflict("A compra expirada pertence a outra conta.")
        identity_proven = True

    ownership_hashes = {value for value in (token_hash, linked_hash, expired_hash) if value}
    if ownership_hashes:
        prior_rows = (
            db.query(BillingSubscription)
            .filter(
                BillingSubscription.provider == "google_play",
                BillingSubscription.package_name == settings.google_play_package_name.strip(),
                BillingSubscription.purchase_token_hash.in_(ownership_hashes),
            )
            .all()
        )
        for prior in prior_rows:
            if prior.user_id != user.id:
                raise BillingOwnershipConflict("A compra ja pertence a outra conta.")
        identity_proven = identity_proven or bool(prior_rows)

    if settings.google_play_require_obfuscated_account_id and not identity_proven:
        raise BillingOwnershipConflict("A compra nao informa uma identidade proprietaria verificavel.")

    if user.google_play_account_id and not account_id_matches(
        expected_account_id,
        user.google_play_account_id,
    ):
        raise BillingOwnershipConflict("Identidade de faturamento inconsistente.")
    user.google_play_account_id = expected_account_id

    if linked_hash and verified.entitlement_granted:
        replaced = (
            db.query(BillingSubscription)
            .filter(
                BillingSubscription.provider == "google_play",
                BillingSubscription.package_name == settings.google_play_package_name.strip(),
                BillingSubscription.purchase_token_hash == linked_hash,
            )
            .first()
        )
        if replaced is not None and replaced.user_id != user.id:
            raise BillingOwnershipConflict("A compra substituida pertence a outra conta.")
        if replaced is not None and replaced.purchase_token_hash != token_hash:
            replaced.entitlement_state = "replaced"
            replaced.auto_renew_enabled = False
            db.query(BillingSubscriptionItem).filter(
                BillingSubscriptionItem.billing_subscription_id == replaced.id
            ).update({BillingSubscriptionItem.entitled: False}, synchronize_session=False)

    return upsert_subscription(
        db,
        user=user,
        provider="google_play",
        package_name=settings.google_play_package_name.strip(),
        provider_status=verified.provider_status,
        entitlement_state=verified.entitlement_state,
        acknowledgement_state=verified.acknowledgement_state,
        items=verified.items,
        purchase_token_hash=token_hash,
        purchase_token_ciphertext=encrypt_purchase_token(purchase_token),
        linked_purchase_token_hash=linked_hash,
        current_period_end=verified.current_period_end,
        auto_renew_enabled=verified.auto_renew_enabled,
        cancel_at_period_end=verified.entitlement_state == "canceled_valid",
        test_purchase=verified.test_purchase,
        provider_event_at=verified.provider_event_at,
        last_order_id=verified.latest_order_id,
    )


def parse_rfc3339(value: Any) -> datetime.datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return parsed


def entitlement_state_for_google(
    provider_status: str,
    current_period_end: datetime.datetime | None,
) -> str:
    if provider_status == "SUBSCRIPTION_STATE_ACTIVE":
        return "entitled"
    if provider_status == "SUBSCRIPTION_STATE_IN_GRACE_PERIOD":
        return "grace"
    if provider_status == "SUBSCRIPTION_STATE_CANCELED":
        if current_period_end and current_period_end > datetime.datetime.utcnow():
            return "canceled_valid"
        return "inactive"
    if provider_status == "SUBSCRIPTION_STATE_PAUSED":
        return "paused"
    if provider_status == "SUBSCRIPTION_STATE_ON_HOLD":
        return "hold"
    if provider_status == "SUBSCRIPTION_STATE_PENDING":
        return "pending"
    return "inactive"


def parse_verified_subscription(
    payload: dict[str, Any],
    catalog: dict[str, GooglePlayProduct],
) -> VerifiedGooglePlaySubscription:
    provider_status = _clean(payload.get("subscriptionState")) or "SUBSCRIPTION_STATE_UNSPECIFIED"
    acknowledgement_state = (
        _clean(payload.get("acknowledgementState"))
        or "ACKNOWLEDGEMENT_STATE_PENDING"
    )
    raw_items = payload.get("lineItems")
    if not isinstance(raw_items, list) or not raw_items:
        raise GooglePlayAPIError("A compra nao possui itens verificaveis.")

    parsed_rows: list[tuple[dict[str, Any], GooglePlayProduct, datetime.datetime | None]] = []
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            raise GooglePlayAPIError("A compra retornou um item invalido.")
        product_id = _clean(raw_item.get("productId"))
        product = catalog.get(product_id or "")
        if product is None:
            raise GooglePlayAPIError("A compra nao pertence ao catalogo do Vera Fidei.")
        offer = raw_item.get("offerDetails") if isinstance(raw_item.get("offerDetails"), dict) else {}
        returned_base_plan = _clean(offer.get("basePlanId"))
        if product.base_plan_id and returned_base_plan != product.base_plan_id:
            raise GooglePlayAPIError("O plano-base da compra nao corresponde ao catalogo.")
        raw_expiry = raw_item.get("expiryTime")
        expiry = parse_rfc3339(raw_expiry)
        if raw_expiry is not None and expiry is None:
            raise GooglePlayAPIError("A compra retornou uma expiracao invalida.")
        parsed_rows.append((raw_item, product, expiry))

    current_period_end = max(
        (expiry for _, _, expiry in parsed_rows if expiry is not None),
        default=None,
    )
    now = datetime.datetime.utcnow()
    current_rows = [row for row in parsed_rows if row[2] is not None and row[2] > now]
    deferred_replacement_products = {
        _clean(raw_item["deferredItemReplacement"].get("productId"))
        for raw_item, _, expiry in parsed_rows
        if expiry is not None
        and expiry > now
        and isinstance(raw_item.get("deferredItemReplacement"), dict)
    }
    missing_expiry_products = {
        product.product_id for _, product, expiry in parsed_rows if expiry is None
    }
    valid_deferred_shape = bool(
        provider_status == "SUBSCRIPTION_STATE_ACTIVE"
        and current_rows
        and missing_expiry_products
        and None not in deferred_replacement_products
        and missing_expiry_products.issubset(deferred_replacement_products)
    )
    access_capable_statuses = {
        "SUBSCRIPTION_STATE_ACTIVE",
        "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
        "SUBSCRIPTION_STATE_CANCELED",
    }
    if provider_status in access_capable_statuses and any(
        expiry is None for _, _, expiry in parsed_rows
    ) and not valid_deferred_shape:
        raise GooglePlayAPIError("A compra nao possui expiracao verificavel.")
    if provider_status in {
        "SUBSCRIPTION_STATE_ACTIVE",
        "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
    } and not current_rows:
        raise GooglePlayAPIError("A compra nao possui direito vigente verificavel.")

    entitlement_state = entitlement_state_for_google(provider_status, current_period_end)
    items: list[SubscriptionItemInput] = []
    latest_order_id: str | None = None
    any_auto_renew = False
    for index, (raw_item, product, expiry) in enumerate(parsed_rows):
        offer = raw_item.get("offerDetails") if isinstance(raw_item.get("offerDetails"), dict) else {}
        auto_renew = raw_item.get("autoRenewingPlan")
        auto_renew_enabled = bool(
            isinstance(auto_renew, dict) and auto_renew.get("autoRenewEnabled") is True
        )
        any_auto_renew = any_auto_renew or auto_renew_enabled
        order_id = _clean(raw_item.get("latestSuccessfulOrderId"))
        latest_order_id = order_id or latest_order_id
        entitled = entitlement_state in ACCESS_STATES and expiry is not None and expiry > now
        # The same order id may legitimately appear on multiple line items.  Include
        # stable, non-secret item coordinates so the per-subscription unique key
        # cannot collide in deferred replacements or add-on purchases.
        item_key = ":".join(
            (
                "google",
                order_id or "no-order",
                product.product_id,
                _clean(offer.get("basePlanId")) or "no-base-plan",
                str(index),
            )
        )
        items.append(
            SubscriptionItemInput(
                item_key=item_key[:700],
                product_id=product.product_id,
                plan=product.plan,
                base_plan_id=_clean(offer.get("basePlanId")),
                offer_id=_clean(offer.get("offerId")),
                expiry_time=expiry,
                auto_renew_enabled=auto_renew_enabled,
                entitled=entitled,
            )
        )

    external_ids = (
        payload.get("externalAccountIdentifiers")
        if isinstance(payload.get("externalAccountIdentifiers"), dict)
        else {}
    )
    out_of_app = (
        payload.get("outOfAppPurchaseContext")
        if isinstance(payload.get("outOfAppPurchaseContext"), dict)
        else {}
    )
    expired_external_ids = (
        out_of_app.get("expiredExternalAccountIdentifiers")
        if isinstance(out_of_app.get("expiredExternalAccountIdentifiers"), dict)
        else {}
    )
    return VerifiedGooglePlaySubscription(
        provider_status=provider_status,
        entitlement_state=entitlement_state,
        acknowledgement_state=acknowledgement_state,
        items=items,
        current_period_end=current_period_end,
        auto_renew_enabled=any_auto_renew,
        linked_purchase_token=_clean(payload.get("linkedPurchaseToken")),
        obfuscated_account_id=_clean(external_ids.get("obfuscatedExternalAccountId")),
        expired_purchase_token=_clean(out_of_app.get("expiredPurchaseToken")),
        expired_obfuscated_account_id=_clean(
            expired_external_ids.get("obfuscatedExternalAccountId")
        ),
        test_purchase=isinstance(payload.get("testPurchase"), dict),
        latest_order_id=latest_order_id,
        provider_event_at=parse_rfc3339(payload.get("startTime")),
    )


class GooglePlayClient:
    def __init__(self) -> None:
        service_account_file = Path(settings.google_play_service_account_file).expanduser()
        if not service_account_file.is_file():
            raise GooglePlayConfigurationError("Credencial de servico Google Play indisponivel.")
        try:
            from google.oauth2 import service_account
        except ImportError as exc:
            raise GooglePlayConfigurationError("Dependencia google-auth indisponivel.") from exc
        try:
            self._credentials = service_account.Credentials.from_service_account_file(
                str(service_account_file),
                scopes=[ANDROID_PUBLISHER_SCOPE],
            )
        except (OSError, TypeError, ValueError) as exc:
            raise GooglePlayConfigurationError("Credencial de servico Google Play invalida.") from exc

    def _access_token(self) -> str:
        try:
            from google.auth.transport.requests import Request as GoogleAuthRequest

            if not self._credentials.valid or not self._credentials.token:
                self._credentials.refresh(GoogleAuthRequest())
        except Exception as exc:
            raise GooglePlayAPIError("Falha ao autenticar no Google Play.", retryable=True) from exc
        token = _clean(self._credentials.token)
        if not token:
            raise GooglePlayAPIError("Falha ao autenticar no Google Play.", retryable=True)
        return token

    def _request(self, method: str, url: str, *, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        parsed = urlsplit(url)
        connection = http.client.HTTPSConnection(
            parsed.hostname,
            port=parsed.port,
            timeout=settings.google_play_http_timeout_seconds,
        )
        body = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            response_body = response.read()
            response_status = response.status
        except (OSError, TimeoutError, socket.timeout, http.client.HTTPException) as exc:
            raise GooglePlayAPIError("Google Play temporariamente indisponivel.", retryable=True) from exc
        finally:
            connection.close()
        if response_status >= 400:
            retryable = response_status == 429 or response_status >= 500
            raise GooglePlayAPIError(
                "Google Play recusou a verificacao da compra.",
                retryable=retryable,
                status_code=response_status,
            )
        if not response_body:
            return {}
        try:
            payload = json.loads(response_body)
        except ValueError as exc:
            raise GooglePlayAPIError("Google Play retornou uma resposta invalida.", retryable=True) from exc
        if not isinstance(payload, dict):
            raise GooglePlayAPIError("Google Play retornou uma resposta invalida.", retryable=True)
        return payload

    def get_subscription(self, purchase_token: str) -> dict[str, Any]:
        package_name = quote(settings.google_play_package_name.strip(), safe="")
        token = quote(purchase_token, safe="")
        url = (
            "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
            f"{package_name}/purchases/subscriptionsv2/tokens/{token}"
        )
        return self._request("GET", url)

    def acknowledge_subscription(self, purchase_token: str, subscription_id: str) -> None:
        package_name = quote(settings.google_play_package_name.strip(), safe="")
        product_id = quote(subscription_id, safe="")
        token = quote(purchase_token, safe="")
        url = (
            "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
            f"{package_name}/purchases/subscriptions/{product_id}/tokens/{token}:acknowledge"
        )
        self._request("POST", url, json_body={})


def get_google_play_client() -> GooglePlayClient:
    return GooglePlayClient()


def validate_google_play_configuration() -> None:
    if not settings.google_play_enabled:
        return
    if not settings.google_play_package_name.strip():
        raise GooglePlayConfigurationError("Package name Google Play nao configurado.")
    if settings.google_play_require_obfuscated_account_id is not True:
        raise GooglePlayConfigurationError(
            "Vinculo de conta ofuscada Google Play deve permanecer obrigatorio."
        )
    load_product_catalog(strict=True)
    _fernet()
    obfuscated_account_id(1)
    if not settings.google_play_service_account_file.strip():
        raise GooglePlayConfigurationError("Credencial de servico Google Play nao configurada.")
    credential_path = Path(settings.google_play_service_account_file).expanduser()
    if not credential_path.is_file():
        raise GooglePlayConfigurationError("Credencial de servico Google Play indisponivel.")
    try:
        credential_payload = json.loads(credential_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise GooglePlayConfigurationError("Credencial de servico Google Play invalida.") from exc
    if not isinstance(credential_payload, dict) or not all(
        _clean(credential_payload.get(field))
        for field in ("client_email", "private_key", "token_uri")
    ):
        raise GooglePlayConfigurationError("Credencial de servico Google Play invalida.")
    if not settings.google_play_pubsub_audience.strip():
        raise GooglePlayConfigurationError("Audience Pub/Sub Google Play nao configurada.")
    if not settings.google_play_pubsub_service_account_email.strip():
        raise GooglePlayConfigurationError("Conta de servico Pub/Sub Google Play nao configurada.")
    if not settings.google_play_pubsub_subscription.strip():
        raise GooglePlayConfigurationError("Assinatura Pub/Sub Google Play nao configurada.")
    if not settings.google_play_pubsub_subscription.strip().startswith("projects/"):
        raise GooglePlayConfigurationError("Assinatura Pub/Sub Google Play invalida.")
    if not 1 <= int(settings.google_play_reconcile_stale_hours) <= 168:
        raise GooglePlayConfigurationError("Intervalo do reconciliador Google Play invalido.")
    if not 1 <= int(settings.google_play_reconcile_batch_size) <= 1000:
        raise GooglePlayConfigurationError("Lote do reconciliador Google Play invalido.")
    if not 1 <= int(settings.google_play_sync_rate_limit) <= 120:
        raise GooglePlayConfigurationError("Limite de sincronizacao Google Play invalido.")
    if not 10 <= int(settings.google_play_sync_rate_window_seconds) <= 3600:
        raise GooglePlayConfigurationError("Janela de sincronizacao Google Play invalida.")
