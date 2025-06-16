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

    MAIL_SERVER = "mail.termondttech.com"
    MAIL_PORT = 465
    MAIL_USE_SSL = True
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")  # info@termondttech.com
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")  # Store this securely in your env!
    MAIL_DEFAULT_SENDER = ("Syvrona Support", "info@termondttech.com")


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
