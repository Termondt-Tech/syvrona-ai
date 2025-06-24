# utils.py
from flask import current_app, render_template, url_for
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
            token, salt=current_app.config["SECURITY_PASSWORD_SALT"], max_age=expiration
        )
    except Exception:
        return False
    return email


def send_new_ticket_alert(ticket):
    link = url_for("admin.ticket_detail", ticket_id=ticket.id, _external=True)
    subject = f"[Syvrona Support] New Ticket Submitted: #{ticket.id} – {ticket.subject}"
    text = render_template("email/ticket_new_admin.txt", ticket=ticket, link=link)
    html = render_template("email/ticket_new_admin.html", ticket=ticket, link=link)
    send_mailgun_message("info@termondttech.com", subject, text, html)


def send_new_ticket_message_alert(ticket, msg):
    link = url_for("admin.ticket_detail", ticket_id=ticket.id, _external=True)
    subject = f"[Syvrona Support] New Reply on Ticket #{ticket.id}: {ticket.subject}"
    text = render_template(
        "email/ticket_message_admin.txt", ticket=ticket, msg=msg, link=link
    )
    html = render_template(
        "email/ticket_message_admin.html", ticket=ticket, msg=msg, link=link
    )
    send_mailgun_message("info@termondttech.com", subject, text, html)


def send_staff_reply_alert(ticket, msg):
    if not ticket.user or not ticket.user.email:
        return
    link = url_for("support.view_ticket", ticket_id=ticket.id, _external=True)
    subject = (
        f"Syvrona Support: Response to Your Ticket #{ticket.id} – {ticket.subject}"
    )
    text = render_template(
        "email/ticket_staff_reply.txt", ticket=ticket, msg=msg, link=link
    )
    html = render_template(
        "email/ticket_staff_reply.html", ticket=ticket, msg=msg, link=link
    )
    send_mailgun_message(ticket.user.email, subject, text, html)
