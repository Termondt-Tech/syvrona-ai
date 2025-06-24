# app/routes/support.py
from datetime import UTC, datetime
from flask import Blueprint, abort, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Ticket, TicketMessage, db
from app.utils import send_new_ticket_alert, send_new_ticket_message_alert

support = Blueprint("support", __name__)


@support.route("/support")
@login_required
def list_tickets():
    tickets = (
        Ticket.query.filter_by(user_id=current_user.id)
        .order_by(Ticket.last_updated.desc())
        .all()
    )
    return render_template("support/list_tickets.html", tickets=tickets)


@support.route("/support/<int:ticket_id>", methods=["GET", "POST"])
@login_required
def view_ticket(ticket_id):

    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.user_id != current_user.id and not getattr(
        current_user, "is_staff", False
    ):
        abort(403)
    if request.method == "POST" and ticket.status != "closed":
        body = request.form.get("message", "").strip()
        if not body:
            flash("Message cannot be empty.", "error")
        else:
            msg = TicketMessage(
                ticket_id=ticket.id,
                sender_id=current_user.id,
                sender_type="user",  # or "admin" if staff
                body=body,
            )
            db.session.add(msg)
            ticket.last_updated = datetime.now(tz=UTC)
            db.session.commit()
            # Optionally send alert to staff
            send_new_ticket_message_alert(ticket, msg)
            flash("Reply posted.", "success")
            return redirect(url_for("support.view_ticket", ticket_id=ticket.id))
    return render_template("support/view_ticket.html", ticket=ticket)


@support.route("/support/new", methods=["GET", "POST"])
@login_required
def submit_ticket():
    if request.method == "POST":
        type = request.form.get("type")
        subject = request.form.get("subject")
        message = request.form.get("message")
        if not subject or not message:
            flash("Subject and message are required.", "error")
            return render_template("support/new_ticket.html")
        # Create ticket
        ticket = Ticket(user_id=current_user.id, type=type, subject=subject)
        db.session.add(ticket)
        db.session.commit()
        # Add initial message
        ticket_msg = TicketMessage(
            ticket_id=ticket.id,
            sender_id=current_user.id,
            sender_type="user",
            body=message,
        )
        db.session.add(ticket_msg)
        db.session.commit()
        # Optionally send alert to staff
        send_new_ticket_alert(ticket)
        flash("Ticket submitted! Our team will get back to you soon.", "success")
        return redirect(url_for("support.list_tickets"))
    return render_template("support/new_ticket.html")
