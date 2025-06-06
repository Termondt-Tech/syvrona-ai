from unittest.mock import patch


def test_app_exists(app):
    assert app is not None


def test_app_is_testing(app):
    assert app.config["TESTING"]


def test_database_initialization(client):
    response = client.get("/")
    assert response.status_code == 200


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_readyz(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json == {"status": "ready"}


def test_homepage(client):
    """Test homepage loads for unauthenticated users."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Syvrona" in response.data  # Change as needed


def test_register_new_user(client):
    with patch("app.auth.stripe.Customer.create") as mock_stripe_customer:
        mock_stripe_customer.return_value = type(
            "Customer", (), {"id": "cus_test_123"}
        )()
        response = client.post(
            "/signup",
            data={
                "email": "newuser@example.com",
                "name": "Test User",
                "password": "StrongPass123",
                "plan": "free",
                "confirm_password": "StrongPass123",
            },
            follow_redirects=True,
        )
        assert (
            b"Signup successful" in response.data
            or b"Thanks for signing up!" in response.data
        )


def test_signup_paid_plan_redirects_to_stripe(client):
    with patch("app.auth.stripe.Customer.create") as mock_stripe_customer, patch(
        "app.auth.stripe.checkout.Session.create"
    ) as mock_stripe_checkout:
        mock_stripe_customer.return_value = type(
            "Customer", (), {"id": "cus_paid_123"}
        )()
        mock_stripe_checkout.return_value = type(
            "Session", (), {"url": "http://stripe-session-url"}
        )()
        response = client.post(
            "/signup",
            data={
                "email": "paiduser@example.com",
                "name": "Test Paid",
                "password": "StrongPassword1!",
                "plan": "pro_monthly",  # <-- must match your config!
                "confirm_password": "StrongPassword1!",
            },
            follow_redirects=False,
        )
        assert response.status_code in (301, 302)
        assert response.headers["Location"] == "http://stripe-session-url"
