# admin_routes.py
from datetime import datetime, timezone
import logging
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.constants import STRIPE_SUBSCRIPTION_STATUSES
from app.models import Notification, Ticket, TicketMessage, User
from app.decorators import admin_required
from flask_login import login_required, current_user
from app import db
from app.utils import send_staff_reply_alert

admin = Blueprint("admin", __name__, url_prefix="/admin")

logger = logging.getLogger(__name__)


@admin.route("/users")
@login_required
@admin_required
def user_list():
    sort_columns = {
        "created_at": User.created_at,
        "last_login": User.last_login,
    }
    sort = request.args.get("sort", "created_at")
    direction = request.args.get("direction", "desc")
    per_page = request.args.get("per_page", 25, type=int)
    page = request.args.get("page", 1, type=int)

    filter_admin = request.args.get("admin", "")  # "yes", "no", ""
    filter_active = request.args.get("active", "")  # "yes", "no", ""
    filter_subscription = request.args.get("subscription_status", "")  # e.g. "active"

    query = User.query

    # Filtering
    if filter_admin == "yes":
        query = query.filter(User.is_admin.is_(True))
    elif filter_admin == "no":
        query = query.filter(User.is_admin.is_(False))
    if filter_active == "yes":
        query = query.filter(User.is_active.is_(True))
    elif filter_active == "no":
        query = query.filter(User.is_active.is_(False))

    # Subscription status filtering
    if filter_subscription:
        query = query.filter(User.subscription_status == filter_subscription)

    sort_column = sort_columns.get(sort, User.created_at)
    if direction == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    users_pagination = query.paginate(page=page, per_page=per_page)
    users = users_pagination.items

    return render_template(
        "admin/user_list.html",
        users=users,
        users_pagination=users_pagination,
        sort=sort,
        direction=direction,
        per_page=per_page,
        filter_admin=filter_admin,
        filter_active=filter_active,
        filter_subscription=filter_subscription,
        subscription_statuses=STRIPE_SUBSCRIPTION_STATUSES,
    )


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


@admin.route("/notifications")
@login_required
@admin_required
def notification_list():
    # Sorting/filtering can be enhanced later
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    notif_type = request.args.get("type", "").strip()  # Empty string = all

    query = Notification.query
    if notif_type:
        query = query.filter(Notification.type == notif_type)

    notifications_pagination = query.order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=per_page
    )
    notifications = notifications_pagination.items

    users = {u.id: u for u in User.query.all()}
    return render_template(
        "admin/notification_list.html",
        notifications=notifications,
        users=users,
        notifications_pagination=notifications_pagination,
        notif_type=notif_type,
    )


@admin.route("/notifications/<int:notification_id>")
@login_required
@admin_required
def notification_detail(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    users = {u.id: u for u in User.query.all()}
    return render_template(
        "admin/notification_detail.html", notification=notification, users=users
    )


@admin.route("/notifications/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_notification():
    users = User.query.filter_by(is_active=True).order_by(User.email).all()
    formdata = {}

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        notif_type = request.form.get("type", "system")
        for_user_id = request.form.get("for_user_id")
        sent_by = current_user.id

        # Always save entered form values for repopulation
        formdata = {
            "title": title,
            "body": body,
            "type": notif_type,
            "for_user_id": for_user_id,
        }

        # (Validation logic as above...)
        error = None

        if not title or not body:
            error = "Title and message are required."

        if error:
            flash(error, "error")
        else:
            notification = Notification(
                title=title,
                body=body,
                type=notif_type,
                created_at=datetime.now(timezone.utc),
                sent_by=sent_by,
                for_user_id=int(for_user_id) if for_user_id else None,
            )
            db.session.add(notification)
            db.session.commit()
            flash("Notification created and sent.", "success")
            return redirect(url_for("admin.notification_list"))

    return render_template(
        "admin/create_notification.html", users=users, formdata=formdata
    )
