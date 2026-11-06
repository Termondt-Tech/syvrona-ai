"""Billing: checkout redirect target (D2), price allowlist, UTC timestamps (D8)."""

import time
from datetime import UTC, datetime
from types import SimpleNamespace as NS

import pytest
import stripe

from app import db
from app.models import User

PRICE = "price_pro_monthly_test"


@pytest.fixture
def priced_app(app):
    app.config["STRIPE_PRICE_IDS"] = {"pro_monthly": PRICE, "pro_yearly": None}
    return app


@pytest.fixture
def stripe_calls(monkeypatch):
    calls = {}

    def customer_create(**kwargs):
        calls["customer"] = kwargs
        return NS(id="cus_test")

    def session_create(**kwargs):
        calls["session"] = kwargs
        return NS(url="https://checkout.example/session")

    monkeypatch.setattr(stripe.Customer, "create", customer_create)
    monkeypatch.setattr(stripe.checkout.Session, "create", session_create)
    return calls


def test_checkout_session_returns_to_the_profile_page(
    client, priced_app, subscriber, stripe_calls
):
    response = client.post("/create-checkout-session", json={"price_id": PRICE})
    assert response.status_code == 200
    assert response.get_json() == {"checkout_url": "https://checkout.example/session"}
    session = stripe_calls["session"]
    assert session["line_items"] == [{"price": PRICE, "quantity": 1}]
    assert session["success_url"].startswith("http://localhost/profile?session_id=")
    assert session["cancel_url"] == "http://localhost/profile"


def test_checkout_session_rejects_a_price_we_do_not_sell(
    client, priced_app, subscriber, stripe_calls
):
    response = client.post("/create-checkout-session", json={"price_id": "price_other"})
    assert response.status_code == 400
    assert "session" not in stripe_calls


def test_checkout_session_hides_stripe_errors(
    client, priced_app, subscriber, stripe_calls, monkeypatch
):
    def fail(**kwargs):
        raise stripe.InvalidRequestError("No such price: secret detail", "price")

    monkeypatch.setattr(stripe.checkout.Session, "create", fail)
    response = client.post("/create-checkout-session", json={"price_id": PRICE})
    assert response.status_code == 502
    assert "secret detail" not in response.get_data(as_text=True)


@pytest.fixture
def non_utc_host(monkeypatch):
    """Run as a host whose local zone is not UTC, as a laptop or droplet might be."""
    monkeypatch.setenv("TZ", "America/Chicago")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def subscription_event(customer, status="active", ended_at=None):
    return {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "customer": customer,
                "status": status,
                "ended_at": ended_at,
                "items": {
                    "data": [
                        {
                            "price": {"id": PRICE},
                            "current_period_start": 1_793_534_400,  # 2026-11-01T12:00Z
                            "current_period_end": 1_796_212_800,  # 2026-12-02T12:00Z
                        }
                    ]
                },
            }
        },
    }


def test_webhook_stores_subscription_dates_in_utc(
    client, create_user, monkeypatch, non_utc_host
):
    user = create_user(email="payer@example.com")
    user.stripe_customer_id = "cus_payer"
    db.session.commit()
    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        lambda payload, sig, secret: subscription_event("cus_payer"),
    )

    assert client.post("/stripe/webhook", data=b"{}").status_code == 200

    db.session.expire_all()
    user = db.session.get(User, user.id)
    assert user.subscription_status == "active"
    assert user.subscription_plan == PRICE
    # Columns are naive; the stored wall time must be UTC, not the host's zone.
    assert user.subscription_start.replace(tzinfo=UTC) == datetime(
        2026, 11, 1, 12, 0, tzinfo=UTC
    )
    assert user.subscription_end.replace(tzinfo=UTC) == datetime(
        2026, 12, 2, 12, 0, tzinfo=UTC
    )


def test_webhook_rejects_a_bad_signature(client, monkeypatch):
    monkeypatch.setenv(
        "STRIPE_WEBHOOK_SECRET", "whsec_test_not_a_secret"
    )  # gitleaks:allow
    response = client.post(
        "/stripe/webhook",
        data=b'{"type": "customer.subscription.updated"}',
        headers={"Stripe-Signature": "t=1,v1=deadbeef"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid signature"}
