import logging
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_hcaptcha import hCaptcha
from flask_wtf import CSRFProtect


from app.config import Config

from app.extensions import init_extensions  # Import the redis client and limiter

from .log_config import configure_logging

db = SQLAlchemy()
migrate = Migrate()  # ← create Migrate instance

login_manager = LoginManager()

hcaptcha = hCaptcha()
csrf = CSRFProtect()


def _mask_url(url_obj):
    # SQLAlchemy 2.x: render_as_string(hide_password=True); 1.4 fallback otherwise
    try:
        return url_obj.render_as_string(hide_password=True)
    except Exception:
        # basic mask for older versions
        url = str(url_obj)
        if "@" in url and ":" in url.split("@")[0]:
            # replace password segment before '@'
            creds, host = url.split("@", 1)
            user = creds.split("://", 1)[-1].split(":")[0]
            return url.replace(creds, f"{user}:***")
        return url


def create_app(config=None):
    configure_logging()
    logger = logging.getLogger(__name__)

    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    db.init_app(app)

    migrate.init_app(app, db)  # ← bind Migrate to app/db

    init_extensions(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    hcaptcha.init_app(app)
    csrf.init_app(app)

    # Log a concise, definitive engine + pool line (once per process)
    with app.app_context():
        eng = db.engine
        try:
            app.logger.info(
                "SQLAlchemy: url=%s pool=%s",
                _mask_url(eng.url),
                eng.pool.status(),
            )
        except Exception as e:
            app.logger.warning("SQLAlchemy: could not read pool status: %s", e)

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

    from .prompt import prompt_bp as prompt_blueprint

    app.register_blueprint(prompt_blueprint)

    from .chain import chain_bp as chain_blueprint

    app.register_blueprint(chain_blueprint)

    from .knowledge_base import knowledge_bp as knowledge_blueprint

    app.register_blueprint(knowledge_blueprint)

    from .tags import tags_bp as tags_blueprint

    app.register_blueprint(tags_blueprint, url_prefix="/tags")

    from app.ratelimit_logging import bp as ratelimit_bp

    app.register_blueprint(ratelimit_bp)

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
        return dict(HCAPTCHA_ENABLED=app.config.get("HCAPTCHA_ENABLED", False))

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        # Optionally log the error here for debugging (don't show details to user)
        logger.error("Internal server error: %s", e)
        return render_template("500.html"), 500

    return app
