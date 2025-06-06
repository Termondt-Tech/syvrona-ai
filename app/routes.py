import logging
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.security import generate_password_hash
from flask_login import login_required, current_user

import app
from app.models import User
from . import db
from .constants import PRICE_LABELS


# Create a Blueprint named 'main'
main = Blueprint("main", __name__)

logger = logging.getLogger(__name__)

# Define the index route


@main.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@main.route("/privacy", methods=["GET"])
def privacy():
    return render_template("privacy.html")


@main.route("/terms", methods=["GET"])
def terms():
    return render_template("terms.html")


@main.route("/profile")
@login_required
def profile():

    user = db.session.get(User, current_user.id)

    return render_template("profile.html", user=user, price_labels=PRICE_LABELS)


@main.route("/profile/update", methods=["POST"])
@login_required
def update_profile():
    try:

        name = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not name or not email:
            flash("Name and email are required.", "warning")
            return redirect(url_for("main.profile"))
        current_user.name = name
        current_user.email = email
        if password:
            password = generate_password_hash(password, method="pbkdf2", salt_length=16)
            current_user.set_password(password)
        app.db.session.commit()

        logger.info(f"Profile updated for user: {current_user.get_id()}")
        flash("Profile updated successfully!", "success")
        return redirect(url_for("main.profile"))
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        flash("Error updating profile.", "error")
        return redirect(url_for("main.profile"))
