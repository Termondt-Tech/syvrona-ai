import logging
from flask import (
    Blueprint,
    flash,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    current_app,
)
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
@login_required
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
        # (No subscription info here, handled in the next block)

    if event["type"] in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        subscription = event["data"]["object"]
        logger.info(f"Processing subscription event: {subscription}")
        stripe_customer_id = subscription["customer"]

        logger.info(f"Stripe event for customer: {stripe_customer_id}")

        user = User.query.filter_by(stripe_customer_id=stripe_customer_id).first()
        if user:
            logger.info(
                f"User found: id={user.id}, email={user.email}, "
                f"old status={user.subscription_status}"
            )
            user.subscription_status = subscription["status"]  # e.g., "active"

            # Get subscription item data safely
            items = subscription.get("items", {}).get("data", [])
            if items:
                item = items[0]
                user.subscription_plan = item["price"]["id"]
                user.subscription_start = datetime.fromtimestamp(
                    item["current_period_start"]
                )
                # For canceled, prefer ended_at if present, otherwise fall back
                if subscription["status"] == "canceled":
                    ended_at = subscription.get("ended_at")
                    if ended_at:
                        user.subscription_end = datetime.fromtimestamp(ended_at)
                    else:
                        user.subscription_end = datetime.fromtimestamp(
                            item["current_period_end"]
                        )
                else:
                    user.subscription_end = datetime.fromtimestamp(
                        item["current_period_end"]
                    )

            else:
                # If no items present, clear subscription plan and dates
                user.subscription_plan = None
                user.subscription_start = None
                user.subscription_end = None

            db.session.commit()
            logger.info(
                (
                    f"Updated user id={user.id}: "
                    f"new status={user.subscription_status}, "
                    f"plan={user.subscription_plan}"
                )
            )

        else:
            logger.warning(
                f"No user found for Stripe customer ID: {stripe_customer_id}"
            )

    return "", 200


@billing.route("/manage-subscription")
@login_required
def manage_subscription():
    session = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
        return_url=url_for("main.profile", _external=True),
    )
    return redirect(session.url)


@billing.route("/subscribe", methods=["GET", "POST"])
@login_required
def subscribe():
    if request.method == "POST":
        plan = request.form.get("plan")
        user = db.session.get(User, current_user.id)
        price_ids = current_app.config.get("STRIPE_PRICE_IDS", {})

        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email, name=user.name, metadata={"user_id": user.id}
            )
            user.stripe_customer_id = customer.id
            db.session.commit()

        if plan in price_ids:
            price_id = price_ids[plan]
            session = stripe.checkout.Session.create(
                customer=user.stripe_customer_id,
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                allow_promotion_codes=False,
                success_url=url_for("main.profile", _external=True)
                + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=url_for("main.profile", _external=True),
            )
            flash("Successfully subscribed.", "success")
            return redirect(session.url)
    else:
        return render_template("subscribe.html")
