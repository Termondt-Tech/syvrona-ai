"""Plan-aware rate-limit helpers.

Usage in routes::

    from app.limits import plan_limits
    @limiter.limit(plan_limits)
    def answer():
        ...
"""

from functools import wraps
from datetime import datetime, UTC
from flask import Response, current_app


from flask_login import current_user

from app.models import UsageStat

FREE_TIER = "free"
PRO_TIER = "pro"


def _tier() -> str:
    """Return 'pro' or 'free' based on the user’s stored Stripe price ID.

    Falls back to 'free' if the user is anonymous or config is missing.
    """
    try:
        price_ids: set[str] = set(
            current_app.config.get("STRIPE_PRICE_IDS", {}).values()
        )
    except RuntimeError:
        # Outside an app context (e.g., unit tests) — default to free
        return FREE_TIER

    plan_id: str | None = getattr(current_user, "subscription_plan", None)
    return PRO_TIER if plan_id in price_ids else FREE_TIER


# Burst + daily windows understood by Flask-Limiter.
DEFAULT_TIER_LIMITS: dict[str, str] = {
    FREE_TIER: "5 per minute;100 per day",
    PRO_TIER: "60 per minute;3000 per day",
}


def plan_limits() -> str:
    """Return the semicolon-separated limiter string for the current request."""
    tier_limits: dict[str, str] = current_app.config.get(
        "RATE_LIMIT_TIERS", DEFAULT_TIER_LIMITS
    )
    return tier_limits.get(_tier(), tier_limits[FREE_TIER])


def enforce_token_quota(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        # 1) load config once per request
        limits = current_app.config.get("TOKEN_QUOTAS", {})
        tier = _tier()  # 'free' or 'pro'
        quota = limits.get(tier, limits.get("free", 50_000))  # default to free quota

        first = datetime.now(tz=UTC).date().replace(day=1)
        stat = UsageStat.query.filter_by(
            user_id=current_user.id, period_start=first
        ).first()
        tokens_used = stat.tokens if stat else 0

        if tokens_used >= quota:
            return Response("Monthly quota exceeded", 402)
        return view(*args, **kwargs)

    return wrapper
