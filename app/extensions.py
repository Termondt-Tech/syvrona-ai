"""Shared Flask extensions.

Usage elsewhere::

    from app.extensions import limiter
"""

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import current_user


def _user_or_ip() -> str:
    """Return a stable rate-limit key: user ID when logged in, else caller IP."""
    return (
        str(current_user.id) if current_user.is_authenticated else get_remote_address()
    )


# One Limiter per process, attached in create_app(). Its storage comes from the app's
# RATELIMIT_STORAGE_URI (Redis in compose, memory:// in tests).
limiter = Limiter(key_func=_user_or_ip, default_limits=[])


def init_extensions(app: Flask) -> None:
    """Attach the shared extensions to *app*. Safe to call twice for one app."""
    if app.extensions.get("limiter_init_done"):
        return
    limiter.init_app(app)
    app.extensions["limiter_init_done"] = True
