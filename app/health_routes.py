# app/health_routes.py
import logging
from flask import Blueprint, jsonify
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from . import db  # Import your SQLAlchemy db instance

logger = logging.getLogger(__name__)

health = Blueprint("health", __name__)


@health.route("/healthz")
def healthz():
    return jsonify({"status": "ok"}), 200


@health.route("/readyz")
def readyz():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ready"}), 200
    except OperationalError as e:
        logger.error("Database connection error during readiness check: %s", e)
        return jsonify({"status": "db-error"}), 503
