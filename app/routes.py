from contextlib import contextmanager
from http import client
import logging
from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, stream_with_context, url_for
from werkzeug.security import generate_password_hash
from flask_login import login_required, current_user
from openai import OpenAI

import app
from app.handler import openai_handler
from app.handler.openai_streamer import OpenAIStreamer

# Create a Blueprint named 'main'
main = Blueprint('main', __name__)

logger = logging.getLogger(__name__)

# Define the index route


@main.route('/', methods=["GET"])
def index():
    return render_template("index.html")

@main.route('/privacy', methods=["GET"])
def privacy():
    return render_template("privacy.html")

@main.route('/terms', methods=["GET"])
def terms():
    return render_template("terms.html")


@main.route('/profile')
@login_required
def profile():
    profile_data = {
        "name": current_user.name,
        "email": current_user.email
    }
    return render_template('profile.html', user=profile_data)


@main.route('/profile/update', methods=["POST"])
@login_required
def update_profile():
    try:

        name = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not name or not email:
            flash('Name and email are required.', 'warning')
            return redirect(url_for('main.profile'))
        current_user.name = name
        current_user.email = email
        if password:
            password = generate_password_hash(
                password, method='pbkdf2', salt_length=16)
            current_user.set_password(password)
        app.db.session.commit()

        logger.info(f"Profile updated for user: {current_user.get_id()}")
        flash("Profile updated successfully!", "success")
        return redirect(url_for('main.profile'))
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        flash("Error updating profile.", "error")
        return redirect(url_for('main.profile'))


@main.route('/chat')
@login_required
def chat():
    print("Current User:", current_user.get_id())
    logger.info(f"Current User: {current_user.get_id()}")
    return render_template('chat.html')


@main.route("/answer", methods=["GET", "POST"])
@login_required
def answer():
    data = request.get_json()
    message = data["message"]
    logger.info(f"Current User: {current_user.get_id()}")
    user_id = current_user.get_id()

    streamer = OpenAIStreamer()

    @stream_with_context
    def generate():
        response = streamer.chat(message, user_id)
        for res in response:
            yield res

    return Response(generate(), content_type="text/plain")
