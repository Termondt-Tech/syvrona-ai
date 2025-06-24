# admin_routes.py
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.models import Ticket, TicketMessage, User
from app.decorators import admin_required
from flask_login import login_required, current_user
from app import db
from app.utils import send_staff_reply_alert

admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.route("/users")
@login_required
@admin_required
def user_list():
    # Supported sort columns, use dict to map query param to SQLAlchemy column
    sort_columns = {
        "created_at": User.created_at,
        "last_login": User.last_login,
    }
    sort = request.args.get("sort", "created_at")
    direction = request.args.get("direction", "desc")

    # Validate sort key
    sort_column = sort_columns.get(sort, User.created_at)
    if direction == "asc":
        users = User.query.order_by(sort_column.asc()).all()
    else:
        users = User.query.order_by(sort_column.desc()).all()

    return render_template("admin/user_list.html", users=users, sort=sort, direction=direction)


@admin.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You can't deactivate your own account.", "error")
        return redirect(url_for("admin.user_list"))

    user.is_active = not user.is_active
    db.session.commit()

    flash(
        f"User {user.email} is now {'active' if user.is_active else 'inactive'}.",
        "success",
    )
    return redirect(url_for("admin.user_list"))


# --- New: User Detail Route ---
@admin.route("/user/<int:user_id>", methods=["GET", "POST"])
def user_detail(user_id):

    PRICE_LABELS = {
        os.getenv("STRIPE_PRICE_ID_PRO_MONTHLY"): "Pro Monthly ($9.99/mo)",
        os.getenv("STRIPE_PRICE_ID_PRO_YEARLY"): "Pro Yearly ($99/year)",
    }

    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        if "deactivate" in request.form:
            if user.id == current_user.id:
                flash("You can't deactivate your own account.", "error")
            else:
                user.is_active = not user.is_active
                db.session.commit()
                flash(
                    f"User {'deactivated' if not user.is_active else 'activated'} "
                    "successfully.",
                    "success",
                )
        elif "delete" in request.form:
            if user.id == current_user.id:
                flash("You can't delete your own account.", "error")
            else:
                db.session.delete(user)
                db.session.commit()
                flash("User deleted successfully.", "success")
                return redirect(url_for("admin.user_list"))

    return render_template("admin/user_view.html", user=user, price_labels=PRICE_LABELS)


@admin.route("/tickets")
@login_required
@admin_required
def tickets():
    # Get filter params
    status = request.args.get("status", "")
    type_ = request.args.get("type", "")
    query = Ticket.query

    if status:
        query = query.filter(Ticket.status.ilike(status))
    if type_:
        query = query.filter(Ticket.type.ilike(type_))
    tickets = query.order_by(Ticket.last_updated.desc()).all()
    return render_template(
        "admin/ticket_list.html",
        tickets=tickets,
        filter_status=status,
        filter_type=type_,
    )


@admin.route("/tickets/<int:ticket_id>", methods=["GET", "POST"])
@login_required
@admin_required
def ticket_detail(ticket_id):
    from flask import request, redirect, url_for, flash
    from datetime import datetime, timezone

    ticket = Ticket.query.get_or_404(ticket_id)
    messages = ticket.messages  # Already ordered if you set order_by

    if request.method == "POST":
        # Handle status update
        if "set_status" in request.form:
            new_status = request.form.get("status")
            if new_status in ["open", "pending", "resolved", "closed"]:
                ticket.status = new_status
                ticket.last_updated = datetime.now(timezone.utc)
                db.session.commit()
                flash(f"Ticket status set to {new_status}.", "success")
                return redirect(url_for("admin.ticket_detail", ticket_id=ticket.id))

        # Handle staff reply
        elif ticket.status != "closed":
            body = request.form.get("message", "").strip()
            if not body:
                flash("Message cannot be empty.", "error")
            else:
                msg = TicketMessage(
                    ticket_id=ticket.id,
                    sender_id=current_user.id,
                    sender_type="admin",
                    body=body,
                )
                db.session.add(msg)
                ticket.last_updated = datetime.now(timezone.utc)
                db.session.commit()
                # Optionally send alert to user
                send_staff_reply_alert(ticket, msg)
                flash("Reply posted.", "success")
                return redirect(url_for("admin.ticket_detail", ticket_id=ticket.id))

    return render_template("admin/ticket_detail.html", ticket=ticket, messages=messages)
