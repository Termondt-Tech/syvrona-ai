# utils.py
from flask import current_app, render_template, url_for
import requests
from itsdangerous import URLSafeTimedSerializer
import logging

logger = logging.getLogger(__name__)


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


def create_ticket_reply_notification(ticket, msg):
    from app import db
    from app.models import Notification

    if not ticket.user:
        return

    notification = Notification(
        sent_by=msg.sender_id,
        for_user_id=ticket.user_id,
        ticket_id=ticket.id,
        title=f"Support replied to your ticket #{ticket.id}",
        body=msg.body[:240],
        type="ticket_reply",
    )
    db.session.add(notification)
    db.session.commit()


def send_staff_reply_alert(ticket, msg):
    create_ticket_reply_notification(ticket, msg)
    if not ticket.user or not ticket.user.email:
        logger.info(
            "No user or user has no email. Skipping email for ticket %r", ticket.id
        )
        return

    prefs = (ticket.user.preferences or {}).get("email_notifications", {})
    logger.info("User %r email notification prefs: %r", ticket.user.id, prefs)
    ticket_reply_pref = prefs.get("ticket_reply", True)
    logger.info("User %r ticket_reply setting: %r", ticket.user.id, ticket_reply_pref)

    if not ticket_reply_pref:
        logger.info(
            "User %r has opted out of ticket reply emails. No email sent for ticket %r",
            ticket.user.id,
            ticket.id,
        )
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
