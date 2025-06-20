# utils.py
from flask import current_app
import requests
from itsdangerous import URLSafeTimedSerializer


def send_mailgun_message(to, subject, text, html=None):
    MAILGUN_DOMAIN = current_app.config.get("MAILGUN_DOMAIN")
    MAILGUN_API_KEY = current_app.config.get("MAILGUN_API_KEY")
    MAILGUN_FROM_EMAIL = current_app.config.get(
        "MAILGUN_FROM_EMAIL", f"Syvrona Support <mailgun@{MAILGUN_DOMAIN}>"
    )

    data = {
        "from": MAILGUN_FROM_EMAIL,
        "to": to,
        "subject": subject,
        "text": text,
    }
    if html:
        data["html"] = html
    return requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data=data,
    )


def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps(email, salt=current_app.config["SECURITY_PASSWORD_SALT"])


def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        email = serializer.loads(
            token,
            salt=current_app.config["SECURITY_PASSWORD_SALT"],
            max_age=expiration
        )
    except Exception:
        return False
    return email
