from datetime import datetime, UTC
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    current_app,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from app.constants import PRICE_LABELS
from app.services.signup import SignupHandler
from app.models import (
    Conversation,
    Message,
    Notification,
    NotificationRead,
    Prompt,
    PromptChain,
    Tag,
    Ticket,
    User,
    message_tags,
    prompt_tags,
    chain_tags,
)
import logging
from app import hcaptcha
from . import db
from app.feature_flags import is_feature_enabled, get_feature_config
from app.utils import confirm_token, generate_confirmation_token, send_mailgun_message

auth = Blueprint("auth", __name__)

logger = logging.getLogger(__name__)


def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps(email, salt=current_app.config["SECURITY_PASSWORD_SALT"])


def confirm_reset_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        email = serializer.loads(
            token, salt=current_app.config["SECURITY_PASSWORD_SALT"], max_age=expiration
        )
    except (SignatureExpired, BadSignature):
        return None
    return email


@auth.route("/login")
def login():
    try:
        return render_template("login.html")
    except Exception as e:
        logging.error("Error rendering template: %s", e)
        return "An error occurred while rendering the template."


@auth.route("/login", methods=["POST"])
def login_post():

    # login code goes here
    email = request.form.get("email")
    password = request.form.get("password")
    remember = True if request.form.get("remember") else False
    honeypot = request.form.get("middle_name", "")

    if honeypot:
        # If the honeypot field is filled, it's likely a bot submission
        logger.warning(
            "Honeypot field filled—possible bot: ip=%s",
            request.remote_addr,
        )

        return redirect(url_for("auth.login"))

    if current_app.config.get("HCAPTCHA_ENABLED", False):
        if not hcaptcha.verify():
            flash("Captcha failed. Please try again.", "error")
            return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()

    # check if the user actually exists
    # take the user-supplied password, hash it,
    # and compare it to the hashed password in the database
    if (
        not user
        or not check_password_hash(user.password, password)
        or not user.is_active
    ):
        logger.info(
            "Failed login attempt: ip=%s exists=%s active=%s",
            request.remote_addr,
            bool(user),
            user.is_active if user else None,
        )
        flash("Login not permitted. Please check your login details.", "error")
        # if the user doesn't exist or password is wrong, reload the page
        return redirect(url_for("auth.login"))

    # if the above check passes, then we know the user has the right credentials
    logger.info(
        "User logged in: user_id=%s ip=%s",
        user.id,
        request.remote_addr,
    )

    # ✅ Update last_login timestamp
    user.last_login = datetime.now(tz=UTC)
    db.session.commit()

    login_user(user, remember=remember)
    return redirect(url_for("auth.dashboard_view"))


@auth.route("/signup")
def signup():
    free_trial_enabled = is_feature_enabled("FREE_TRIAL_ENABLED")
    free_trial_days = get_feature_config("FREE_TRIAL_DAYS", 7)
    return render_template(
        "signup.html",
        free_trial_enabled=free_trial_enabled,
        free_trial_days=free_trial_days,
    )


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth.route("/signup", methods=["POST"])
def signup_post():
    honeypot = request.form.get("middle_name", "")
    if honeypot:
        # If the honeypot field is filled, it's likely a bot submission
        logger.warning(
            "Signup honeypot filled—possible bot: remote_addr=%s",
            request.remote_addr,
        )

        return redirect(url_for("auth.signup"))

    if current_app.config.get("HCAPTCHA_ENABLED", False):
        if not hcaptcha.verify():
            logger.info(
                "Signup captcha failed: ip=%s",
                request.remote_addr,
            )
            flash("Captcha failed. Please try again.", "error")
            return redirect(url_for("auth.login"))

    handler = SignupHandler(
        email=request.form.get("email"),
        name=request.form.get("name"),
        password=request.form.get("password"),
        plan=request.form.get("plan", "free"),
        confirm_password=request.form.get("confirm_password"),
    )
    response = handler.process()
    if handler.new_user:
        logger.info(
            "New user signed up: user_id=%s ip=%s",
            handler.new_user.id,
            request.remote_addr,
        )
        login_user(handler.new_user)
    return response


@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        logger.info("Password reset requested.")
        email = request.form["email"]
        user = User.query.filter_by(email=email).first()
        if user:
            logger.info("Password reset requested: user_id=%s", user.id)
            token = generate_reset_token(user.email)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            # Send reset email
            subject = "Syvrona Password Reset"
            text = render_template("email/password_reset.txt", reset_url=reset_url)
            html = render_template("email/password_reset.html", reset_url=reset_url)
            send_mailgun_message(user.email, subject, text, html=html)
            flash("A password reset link has been sent to your email.", "info")
        else:
            logger.info("Password reset requested for non-existent user")
            # Avoid leaking info; always show same message.
            flash("A password reset link has been sent to your email.", "info")
        return redirect(url_for("auth.login"))
    return render_template("forgot_password.html")


