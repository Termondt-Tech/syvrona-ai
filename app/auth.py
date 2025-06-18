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
from flask_login import login_required, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from app.models import User
import logging
from . import db
import stripe
from app.feature_flags import is_feature_enabled, get_feature_config
from app.utils import send_mailgun_message


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
    return redirect(url_for("main.profile"))


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
    # code to validate and add user to database goes here
    email = request.form.get("email")
    name = request.form.get("name")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")

    if not email or not name or not password or not confirm_password:
        flash("All fields are required.", "error")
        return redirect(url_for("auth.signup"))
    elif password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("auth.signup"))

    plan = request.form.get("plan", "free")

    # if this returns a user, then the email already exists in database
    user = User.query.filter_by(email=email).first()

    if user:
        # if a user is found, we want to redirect back to signup page
        # so user can try again
        flash("Email address already exists", "error")
        return redirect(url_for("auth.signup"))

    # create a new user with the form data. Hash the password so the plaintext version
    # isn't saved.
    new_user = User(
        email=email,
        name=name,
        password=generate_password_hash(password, method="pbkdf2", salt_length=16),
    )

    # add the new user to the database
    db.session.add(new_user)
    db.session.commit()

    logger.info(f"New user created: {new_user.email}")

    customer = stripe.Customer.create(
        email=new_user.email, name=new_user.name, metadata={"user_id": new_user.id}
    )

    logger.info(f"Stripe customer created: {customer.id} for user: {new_user.email}")
    new_user.stripe_customer_id = customer.id
    new_user.last_login = datetime.now()
    db.session.commit()
    logger.info(f"User {new_user.email} Stripe customer ID saved.")
    flash("Thanks for signing up!", "success")
    login_user(new_user)  # log in the user after signup

    price_ids = current_app.config.get("STRIPE_PRICE_IDS", {})

    # If paid plan, create checkout session and redirect to Stripe
    if plan in price_ids:
        price_id = price_ids[plan]

        free_trial_enabled = is_feature_enabled("FREE_TRIAL_ENABLED")
        free_trial_days = get_feature_config("FREE_TRIAL_DAYS", 0)

        subscription_data = {}
        if free_trial_enabled and free_trial_days > 0:
            subscription_data["trial_period_days"] = free_trial_days

        session = stripe.checkout.Session.create(
            customer=new_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            subscription_data=subscription_data,
            allow_promotion_codes=False,
            success_url=url_for("main.profile", _external=True)
            + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=url_for("main.profile", _external=True),
        )
        return redirect(session.url)

    # If free plan, record subscription and redirect to profile
    new_user.subscription_status = "active"
    new_user.subscription_plan = "free"
    new_user.subscription_start = datetime.now()
    db.session.commit()

    flash("Signup successful. You are now logged in.", "success")
    return redirect(url_for("main.profile"))


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
            text = (
                f"To reset your password, visit the following link: {reset_url}\n\n"
                "If you didn't request this, ignore this email."
            )
            send_mailgun_message(user.email, subject, text)

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
