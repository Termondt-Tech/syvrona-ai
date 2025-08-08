# app/ratelimit_logging.py
import logging
from flask import Blueprint, request, Response
from flask_limiter.errors import RateLimitExceeded
from flask_login import current_user

bp = Blueprint("ratelimit_logging", __name__)
log = logging.getLogger("ratelimit")


@bp.app_errorhandler(RateLimitExceeded)
def handle_ratelimit(e: RateLimitExceeded) -> Response:
    """Log one line and return a polite 429 JSON/plain response."""
    user_id = getattr(current_user, "id", None)
    log.warning(
        "RATE_LIMIT_EXCEEDED user=%s ip=%s path=%s limit=\"%s\" retry_after=%s",
        user_id,
        request.remote_addr,
        request.path,
        e.description,          # e.g. "3 per 1 minute"
        getattr(e, "retry_after", "unknown"),
    )
    return Response("Rate limit exceeded", status=429, mimetype="text/plain")