@auth.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = confirm_reset_token(token)
    if not email:
        flash("The password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return render_template("reset_password.html", token=token)

        user = User.query.filter_by(email=email).first()
        if user:
            user.password = generate_password_hash(
                password, method="pbkdf2", salt_length=16
            )
            db.session.commit()
            logger.info(f"Password reset successful for user: {user.email}")
            flash("Your password has been updated. Please log in.", "success")
            return redirect(url_for("auth.login"))
        else:
            logger.warning(f"Password reset attempted for non-existent user: {email}")
            flash("User not found.", "danger")
            return redirect(url_for("auth.forgot_password"))

    return render_template("reset_password.html", token=token)


@auth.route("/confirm-email/<token>")
def confirm_email(token):
    email = confirm_token(token)
    if not email:
        flash("The confirmation link is invalid or has expired.", "danger")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first_or_404()
    if user.verified:
        flash("Account already confirmed. Please login.", "success")
    else:
        user.verified = True
        db.session.commit()
        flash("You have confirmed your account. Thanks!", "success")
    return redirect(url_for("auth.login"))


@auth.route("/resend_verification", methods=["GET"])
@login_required
def resend_verification():
    user = current_user
    if user.verified:
        flash("Your email is already verified.", "success")
        return redirect(url_for("auth.profile"))

    token = generate_confirmation_token(user.email)
    confirm_url = url_for("auth.confirm_email", token=token, _external=True)

    subject = "Syvrona – Please Confirm Your Email"
    text_body = render_template(
        "email/confirm_email.txt",
        user=user,
        confirm_url=confirm_url,
    )
    html_body = render_template(
        "email/confirm_email.html",
        user=user,
        confirm_url=confirm_url,
    )
    send_mailgun_message(to=user.email, subject=subject, text=text_body, html=html_body)

    flash("Verification email sent. Please check your inbox.", "success")
    return redirect(url_for("auth.profile"))


@auth.route("/profile")
@login_required
def profile():

    user = db.session.get(User, current_user.id)

    logger.info(f"Rendering preferences for user: {user.preferences}")

    return render_template("profile.html", user=user, price_labels=PRICE_LABELS)


@auth.route("/profile/update", methods=["POST"])
@login_required
def update_profile():
    try:
        name = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        user = current_user

        if not name or not email:
            flash("Name and email are required.", "warning")
            return redirect(url_for("auth.profile"))
        if password and password != confirm_password:
            flash("Passwords do not match.", "warning")
            return redirect(url_for("auth.profile"))

        email_changed = user.email != email
        user.name = name

        if email_changed:
            # Check if the new email is already in use by someone else
            existing_user = db.session.query(User).filter_by(email=email).first()
            if existing_user:
                logger.info(
                    "Attempted email update to existing email: user_id=%s",
                    user.get_id(),
                )
                flash("Email address already in use.", "warning")
                return redirect(url_for("auth.profile"))

            logger.info(
                "User changed email: user_id=%s",
                user.get_id(),
            )

            user.email = email
            user.verified = False  # Mark as unverified
            db.session.commit()

            # Send confirmation email to new address
            from app.utils import send_mailgun_message, generate_confirmation_token

            confirm_token = generate_confirmation_token(email)
            confirm_url = url_for(
                "auth.confirm_email", token=confirm_token, _external=True
            )
            subject = "Confirm Your New Email Address"
            text_body = render_template(
                "email/confirm_email.txt",
                user=user,
                confirm_url=confirm_url,
            )
            html_body = render_template(
                "email/confirm_email.html",
                user=user,
                confirm_url=confirm_url,
            )
            send_mailgun_message(
                to=email,
                subject=subject,
                text=text_body,
                html=html_body,
            )
            flash(
                "Profile updated. Please check your new email to confirm your address.",
                "info",
            )
        else:
            if password:
                hashed_password = generate_password_hash(
                    password, method="pbkdf2", salt_length=16
                )
                user.set_password(hashed_password)
            db.session.commit()
            flash("Profile updated successfully!", "success")

        return redirect(url_for("auth.profile"))
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        flash("Error updating profile.", "error")
        return redirect(url_for("auth.profile"))


@auth.route("/profile/preferences", methods=["POST"])
@login_required
def update_preferences():
    prefs = dict(current_user.preferences) if current_user.preferences else {}

    # Always create a new dict to avoid reference issues
    email_prefs = {}

    email_prefs["ticket_reply"] = "email_ticket_reply" in request.form
    email_prefs["system"] = "email_system" in request.form
    email_prefs["marketing"] = "email_marketing" in request.form

    prefs["email_notifications"] = email_prefs

    current_user.preferences = prefs
    logger.info(f"Saving preferences: {prefs}")
    db.session.commit()

    flash("Your preferences have been updated.", "success")
    return redirect(url_for("auth.profile"))


@auth.route("/notifications")
@login_required
def notifications():
    # --- Query Params ---
    filter_type = request.args.get("filter", "all")  # all, unread, read, archived
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    # --- All notifications for user (broadcast and targeted) ---
    notifications_query = Notification.query.filter(
        (Notification.for_user_id.is_(None))
        | (Notification.for_user_id == current_user.id)
    ).order_by(Notification.created_at.desc())

    # --- Read & archived IDs ---
    read_rows = NotificationRead.query.filter_by(user_id=current_user.id).all()
    read_ids = {
        nr.notification_id for nr in read_rows if not getattr(nr, "archived", False)
    }
    archived_ids = {
        nr.notification_id for nr in read_rows if getattr(nr, "archived", False)
    }

    # --- Filtering ---
    if filter_type == "unread":
        notifications_query = notifications_query.filter(
            ~Notification.id.in_(read_ids), ~Notification.id.in_(archived_ids)
        )
    elif filter_type == "read":
        notifications_query = notifications_query.filter(
            Notification.id.in_(read_ids), ~Notification.id.in_(archived_ids)
        )
    elif filter_type == "archived":
        notifications_query = notifications_query.filter(
            Notification.id.in_(archived_ids)
        )
    else:  # "all"
        notifications_query = notifications_query.filter(
            ~Notification.id.in_(archived_ids)
        )

    notifications_pagination = notifications_query.paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template(
        "notifications.html",
        notifications=notifications_pagination.items,
        read_ids=read_ids,
        archived_ids=archived_ids,
        filter_type=filter_type,
        notifications_pagination=notifications_pagination,
        per_page=per_page,
    )


@auth.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):

    # Don't duplicate rows (enforce unique constraint)
    existing = NotificationRead.query.filter_by(
        notification_id=notification_id, user_id=current_user.id
    ).first()
    if not existing:
        nr = NotificationRead(notification_id=notification_id, user_id=current_user.id)
        db.session.add(nr)
        db.session.commit()
    return redirect(url_for("auth.notifications"))


