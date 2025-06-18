# utils.py
from flask import current_app
import requests


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
