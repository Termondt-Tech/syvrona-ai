from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User
import logging
from . import db
import stripe
import os


# Map your internal plan codes to Stripe Price IDs
STRIPE_PRICE_IDS = {
    "pro_monthly": os.getenv("STRIPE_PRICE_ID_PRO_MONTHLY"),
    "pro_yearly": os.getenv("STRIPE_PRICE_ID_PRO_YEARLY"),
}

auth = Blueprint("auth", __name__)

logger = logging.getLogger(__name__)


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
    user.last_login = datetime.now()
    db.session.commit()

    login_user(user, remember=remember)
    flash("Login successful.", "success")
    return redirect(url_for("main.profile"))


@auth.route("/signup")
def signup():
    return render_template("signup.html")


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

    customer = stripe.Customer.create(
        email=new_user.email, name=new_user.name, metadata={"user_id": new_user.id}
    )
    new_user.stripe_customer_id = customer.id
    new_user.last_login = datetime.now()
    db.session.commit()
    flash("Thanks for signing up!", "success")
    login_user(new_user)  # log in the user after signup

    # If paid plan, create checkout session and redirect to Stripe
    if plan in STRIPE_PRICE_IDS:
        price_id = STRIPE_PRICE_IDS[plan]
        session = stripe.checkout.Session.create(
            customer=new_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            allow_promotion_codes=True,
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
