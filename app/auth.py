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
from app.handler.signup_handler import SignupHandler
from app.models import User
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
    honeypot = request.form.get('middle_name', '')

    if honeypot:
        # If the honeypot field is filled, it's likely a bot submission
        logger.warning("Honeypot field filled—possible bot: %r", request.form)
        return redirect(url_for("auth.login"))

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
        flash("Login not permitted. Please check your login details.", "error")
        # if the user doesn't exist or password is wrong, reload the page
        return redirect(url_for("auth.login"))

    # if the above check passes, then we know the user has the right credentials

    # ✅ Update last_login timestamp
    user.last_login = datetime.now(tz=UTC)
    db.session.commit()

    login_user(user, remember=remember)
    flash("Login successful.", "success")
    return redirect(url_for("auth.profile"))


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
    honeypot = request.form.get('middle_name', '')
    if honeypot:
        # If the honeypot field is filled, it's likely a bot submission
        logger.warning("Honeypot field filled—possible bot: %r", request.form)
        return redirect(url_for("auth.signup"))

    if not hcaptcha.verify():
        flash("Captcha failed. Please try again.", "error")
        return redirect(url_for("auth.signup"))

    handler = SignupHandler(
        email=request.form.get("email"),
        name=request.form.get("name"),
        password=request.form.get("password"),
        plan=request.form.get("plan", "free"),
        confirm_password=request.form.get("confirm_password"),
    )
    response = handler.process()
    if handler.new_user:
        login_user(handler.new_user)
    return response


@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        logger.info("Password reset requested.")
        email = request.form["email"]
        user = User.query.filter_by(email=email).first()
        if user:
            logger.info(f"Password reset link requested for user: {user.email}")
            token = generate_reset_token(user.email)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            # Send reset email
            subject = "Syvrona Password Reset"
            text = render_template("email/password_reset.txt", reset_url=reset_url)
            html = render_template("email/password_reset.html", reset_url=reset_url)
            send_mailgun_message(user.email, subject, text, html=html)
            flash("A password reset link has been sent to your email.", "info")
        else:
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
                flash("Email address already in use.", "warning")
                return redirect(url_for("auth.profile"))

            logger.info(
                f"Updating email for user: {user.get_id()} "
                f"from {user.email} to {email}"
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
