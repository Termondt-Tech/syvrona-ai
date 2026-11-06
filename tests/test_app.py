from unittest.mock import patch
from app import db
from app.models import User, Prompt


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
    with (
        patch("app.services.signup.send_mailgun_message") as mock_mailgun,
        patch("app.services.signup.stripe.Customer.create") as mock_stripe_customer,
    ):
        mock_mailgun.return_value = None
        mock_stripe_customer.return_value = type(
            "Customer", (), {"id": "cus_test_123"}
        )()
        response = client.post(
            "/signup",
            data={
                "email": "newuser@example.com",
                "name": "Test User",
                "password": "StrongPass123",  # gitleaks:allow
                "plan": "free",
                "confirm_password": "StrongPass123",  # gitleaks:allow
            },
            follow_redirects=True,
        )
        assert (
            b"Signup successful" in response.data
            or b"Thanks for signing up!" in response.data
        )


def test_signup_paid_plan_redirects_to_stripe(client):
    with (
        patch("app.services.signup.send_mailgun_message") as mock_mailgun,
        patch("app.services.signup.stripe.Customer.create") as mock_stripe_customer,
        patch(
            "app.services.signup.stripe.checkout.Session.create"
        ) as mock_stripe_checkout,
    ):
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
            "password": "StrongPass123",  # gitleaks:allow
            "plan": "free",
            "confirm_password": "StrongPass123",  # gitleaks:allow
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
    with (
        patch("app.services.signup.send_mailgun_message") as mock_mailgun,
        patch("app.services.signup.stripe.Customer.create") as mock_stripe_customer,
    ):
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
                "password": "StrongPass123",  # gitleaks:allow
                "plan": "free",
                "confirm_password": "StrongPass123",  # gitleaks:allow
            },
            follow_redirects=True,
        )
        # Try again
        response = client.post(
            "/signup",
            data={
                "email": "dup@example.com",
                "name": "Dup User",
                "password": "StrongPass123",  # gitleaks:allow
                "plan": "free",
                "confirm_password": "StrongPass123",  # gitleaks:allow
            },
            follow_redirects=True,
        )
        assert b"Email address already exists" in response.data


def test_profile_requires_login(client):
    response = client.get("/profile", follow_redirects=False)
    assert response.status_code in (301, 302)
    assert "/login" in response.headers.get("Location", "")


def test_profile_access_with_login(client, login_user):
    login_user(email="bob@example.com", password="securepw")
    response = client.get("/profile")
    assert response.status_code == 200
    assert b"Profile" in response.data  # Or check your profile content


def test_premium_page_requires_subscription(client, login_user):
    # Free user (inactive subscription)
    login_user(email="free@example.com", password="pw", subscription_status="inactive")
    response = client.get("/chat", follow_redirects=False)
    assert response.status_code in (301, 302, 403)
    # Check for upgrade message/redirect if you want


def test_premium_page_allows_subscribed_user(client, login_user):
    # Subscribed user (active subscription)
    login_user(email="paid@example.com", password="pw", subscription_status="active")
    response = client.get("/chat")
    assert response.status_code == 200
    assert b"Chat" in response.data  # Or expected content


def test_confirm_email_with_invalid_token(client):
    response = client.get("/confirm-email/some-invalid-token", follow_redirects=True)
    assert b"The confirmation link is invalid or has expired." in response.data


def test_prompt_list_requires_login(client):
    """Prompt list should require authentication."""
    response = client.get("/prompts")
    # Should redirect to login (302) or 401 if API
    assert response.status_code in (301, 302, 401)


def test_prompt_list_requires_subscription(client, login_user):
    """Prompt list should require active subscription."""
    login_user(email="free@example.com", password="pw", subscription_status="inactive")
    response = client.get("/prompts")
    assert response.status_code in (301, 302, 403)


def test_prompt_list_displays_prompts(client, login_user):
    """Prompt list shows user prompts."""
    login_user(email="paid@example.com", password="pw", subscription_status="active")
    user = User.query.filter_by(email="paid@example.com").first()

    prompt = Prompt(
        user_id=user.id,
        title="Test Prompt",
        description="Test Desc",
        body="Prompt Body",
    )
    db.session.add(prompt)
    db.session.commit()

    response = client.get("/prompts")
    assert response.status_code == 200
    assert b"Test Prompt" in response.data
    assert b"Test Desc" in response.data


def test_create_prompt_page(client, login_user):
    """User can view the prompt creation page."""
    login_user(email="paid@example.com", password="pw", subscription_status="active")
    response = client.get("/prompts/create")
    assert response.status_code == 200
    assert b"Create" in response.data


def test_create_prompt(client, login_user):
    """User can create a prompt via POST."""
    login_user(email="paid@example.com", password="pw", subscription_status="active")
    user = User.query.filter_by(email="paid@example.com").first()

    data = {
        "title": "My Prompt",
        "description": "My Description",
        "body": "Prompt Content",
    }
    response = client.post("/prompts/create", data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b"My Prompt" in response.data

    # Check DB
    assert (
        Prompt.query.filter_by(user_id=user.id, title="My Prompt").first() is not None
    )


def test_edit_prompt(client, login_user):
    """User can edit an existing prompt."""
    login_user(email="paid@example.com", password="pw", subscription_status="active")
    user = User.query.filter_by(email="paid@example.com").first()

    prompt = Prompt(user_id=user.id, title="EditMe", description="D", body="Body")
    db.session.add(prompt)
    db.session.commit()
    edit_url = f"/prompts/{prompt.id}/edit"

    # GET page
    response = client.get(edit_url)
    assert response.status_code == 200
    assert b"EditMe" in response.data

    # POST update
    data = {"title": "Edited", "description": "Desc", "body": "New Body"}
    response = client.post(edit_url, data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Edited" in response.data

    prompt = db.session.get(Prompt, prompt.id)  # SQLAlchemy 2.x style
    assert prompt.title == "Edited"


def test_delete_prompt(client, login_user):
    """User can delete an existing prompt."""
    login_user(email="paid@example.com", password="pw", subscription_status="active")
    user = User.query.filter_by(email="paid@example.com").first()

    prompt = Prompt(user_id=user.id, title="DelMe", description="", body="")
    db.session.add(prompt)
    db.session.commit()
    del_url = f"/prompts/{prompt.id}/delete"
    response = client.post(del_url, follow_redirects=True)
    assert response.status_code == 200
    assert db.session.get(Prompt, prompt.id) is None
