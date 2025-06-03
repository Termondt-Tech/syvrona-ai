from contextlib import contextmanager
from http import client
import logging
from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
    session,
)
from werkzeug.security import generate_password_hash
from flask_login import login_required, current_user
from openai import OpenAI

import app
from app.handler import openai_handler
from app.handler.conversation_handler import (
    create_conversation,
    get_user_conversations,
    update_conversation_title,
    get_conversation,
    get_conversation_messages,
    delete_conversation,
)
from app.models import User
from app.decorators import require_active_subscription
import os


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
    PRICE_LABELS = {
        os.getenv("STRIPE_PRICE_ID_PRO_MONTHLY"): "Pro Monthly ($9.99/mo)",
        os.getenv("STRIPE_PRICE_ID_PRO_YEARLY"): "Pro Yearly ($99/year)",
    }

    user = User.query.get(current_user.id)
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


@main.route("/chat/new")
@login_required
@require_active_subscription
def new_chat():
    logger.info(f"New chat for user: {current_user.get_id()}")
    session.pop("conversation_id", None)
    return redirect(url_for("main.chat"))


@main.route("/chat")
@login_required
@require_active_subscription
def chat():
    logger.info(f"Current User: {current_user.get_id()}")
    conversation_id = session.get("conversation_id")
    messages = []

    if conversation_id:
        conversation = get_conversation(conversation_id)
        if conversation and conversation.user_id == current_user.id:
            messages = get_conversation_messages(conversation_id)
    return render_template("chat.html", messages=messages)


@main.route("/answer", methods=["GET", "POST"])
@login_required
@require_active_subscription
def answer():
    data = request.get_json()
    message = data["message"]
    model = data.get("model", "gpt-3.5-turbo")  # default fallback
    logger.info(f"Model: {model}")
    logger.info(f"Current User: {current_user.get_id()}")
    user_id = current_user.get_id()
    conversation_id = session.get("conversation_id")
    if not conversation_id:
        conversation = create_conversation(user_id, message)
        conversation_id = conversation.id
        logger.info(f"New conversation created with ID: {conversation_id}")
        # Store the conversation ID in the session
        session["conversation_id"] = conversation_id

    from app.handler.ai_streamer import AIStreamer  # adjust path as needed

    streamer = AIStreamer()

    logger.info("Calling AIStreamer.chat...")

    @stream_with_context
    def generate():
        response = streamer.chat(message, user_id, conversation_id, model)
        for res in response:
            yield res

    return Response(generate(), content_type="text/plain")


@main.route("/conversations")
@login_required
@require_active_subscription
def conversations():
    user_id = current_user.get_id()
    convos = get_user_conversations(user_id)
    logger.info(f"User {user_id} has {len(convos)} conversations.")
    if not convos:
        flash("No conversations found.", "info")
        return render_template("conversations.html", conversations=[])
    # Check if the user has conversations
    return render_template("conversations.html", conversations=convos)


@main.route("/conversation/<int:conversation_id>/edit", methods=["POST"])
@login_required
@require_active_subscription
def edit_conversation_title(conversation_id):
    update_conversation_title(conversation_id, request.form["title"])
    logger.info(f"Conversation {conversation_id} title updated.")
    flash("Conversation title updated successfully!", "success")
    # Redirect to the conversations page
    return redirect(url_for("main.conversations"))


@main.route("/conversation/<int:conversation_id>")
@login_required
@require_active_subscription
def resume_conversation(conversation_id):
    conversation = get_conversation(conversation_id)
    if conversation is None:
        flash("Conversation not found.", "error")
        return redirect(url_for("main.conversations"))
    if conversation.user_id != current_user.id:
        return "Unauthorized", 403
    session["conversation_id"] = conversation.id
    logger.info(f"Resumed conversation with ID: {conversation_id}")
    return redirect(url_for("main.chat"))


@main.route("/conversation/<int:conversation_id>/view")
@login_required
@require_active_subscription
def view_conversation(conversation_id):
    convo = get_conversation(conversation_id)
    if convo is None:
        flash("Conversation not found.", "error")
        return redirect(url_for("main.conversations"))
    if convo.user_id != current_user.id:
        return "Unauthorized", 403

    messages = get_conversation_messages(conversation_id)

    if messages is None:
        flash("Messages not found.", "error")
        return redirect(url_for("main.conversations"))

    logger.info(
        f"Viewing conversation with ID: {conversation_id} for user: {current_user.get_id()}"
    )
    return render_template(
        "view_conversation.html", conversation=convo, messages=messages
    )


@main.route("/conversation/<int:conversation_id>/delete", methods=["POST"])
@login_required
@require_active_subscription
def delete_conversation_route(conversation_id):
    convo = get_conversation(conversation_id)
    if not convo or convo.user_id != current_user.id:
        return "Unauthorized", 403
    session.pop("conversation_id", None)  # In case it was active
    delete_conversation(conversation_id)
    flash("Conversation deleted.", "success")
    logger.info(
        f"Conversation {conversation_id} deleted for user: {current_user.get_id()}"
    )
    return redirect(url_for("main.conversations"))
