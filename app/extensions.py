"""Shared Flask extensions.

Usage elsewhere::

    from app.extensions import limiter
"""

from typing import Optional
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import current_user
from flask import Flask
from redis import Redis


def _user_or_ip() -> str:
    """Return a stable rate-limit key: user ID when logged in, else caller IP."""
    return (
        str(current_user.id) if current_user.is_authenticated else get_remote_address()
    )


# Lazy-initialised Limiter.  We attach it inside create_app() to avoid
# touching current_app at import time.
limiter = Limiter(
    key_func=_user_or_ip,
    default_limits=[],
)

# ------------------------------------------------------------------ #
#  SINGLETONS that live for the lifetime of each Gunicorn worker     #
# ------------------------------------------------------------------ #
redis_client: Optional[Redis] = None  # ← add this line
limiter = Limiter(key_func=_user_or_ip, default_limits=[])


# ------------------------------------------------------------------ #
#  Extension initialiser                                             #
# ------------------------------------------------------------------ #
def init_extensions(app: Flask) -> None:
    """Attach all shared extensions to *app*.

    Call from create_app() after app is configured.
    """
    # ── 1. short-circuit if we've already done this for this app ──────────
    if app.extensions.get("limiter_init_done"):
        return  # idempotent -> nothing more to do

    # ── 2. Redis client (optional, but keeps one pool per worker) ─────────
    global redis_client
    if redis_client is None:
        redis_client = Redis.from_url(
            app.config.get("RATELIMIT_STORAGE_URI", "redis://redis:6379/0")
        )
    app.extensions["redis_client"] = redis_client

    # ── 3. Limiter --------------------------------------------------------
    limiter.storage_uri = app.config["RATELIMIT_STORAGE_URI"]  # inject runtime cfg
    limiter.init_app(app)  # registers handlers
    app.extensions["limiter"] = limiter

    # ── 4. mark as done so later calls are no-ops ------------------------
    app.extensions["limiter_init_done"] = True
