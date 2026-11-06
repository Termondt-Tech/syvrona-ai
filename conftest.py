import os

import pytest
from sqlalchemy.pool import StaticPool
from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import User
from app.services.ai_streamer import ProviderRegistry
from tests.fakes import FakeProvider

# The suite runs on in-memory SQLite. Point TEST_DATABASE_URL at a disposable MySQL
# database to run the same tests against the production dialect (see CLAUDE.md).
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


def _engine_options(url):
    if url.startswith("sqlite"):
        return {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


@pytest.fixture
def create_user(app):
    def _create_user(
        email="user@example.com",
        password="password123",
        name="Test User",
        is_admin=False,
        is_active=True,
        subscription_status="inactive",
        subscription_plan=None,
        verified=True,
    ):
        hashed_pw = generate_password_hash(
            password, method="pbkdf2:sha256", salt_length=16
        )
        user = User(
            email=email,
            password=hashed_pw,
            name=name,
            is_admin=is_admin,
            is_active=is_active,
            subscription_status=subscription_status,
            subscription_plan=subscription_plan,
            verified=verified,
        )
        db.session.add(user)
        db.session.commit()
        return user

    return _create_user


@pytest.fixture
def login_user(client, create_user):
    def _login_user(email="user@example.com", password="password123", **kwargs):
        # Create user in DB if not already present
        create_user(email=email, password=password, **kwargs)
        # Log in using client (POST /login)
        response = client.post(
            "/login", data={"email": email, "password": password}, follow_redirects=True
        )
        return response

    return _login_user


@pytest.fixture
def fake_provider():
    return FakeProvider()


@pytest.fixture
def app(fake_provider):
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,  # Disable CSRF for tests
            "SQLALCHEMY_DATABASE_URI": TEST_DATABASE_URL,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SQLALCHEMY_ENGINE_OPTIONS": _engine_options(TEST_DATABASE_URL),
            "RATELIMIT_STORAGE_URI": "memory://",
        }
    )
    # Every provider key resolves to the same fake: no SDK client, no network.
    app.extensions["ai_providers"] = ProviderRegistry.of(
        openai=fake_provider, anthropic=fake_provider, gemini=fake_provider
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()  # close the pooled connection; one engine per test app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def subscriber(login_user):
    """Log in an active subscriber and return the user."""
    login_user(subscription_status="active")
    return User.query.filter_by(email="user@example.com").one()
