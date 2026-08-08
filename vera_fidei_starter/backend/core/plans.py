from __future__ import annotations

from core.config import settings

PLAN_ORDER = ["fiel", "catequista", "apologeta", "patristico", "magisterio"]
OWNER_PLAN = "magisterio"
DEFAULT_PLAN = "fiel"
PLAN_VERIFICATION_LIMITS = {
    "fiel": 10,
    "catequista": 25,
    "apologeta": 50,
    "patristico": 100,
    "magisterio": None,
}
PLAN_LABELS = {
    "fiel": "Fiel",
    "catequista": "Catequista",
    "apologeta": "Apologeta",
    "patristico": "Patristico",
    "magisterio": "Magisterio",
}
PLAN_HISTORY_LIMITS = {
    "fiel": 10,
    "catequista": None,
    "apologeta": None,
    "patristico": None,
    "magisterio": None,
}
PLAN_SEARCH_DAILY_LIMITS = {
    "fiel": 5,
    "catequista": 20,
    "apologeta": 50,
    "patristico": 100,
    "magisterio": None,
}
PLAN_FEATURES = {
    "fiel": {
        "basic_verification",
        "confidence_result",
        "recent_history",
        "library_access",
    },
    "catequista": {
        "basic_verification",
        "confidence_result",
        "recent_history",
        "library_access",
        "pdf_reports",
        "exact_reference",
        "full_history",
    },
    "apologeta": {
        "basic_verification",
        "confidence_result",
        "recent_history",
        "library_access",
        "pdf_reports",
        "exact_reference",
        "full_history",
        "patristic_context",
        "translation_analysis",
        "textual_variant_analysis",
        "digitized_pdfs",
        "csv_export",
    },
    "patristico": {
        "basic_verification",
        "confidence_result",
        "recent_history",
        "library_access",
        "pdf_reports",
        "exact_reference",
        "full_history",
        "patristic_context",
        "translation_analysis",
        "textual_variant_analysis",
        "digitized_pdfs",
        "csv_export",
        "institution_panel",
        "member_management",
        "monthly_usage_report",
    },
    "magisterio": {
        "basic_verification",
        "confidence_result",
        "recent_history",
        "library_access",
        "pdf_reports",
        "exact_reference",
        "full_history",
        "patristic_context",
        "translation_analysis",
        "textual_variant_analysis",
        "digitized_pdfs",
        "csv_export",
        "institution_panel",
        "member_management",
        "monthly_usage_report",
        "dedicated_api",
        "rest_endpoint",
        "api_key_management",
        "external_integrations",
        "advanced_priority",
    },
}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_owner_email(email: str) -> bool:
    return normalize_email(email) == normalize_email(settings.owner_email)


def initial_plan_for_email(email: str) -> str:
    return OWNER_PLAN if is_owner_email(email) else DEFAULT_PLAN


def verification_limit_for_plan(plan: str | None) -> int | None:
    return PLAN_VERIFICATION_LIMITS.get(plan or DEFAULT_PLAN, PLAN_VERIFICATION_LIMITS[DEFAULT_PLAN])


def normalized_plan(plan: str | None) -> str:
    return plan if plan in PLAN_ORDER else DEFAULT_PLAN


def plan_rank(plan: str | None) -> int:
    return PLAN_ORDER.index(normalized_plan(plan))


def has_min_plan(plan: str | None, min_plan: str) -> bool:
    return plan_rank(plan) >= plan_rank(min_plan)


def has_feature(plan: str | None, feature: str) -> bool:
    return feature in PLAN_FEATURES.get(normalized_plan(plan), PLAN_FEATURES[DEFAULT_PLAN])


def history_limit_for_plan(plan: str | None) -> int | None:
    return PLAN_HISTORY_LIMITS.get(normalized_plan(plan))


def search_daily_limit_for_plan(plan: str | None) -> int | None:
    return PLAN_SEARCH_DAILY_LIMITS.get(normalized_plan(plan))


def ensure_owner_access(user) -> bool:
    if not is_owner_email(user.email):
        return False
    changed = False
    if user.plan != OWNER_PLAN:
        user.plan = OWNER_PLAN
        changed = True
    if getattr(user, "billing_status", None) != "owner":
        user.billing_status = "owner"
        changed = True
    if getattr(user, "billing_cancel_at_period_end", False):
        user.billing_cancel_at_period_end = False
        changed = True
    return changed
