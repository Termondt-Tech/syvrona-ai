import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SECURITY_PASSWORD_SALT = os.getenv("SECURITY_PASSWORD_SALT")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
