import logging
from flask import Blueprint, request, jsonify, redirect, url_for
from flask_login import current_user, login_required
import stripe
from . import db
from .models import User
from datetime import datetime
import os

logger = logging.getLogger(__name__)

stripe.api_key = os.getenv("STRIPE_API_KEY")

billing = Blueprint("billing", __name__)


@billing.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    # Ensure user is authenticated
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    price_id = data.get("price_id")
    if not price_id:
        return jsonify({"error": "Missing price_id"}), 400

    # Check if the user already has a Stripe customer
    if not current_user.stripe_customer_id:
        # Create Stripe customer in Stripe
        customer = stripe.Customer.create(
            email=current_user.email,
            name=current_user.name,
            metadata={"user_id": current_user.id},
        )
        current_user.stripe_customer_id = customer.id
        db.session.commit()
        stripe_customer_id = customer.id
    else:
        stripe_customer_id = current_user.stripe_customer_id

    try:
        checkout_session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            allow_promotion_codes=True,
            success_url=url_for("profile", _external=True)
            + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=url_for("profile", _external=True),
        )
        return jsonify({"checkout_url": checkout_session.url})
    except Exception as e:
        return jsonify(error=str(e)), 500


@billing.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    event = None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        return jsonify({"error": "Invalid signature"}), 400

    logger.info(f"Received Stripe event: {event['type']}")

    # Handle relevant Stripe event types
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        logger.info(f"checkout.session.completed: {session}")
        # You can fetch customer/subscription from session['customer']
        # Optionally fetch subscription object if needed

    if (
        event["type"] == "customer.subscription.created"
        or event["type"] == "customer.subscription.updated"
        or event["type"] == "customer.subscription.deleted"
    ):
        subscription = event["data"]["object"]
        logger.info(f"Processing subscription event: {subscription}")
        stripe_customer_id = subscription["customer"]
        user = User.query.filter_by(stripe_customer_id=stripe_customer_id).first()
        if user:
            logger.info(f"Updating user {user.id} subscription info")
            user.subscription_status = subscription["status"]  # e.g., "active"
            user.subscription_plan = subscription["items"]["data"][0]["price"]["id"]
            user.subscription_start = datetime.fromtimestamp(
                subscription["current_period_start"]
            )
            user.subscription_end = datetime.fromtimestamp(
                subscription["current_period_end"]
            )
            db.session.commit()

    return "", 200


@billing.route("/manage-subscription")
@login_required
def manage_subscription():
    session = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
        return_url=url_for("main.profile", _external=True),
    )
    return redirect(session.url)
