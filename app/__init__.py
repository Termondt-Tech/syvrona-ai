import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_hcaptcha import hCaptcha


from app.config import Config

from .log_config import configure_logging

db = SQLAlchemy()
migrate = Migrate()  # ← create Migrate instance

login_manager = LoginManager()

logger = logging.getLogger(__name__)

hcaptcha = hCaptcha()


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    db.init_app(app)
    logger.info("Database initialized")
    migrate.init_app(app, db)  # ← bind Migrate to app/db
    logger.info("Migration initialized")

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    logger.info("Login manager initialized")

    configure_logging()
    logger.info("Logging configured")

    hcaptcha.init_app(app)

    logger.info("App configuration:")
    logger.info(
        "SQLALCHEMY_DATABASE_URI: %s", app.config.get("SQLALCHEMY_DATABASE_URI")
    )

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from .routes import main as main_blueprint

    app.register_blueprint(main_blueprint)

    from .auth import auth as auth_blueprint

    app.register_blueprint(auth_blueprint)

    from .admin_routes import admin as admin_blueprint  # Adjust import path as needed

    app.register_blueprint(admin_blueprint)

    from .billing import billing as billing_blueprint  # Adjust import path as needed

    app.register_blueprint(billing_blueprint)

    from .health_routes import (
        health as health_blueprint,
    )  # Adjust import path as needed

    app.register_blueprint(health_blueprint)

    from app.chat import chat as chat_blueprint

    app.register_blueprint(chat_blueprint)

    from .support import support as support_blueprint

    app.register_blueprint(support_blueprint)

    @app.context_processor
    def inject_unread_notification_count():
        from app.models import Notification, NotificationRead
        if not current_user.is_authenticated:
            return dict(unread_notifications=0)
        notifications = Notification.query.filter(
            (Notification.for_user_id.is_(None))
            | (Notification.for_user_id == current_user.id)
        ).all()
        read_rows = NotificationRead.query.filter_by(user_id=current_user.id).all()
        read_ids = {
            nr.notification_id for nr in read_rows if not getattr(nr, "archived", False)
        }
        archived_ids = {
            nr.notification_id for nr in read_rows if getattr(nr, "archived", False)
        }
        unread_count = len(
            [
                n
                for n in notifications
                if n.id not in read_ids and n.id not in archived_ids
            ]
        )
        return dict(unread_notifications=unread_count)

    @app.context_processor
    def inject_hcaptcha_enabled():
        return dict(HCAPTCHA_ENABLED=app.config.get('HCAPTCHA_ENABLED', False))

    return app
