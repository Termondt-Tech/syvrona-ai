import pytest
from sqlalchemy.pool import StaticPool
from app import create_app, db
from werkzeug.security import generate_password_hash

from app.models import User


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
def app():
    # Set up test config
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,  # Disable CSRF for tests
            "SQLALCHEMY_DATABASE_URI": (
                "sqlite:///:memory:"  # Use in-memory DB for tests
            ),
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
