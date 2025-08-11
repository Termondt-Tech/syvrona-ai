import os
import json


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SECURITY_PASSWORD_SALT = os.getenv("SECURITY_PASSWORD_SALT")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        # Reasonable defaults for MySQL + gthread workers
        "pool_size": int(os.getenv("DB_POOL_SIZE", 10)),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", 5)),
        "pool_pre_ping": True,  # detect dead connections
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", 1800)),  # seconds
        "pool_reset_on_return": "rollback",  # keeps connections clean between requests
    }

    STRIPE_PRICE_IDS = {
        "pro_monthly": os.getenv("STRIPE_PRICE_ID_PRO_MONTHLY"),
        "pro_yearly": os.getenv("STRIPE_PRICE_ID_PRO_YEARLY"),
    }

    DEBUG = False
    TESTING = False
    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError("DATABASE_URL must be set for all environments.")
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY must be set for all environments.")

    MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
    MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
    MAILGUN_FROM_EMAIL = os.getenv(
        "MAILGUN_FROM_EMAIL", f"Syvrona Support <mailgun@{MAILGUN_DOMAIN}>"
    )
    FEATURE_FLAGS = {
        "FREE_TRIAL_ENABLED": (
            os.environ.get("FREE_TRIAL_ENABLED", "false").lower() == "true"
        ),
        "FREE_TRIAL_DAYS": int(os.environ.get("FREE_TRIAL_DAYS", 0)),
        # Add future flags here
    }

    HCAPTCHA_ENABLED = os.getenv("HCAPTCHA_ENABLED", "false").lower() == "true"
    HCAPTCHA_SITE_KEY = os.getenv("HCAPTCHA_SITE_KEY")
    HCAPTCHA_SECRET_KEY = os.getenv("HCAPTCHA_SECRET_KEY")

    # CSRF protection
    WTF_CSRF_ENABLED = os.getenv("WTF_CSRF_ENABLED", "true").lower() == "true"
    WTF_CSRF_TIME_LIMIT = int(os.getenv("WTF_CSRF_TIME_LIMIT", 86400))  # 24 hours

    # Rate limiting configuration
    # Default to Redis; can be overridden in .env
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "redis://redis:6379/0")

    # ---- Rate-limit tiers -----------------------------------------------
    _default = {
        "free": "5 per minute;100 per day",
        "pro": "60 per minute;3000 per day",
    }

    _env_json = os.getenv("RATE_LIMIT_TIERS")

    if _env_json:
        try:
            RATE_LIMIT_TIERS = json.loads(_env_json)
        except json.JSONDecodeError:
            raise ValueError("RATE_LIMIT_TIERS must be valid JSON")
    else:
        RATE_LIMIT_TIERS = _default

    # ---- Token quotas ---------------------------------------------------
    # Default to 50,000 tokens for free tier; can be overridden in .env
    TOKEN_QUOTAS = json.loads(os.getenv("TOKEN_QUOTAS", '{"free": 50000}'))


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
