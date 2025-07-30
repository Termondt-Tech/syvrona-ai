import logging
from datetime import datetime
from flask import current_app, url_for, render_template, flash, redirect
from werkzeug.security import generate_password_hash
from app.feature_flags import get_feature_config, is_feature_enabled
from app.models import db, User
from app.utils import (
    generate_confirmation_token,
    send_mailgun_message,
)
import stripe

logger = logging.getLogger(__name__)


class SignupHandler:
    def __init__(self, email, name, password, plan, confirm_password):
        self.email = email
        self.name = name
        self.password = password
        self.plan = plan
        self.confirm_password = confirm_password
        self.new_user = None

    def validate(self):
        # All fields present
        if not all([self.email, self.name, self.password, self.confirm_password]):
            return "All fields are required."
        # Passwords match
        if self.password != self.confirm_password:
            return "Passwords do not match."
        # Email not already used
        if User.query.filter_by(email=self.email).first():
            return "Email address already exists."
        return None

    def create_user(self):
        self.new_user = User(
            email=self.email,
            name=self.name,
            password=generate_password_hash(
                self.password, method="pbkdf2", salt_length=16
            ),
        )
        db.session.add(self.new_user)
        db.session.commit()
        logger.info(
            "New user created: user_id=%s",
            self.new_user.id,
        )
        logger.info(
            "User chose plan: user_id=%s plan=%s",
            self.new_user.id,
            self.plan,
        )

    def send_welcome_email(self):
        token = generate_confirmation_token(self.new_user.email)
        confirm_url = url_for("auth.confirm_email", token=token, _external=True)
        free_trial_enabled = is_feature_enabled("FREE_TRIAL_ENABLED")
        free_trial_days = get_feature_config("FREE_TRIAL_DAYS", 0)
        subject = "Welcome to Syvrona – Please Confirm Your Email"
        text_body = render_template(
            "email/welcome_confirm.txt",
            user=self.new_user,
            confirm_url=confirm_url,
            free_trial_enabled=free_trial_enabled,
            free_trial_days=free_trial_days,
        )
        html_body = render_template(
            "email/welcome_confirm.html",
            user=self.new_user,
            confirm_url=confirm_url,
            free_trial_enabled=free_trial_enabled,
            free_trial_days=free_trial_days,
        )
        send_mailgun_message(
            to=self.new_user.email, subject=subject, text=text_body, html=html_body
        )

    def create_stripe_customer(self):
        try:
            customer = stripe.Customer.create(
                email=self.new_user.email,
                name=self.new_user.name,
                metadata={"user_id": self.new_user.id},
            )
            self.new_user.stripe_customer_id = customer.id
            self.new_user.last_login = datetime.now()
            db.session.commit()
            logger.info(
                "Stripe customer created: customer_id=%s user_id=%s",
                customer.id,
                self.new_user.id,
            )
        except Exception as e:
            logger.error(
                "Stripe customer creation error: user_id=%s error=%s",
                self.new_user.id,
                e,
            )
            flash(
                "There was an error creating your account. Please contact support.",
                "error",
            )
            raise

    def handle_subscription(self):
        price_ids = current_app.config.get("STRIPE_PRICE_IDS", {})
        if self.plan in price_ids:
            price_id = price_ids[self.plan]
            free_trial_enabled = is_feature_enabled("FREE_TRIAL_ENABLED")
            free_trial_days = get_feature_config("FREE_TRIAL_DAYS", 0)
            subscription_data = {}
            if free_trial_enabled and free_trial_days > 0:
                subscription_data["trial_period_days"] = free_trial_days

            try:
                session = stripe.checkout.Session.create(
                    customer=self.new_user.stripe_customer_id,
                    payment_method_types=["card"],
                    line_items=[{"price": price_id, "quantity": 1}],
                    mode="subscription",
                    subscription_data=subscription_data,
                    allow_promotion_codes=False,
                    success_url=url_for("auth.dashboard_view", _external=True)
                    + "?session_id={CHECKOUT_SESSION_ID}",
                    cancel_url=url_for("auth.dashboard_view", _external=True),
                )
            except Exception as e:
                logger.error(
                    "Stripe checkout session create error: user_id=%s error=%s",
                    self.new_user.id,
                    e,
                )
                flash(
                    "There was an error creating your subscription. "
                    "Please contact support.",
                    "error",
                )
                raise

            return redirect(session.url)
        else:
            # Free plan
            self.new_user.subscription_status = "active"
            self.new_user.subscription_plan = "free"
            self.new_user.subscription_start = datetime.now()
            db.session.commit()
            flash("Signup successful. You are now logged in.", "success")
            return redirect(url_for("auth.profile"))

    def process(self):
        # Validate input (return message if not valid)
        error = self.validate()
        if error:
            flash(error, "error")
            return redirect(url_for("auth.signup"))
        # Create user
        self.create_user()
        # Send welcome/confirm email
        self.send_welcome_email()
        # Create Stripe customer
        self.create_stripe_customer()
        # Log user in (in route)
        # Handle subscription and redirect
        return self.handle_subscription()