@auth.route("/notifications/<int:notification_id>/archive", methods=["POST"])
@login_required
def archive_notification(notification_id):
    from app.models import NotificationRead, db

    nr = NotificationRead.query.filter_by(
        notification_id=notification_id, user_id=current_user.id
    ).first()
    if nr:
        nr.archived = True
    else:
        nr = NotificationRead(
            notification_id=notification_id,
            user_id=current_user.id,
            archived=True,
        )
        db.session.add(nr)
    db.session.commit()
    flash("Notification archived.", "success")
    return redirect(url_for("auth.notifications"))


@auth.route("/notifications/archive_all", methods=["POST"])
@login_required
def archive_all_notifications():
    from app.models import Notification, NotificationRead, db

    # Find all active (not archived) notifications for the user
    # (Consider only those visible in the main list)
    notif_ids = [
        n.id
        for n in Notification.query.filter(
            (Notification.for_user_id.is_(None))
            | (Notification.for_user_id == current_user.id)
        ).all()
    ]
    existing = NotificationRead.query.filter(
        NotificationRead.user_id == current_user.id,
        NotificationRead.notification_id.in_(notif_ids),
    ).all()
    existing_ids = {nr.notification_id for nr in existing}
    # Archive existing
    for nr in existing:
        nr.archived = True
    # Create new NotificationRead rows for any un-archived notifications
    for nid in notif_ids:
        if nid not in existing_ids:
            db.session.add(
                NotificationRead(
                    notification_id=nid, user_id=current_user.id, archived=True
                )
            )
    db.session.commit()
    flash("All notifications archived.", "success")
    return redirect(url_for("auth.notifications"))


