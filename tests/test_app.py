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
    with patch(
        "app.handler.signup_handler.send_mailgun_message"
    ) as mock_mailgun, patch(
        "app.handler.signup_handler.stripe.Customer.create"
    ) as mock_stripe_customer:
        mock_mailgun.return_value = None
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
    with patch(
        "app.handler.signup_handler.send_mailgun_message"
    ) as mock_mailgun, patch(
        "app.handler.signup_handler.stripe.Customer.create"
    ) as mock_stripe_customer, patch(
        "app.handler.signup_handler.stripe.checkout.Session.create"
    ) as mock_stripe_checkout:
        mock_mailgun.return_value = None
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


def test_signup_missing_fields(client):
    response = client.post(
        "/signup",
        data={
            "email": "",
            "name": "Test User",
            "password": "StrongPass123",
            "plan": "free",
            "confirm_password": "StrongPass123",
        },
        follow_redirects=True,
    )
    assert b"All fields are required" in response.data


def test_signup_password_mismatch(client):
    response = client.post(
        "/signup",
        data={
            "email": "user2@example.com",
            "name": "Test User2",
            "password": "pw1",
            "plan": "free",
            "confirm_password": "pw2",
        },
        follow_redirects=True,
    )
    assert b"Passwords do not match" in response.data


def test_signup_duplicate_email(client):
    with patch(
        "app.handler.signup_handler.send_mailgun_message"
    ) as mock_mailgun, patch(
        "app.handler.signup_handler.stripe.Customer.create"
    ) as mock_stripe_customer:
        mock_mailgun.return_value = None
        mock_stripe_customer.return_value = type(
            "Customer", (), {"id": "cus_test_dup"}
        )()
        # Register once
        client.post(
            "/signup",
            data={
                "email": "dup@example.com",
                "name": "Dup User",
                "password": "StrongPass123",
                "plan": "free",
                "confirm_password": "StrongPass123",
            },
            follow_redirects=True,
        )
        # Try again
        response = client.post(
            "/signup",
            data={
                "email": "dup@example.com",
                "name": "Dup User",
                "password": "StrongPass123",
                "plan": "free",
                "confirm_password": "StrongPass123",
            },
            follow_redirects=True,
        )
        assert b"Email address already exists" in response.data


def test_profile_requires_login(client):
    response = client.get("/profile", follow_redirects=False)
    assert response.status_code in (301, 302)
    assert "/login" in response.headers.get("Location", "")


def test_confirm_email_with_invalid_token(client):
    response = client.get("/confirm-email/some-invalid-token", follow_redirects=True)
    assert b"The confirmation link is invalid or has expired." in response.data
