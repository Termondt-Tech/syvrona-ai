# admin_routes.py
from datetime import datetime, timezone
import logging
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request
from sqlalchemy import desc, func
from app.constants import STRIPE_SUBSCRIPTION_STATUSES
from app.models import Conversation, Message, Notification, Ticket, TicketMessage, User
from app.decorators import admin_required
from flask_login import login_required, current_user
from app import db
from app.utils import send_staff_reply_alert

admin = Blueprint("admin", __name__, url_prefix="/admin")


def _utc_date(value):
    """An admin form's YYYY-MM-DD as midnight UTC; None when blank (D8)."""
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc) if value else None


logger = logging.getLogger(__name__)


@admin.route("/users")
@login_required
@admin_required
def user_list():

    sort = request.args.get("sort", "created_at")
    direction = request.args.get("direction", "desc")
    per_page = request.args.get("per_page", 25, type=int)
    page = request.args.get("page", 1, type=int)

    filter_admin = request.args.get("admin", "")
    filter_active = request.args.get("active", "")
    filter_subscription = request.args.get("subscription_status", "")

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
    if filter_subscription:
        query = query.filter(User.subscription_status == filter_subscription)

    # --- Sort handling ---
    if sort in ("messages_sent", "messages_received"):
        role = "user" if sort == "messages_sent" else "assistant"
        msg_count_subq = (
            db.session.query(
                Conversation.user_id.label("uid"),
                func.count(Message.id).label("msg_count"),
            )
            .join(Message, Conversation.id == Message.conversation_id)
            .filter(Message.role == role)
            .group_by(Conversation.user_id)
            .subquery()
        )
        query = query.outerjoin(msg_count_subq, User.id == msg_count_subq.c.uid)
        sort_column = func.coalesce(msg_count_subq.c.msg_count, 0)
        if direction == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())
    else:
        sort_columns = {
            "created_at": User.created_at,
            "last_login": User.last_login,
        }
        sort_column = sort_columns.get(sort, User.created_at)
        if direction == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

    users_pagination = query.paginate(page=page, per_page=per_page)
    users = users_pagination.items

    # Efficient badge count fetch (for just visible users)
    user_ids = [u.id for u in users]
    user_msg_counts = dict(
        db.session.query(Conversation.user_id, func.count(Message.id))
        .join(Message, Conversation.id == Message.conversation_id)
        .filter(Conversation.user_id.in_(user_ids), Message.role == "user")
        .group_by(Conversation.user_id)
        .all()
    )
    ai_msg_counts = dict(
        db.session.query(Conversation.user_id, func.count(Message.id))
        .join(Message, Conversation.id == Message.conversation_id)
        .filter(Conversation.user_id.in_(user_ids), Message.role == "assistant")
        .group_by(Conversation.user_id)
        .all()
    )

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
        user_msg_counts=user_msg_counts,
        ai_msg_counts=ai_msg_counts,
    )


@admin.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = db.get_or_404(User, user_id)

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

    STRIPE_SUBSCRIPTION_STATUS_OPTIONS = [
        "active",
        "trialing",
        "canceled",
        "incomplete",
        "incomplete_expired",
        "past_due",
        "paused",
        "unpaid",
    ]

    user = db.get_or_404(User, user_id)

    # Core message and conversation counts
    message_count_user = (
        db.session.query(func.count(Message.id))
        .join(Conversation)
        .filter(Conversation.user_id == user.id, Message.role == "user")
        .scalar()
    )
    message_count_ai = (
        db.session.query(func.count(Message.id))
        .join(Conversation)
        .filter(Conversation.user_id == user.id, Message.role == "assistant")
        .scalar()
    )
    conversation_count = (
        db.session.query(func.count(Conversation.id))
        .filter(Conversation.user_id == user.id)
        .scalar()
    )

    # Most active day for user messages
    most_active = (
        db.session.query(
            func.date(Message.created_at), func.count(Message.id).label("msg_count")
        )
        .join(Conversation)
        .filter(Conversation.user_id == user.id, Message.role == "user")
        .group_by(func.date(Message.created_at))
        .order_by(desc("msg_count"))
        .first()
    )

    # Recent activity (last 7 days)
    from datetime import datetime, timedelta, UTC

    now = datetime.now(tz=UTC)
    seven_days_ago = now - timedelta(days=7)
    recent_user_msgs = (
        db.session.query(func.count(Message.id))
        .join(Conversation)
        .filter(
            Conversation.user_id == user.id,
            Message.role == "user",
            Message.created_at >= seven_days_ago,
        )
        .scalar()
    )
    recent_ai_msgs = (
        db.session.query(func.count(Message.id))
        .join(Conversation)
        .filter(
            Conversation.user_id == user.id,
            Message.role == "assistant",
            Message.created_at >= seven_days_ago,
        )
        .scalar()
    )

    # Top AI models used
    model_stats = (
        db.session.query(Message.model, func.count(Message.id))
        .join(Conversation)
        .filter(Conversation.user_id == user.id, Message.role == "assistant")
        .group_by(Message.model)
        .order_by(desc(func.count(Message.id)))
        .limit(3)
        .all()
    )

    # --- FIXED: Average messages per conversation ---
    msg_counts = (
        db.session.query(func.count(Message.id))
        .join(Conversation)
        .filter(Conversation.user_id == user.id)
        .group_by(Conversation.id)
        .all()
    )
    msg_counts = [c[0] for c in msg_counts]
    avg_msgs_per_convo = (
        round(sum(msg_counts) / len(msg_counts), 2) if msg_counts else 0
    )

    stats = {
        "message_count_user": message_count_user,
        "message_count_ai": message_count_ai,
        "conversation_count": conversation_count,
        "most_active": most_active,
        "recent_user_msgs": recent_user_msgs,
        "recent_ai_msgs": recent_ai_msgs,
        "model_stats": model_stats,
        "avg_msgs_per_convo": avg_msgs_per_convo,
    }

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
        elif "update_subscription" in request.form:
            user.subscription_status = request.form.get("subscription_status")
            user.subscription_plan = request.form.get("subscription_plan")
            # Handle dates safely; HTML5 returns ISO format
            start = request.form.get("subscription_start")
            end = request.form.get("subscription_end")
            user.subscription_start = _utc_date(start)
            user.subscription_end = _utc_date(end)
            db.session.commit()
            flash("Subscription details updated.", "success")

    return render_template(
        "admin/user_view.html",
        user=user,
        price_labels=PRICE_LABELS,
        subscription_status_options=STRIPE_SUBSCRIPTION_STATUS_OPTIONS,
        stats=stats,
    )


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

    ticket = db.get_or_404(Ticket, ticket_id)
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
    notification = db.get_or_404(Notification, notification_id)
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