@auth.route("/dashboard")
@login_required
def dashboard_view():
    # Last 5 conversations
    recent_convos = (
        Conversation.query.filter_by(user_id=current_user.id)
        .order_by(Conversation.created_at.desc())
        .limit(5)
        .all()
    )

    # Unread notifications
    notifications = (
        Notification.query.filter(
            (Notification.for_user_id.is_(None))
            | (Notification.for_user_id == current_user.id)
        )
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )
    read_ids = {
        nr.notification_id
        for nr in NotificationRead.query.filter_by(user_id=current_user.id)
    }
    unread_notifications_list = [n for n in notifications if n.id not in read_ids]

    # Open tickets
    open_tickets = (
        Ticket.query.filter(
            Ticket.user_id == current_user.id,
            Ticket.status.in_(["open", "pending"]),
        )
        .order_by(Ticket.created_at.desc())
        .limit(3)
        .all()
    )

    # Recent prompts (last 5)
    recent_prompts = (
        Prompt.query.filter_by(user_id=current_user.id)
        .order_by(Prompt.updated_at.desc())
        .limit(5)
        .all()
    )

    # Recent chains (last 5)
    recent_chains = (
        PromptChain.query.filter_by(user_id=current_user.id)
        .order_by(PromptChain.updated_at.desc())
        .limit(5)
        .all()
    )

    # Tags recently used in conversations/messages
    recent_convo_tags = (
        db.session.query(Tag, db.func.count(Message.id).label("msg_count"))
        .join(message_tags, Tag.id == message_tags.c.tag_id)
        .join(Message, Message.id == message_tags.c.message_id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(Conversation.user_id == current_user.id)
        .group_by(Tag.id)
        .order_by(db.func.max(Message.created_at).desc())
        .limit(5)
        .all()
    )

    # Tags recently used on prompts
    recent_prompt_tags = (
        db.session.query(Tag, db.func.count(Prompt.id).label("prompt_count"))
        .join(prompt_tags, Tag.id == prompt_tags.c.tag_id)
        .join(Prompt, Prompt.id == prompt_tags.c.prompt_id)
        .filter(Prompt.user_id == current_user.id)
        .group_by(Tag.id)
        .order_by(db.func.max(Prompt.updated_at).desc())
        .limit(5)
        .all()
    )

    # Tags recently used on chains
    recent_chain_tags = (
        db.session.query(Tag, db.func.count(PromptChain.id).label("chain_count"))
        .join(chain_tags, Tag.id == chain_tags.c.tag_id)
        .join(PromptChain, PromptChain.id == chain_tags.c.chain_id)
        .filter(PromptChain.user_id == current_user.id)
        .group_by(Tag.id)
        .order_by(db.func.max(PromptChain.updated_at).desc())
        .limit(5)
        .all()
    )

    # Total tags (dedupe)
    tags_count = (
        db.session.query(db.func.count(db.distinct(Tag.id)))
        .outerjoin(message_tags, Tag.id == message_tags.c.tag_id)
        .outerjoin(prompt_tags, Tag.id == prompt_tags.c.tag_id)
        .outerjoin(chain_tags, Tag.id == chain_tags.c.tag_id)
        .filter((Tag.user_id == current_user.id))
        .scalar()
    )

    subscription_status = getattr(current_user, "subscription_status", None)
    subscription_plan = getattr(current_user, "subscription_plan", None)

    return render_template(
        "dashboard.html",
        recent_convos=recent_convos,
        notifications=notifications,
        read_ids=read_ids,
        open_tickets=open_tickets,
        subscription_status=subscription_status,
        subscription_plan=subscription_plan,
        unread_notifications_list=unread_notifications_list,
        price_labels=PRICE_LABELS,
        recent_prompts=recent_prompts,
        recent_chains=recent_chains,
        recent_convo_tags=recent_convo_tags,
        recent_prompt_tags=recent_prompt_tags,
        recent_chain_tags=recent_chain_tags,
        tags_count=tags_count,
    )


@auth.route("/notifications/<int:notification_id>")
@login_required
def notification_detail(notification_id):
    notification = db.get_or_404(Notification, notification_id)

    # Make sure user can only see their notifications (or broadcasts)
    if notification.for_user_id and notification.for_user_id != current_user.id:
        flash("You are not authorized to view this notification.", "error")
        return redirect(url_for("auth.notifications"))

    # Mark as read if not already
    nr = NotificationRead.query.filter_by(
        notification_id=notification.id, user_id=current_user.id
    ).first()
    if not nr:
        nr = NotificationRead(notification_id=notification.id, user_id=current_user.id)
        db.session.add(nr)
        db.session.commit()

    return render_template("notification_detail.html", notification=notification)
