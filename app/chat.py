import logging
from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    request,
    jsonify,
    render_template,
    abort,
    session,
    stream_with_context,
    url_for,
)
from flask_login import current_user, login_required

from app.decorators import require_active_subscription
from app.handler.conversation_handler import (
    create_conversation,
    delete_conversation,
    get_conversation,
    get_user_conversations,
    search_conversations_by_message,
    update_conversation_title,
    get_conversation_messages,
)

from . import db

from app.models import Message, Tag, message_tags, Conversation

chat = Blueprint("chat", __name__)

logger = logging.getLogger(__name__)


@chat.route("/tags")
@login_required
@require_active_subscription
def get_tags():
    q = request.args.get("q", "").strip()
    tags_query = Tag.query.filter_by(user_id=current_user.id)
    if q:
        tags_query = tags_query.filter(Tag.name.ilike(f"%{q}%"))
    tags = tags_query.order_by(Tag.name).all()
    return jsonify([{"id": tag.id, "name": tag.name} for tag in tags])


@chat.route("/messages/<int:msg_id>/tags", methods=["POST"])
@login_required
@require_active_subscription
def add_tag_to_message(msg_id):
    data = request.get_json()
    tag_name = data.get("tag", "").strip()
    if not tag_name:
        abort(400, "Tag name required")

    # One word/multiword tag normalization (optional)
    # tag_name = tag_name.lower()

    message = Message.query.get_or_404(msg_id)
    # Make sure user owns the message (or has access)
    if message.conversation.user_id != current_user.id:
        abort(403)

    # Check for existing tag, else create
    tag = Tag.query.filter_by(user_id=current_user.id, name=tag_name).first()
    if not tag:
        tag = Tag(name=tag_name, user_id=current_user.id)
        db.session.add(tag)
        db.session.flush()  # get tag.id without full commit

    if tag not in message.tags:
        message.tags.append(tag)
        db.session.commit()
        return jsonify({"success": True, "tag": {"id": tag.id, "name": tag.name}})
    else:
        return jsonify({"success": False, "reason": "Tag already present"}), 409


@chat.route("/messages/<int:msg_id>/tags/<int:tag_id>", methods=["DELETE"])
@login_required
@require_active_subscription
def remove_tag_from_message(msg_id, tag_id):
    message = Message.query.get_or_404(msg_id)
    tag = Tag.query.get_or_404(tag_id)

    # Ownership check
    if (
        message.conversation.user_id != current_user.id
        or tag.user_id != current_user.id
    ):
        abort(404)

    if tag in message.tags:
        message.tags.remove(tag)
        db.session.commit()
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "reason": "Tag not found"}), 404


@chat.route("/my-tags", methods=["GET"])
@login_required
@require_active_subscription
def my_tags():
    user_id = current_user.get_id()
    # Get all tags used by this user's messages, plus usage count
    tags = (
        db.session.query(Tag, db.func.count(Message.id).label("msg_count"))
        .join(message_tags, Tag.id == message_tags.c.tag_id)
        .join(Message, Message.id == message_tags.c.message_id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(Conversation.user_id == user_id)
        .group_by(Tag.id)
        .order_by(db.func.count(Message.id).desc(), Tag.name.asc())
        .all()
    )
    return render_template("my_tags.html", tags=tags)


@chat.route("/tag/<int:tag_id>")
@login_required
def tagged_messages(tag_id):
    # Get the tag
    tag = Tag.query.get_or_404(tag_id)
    # Ensure the tag belongs to the current user
    if tag.user_id != current_user.get_id():
        abort(404)
    # Get all messages for this tag (owned by user)
    messages = (
        db.session.query(Message, Conversation)
        .join(message_tags)
        .join(Tag)
        .join(Conversation)
        .filter(Tag.id == tag_id, Conversation.user_id == current_user.get_id())
        .order_by(Message.created_at.desc())
        .all()
    )
    # Each item is a tuple: (Message, Conversation)
    return render_template("tagged_messages.html", tag=tag, messages=messages)


@chat.route("/message/<int:message_id>")
@login_required
@require_active_subscription
def view_message(message_id):

    message = Message.query.get_or_404(message_id)
    # Ensure the message belongs to a conversation owned by the user
    if message.conversation.user_id != current_user.id:
        abort(404)

    conversation = Conversation.query.get_or_404(message.conversation_id)
    # Optional: get tag_id from ?tag= if coming from tagged page
    back_to_tag_id = request.args.get("tag", type=int)
    back_to_tag_name = None
    if back_to_tag_id:
        tag = next((t for t in message.tags if t.id == back_to_tag_id), None)
        back_to_tag_name = tag.name if tag else None
    return render_template(
        "message_view.html",
        message=message,
        conversation=conversation,
        back_to_tag_id=back_to_tag_id,
        back_to_tag_name=back_to_tag_name,
    )


@chat.route("/conversations")
@login_required
@require_active_subscription
def conversations():
    user_id = current_user.get_id()
    q = request.args.get("q", "").strip()
    if q:
        convos, convo_to_msg = search_conversations_by_message(user_id, q)
        search_query = q
    else:
        convos = get_user_conversations(user_id)
        convo_to_msg = {}
        search_query = ""
        logger.info(f"User {user_id} has {len(convos)} conversations.")

    if not convos:
        flash("No conversations found.", "info")
        return render_template("conversations.html", conversations=[])
    # Check if the user has conversations
    return render_template(
        "conversations.html",
        conversations=convos,
        convo_to_msg=convo_to_msg,
        search_query=search_query,
    )


@chat.route("/conversation/<int:conversation_id>/edit", methods=["POST"])
@login_required
@require_active_subscription
def edit_conversation_title(conversation_id):
    convo = get_conversation(conversation_id)
    if convo is None or convo.user_id != current_user.id:
        abort(404)

    update_conversation_title(conversation_id, request.form["title"])
    logger.info(f"Conversation {conversation_id} title updated.")
    flash("Conversation title updated successfully!", "success")
    # Redirect to the conversations page
    return redirect(url_for("chat.conversations"))


@chat.route("/conversation/<int:conversation_id>")
@login_required
@require_active_subscription
def resume_conversation(conversation_id):
    conversation = get_conversation(conversation_id)
    if conversation is None:
        flash("Conversation not found.", "error")
        return redirect(url_for("chat.conversations"))
    if conversation.user_id != current_user.id:
        abort(404)  # Unauthorized access - send as 404 to avoid leaking info
    session["conversation_id"] = conversation.id
    logger.info(f"Resumed conversation with ID: {conversation_id}")
    return redirect(url_for("chat.chat_page"))


@chat.route("/conversation/<int:conversation_id>/view")
@login_required
@require_active_subscription
def view_conversation(conversation_id):
    convo = get_conversation(conversation_id)
    if convo is None or convo.user_id != current_user.id:
        abort(404)  # Not found or unauthorized

    messages = get_conversation_messages(conversation_id)

    if messages is None:
        flash("Messages not found.", "error")
        return redirect(url_for("chat.conversations"))

    logger.info(
        (
            f"Viewing conversation with ID: {conversation_id} "
            f"for user: {current_user.get_id()}"
        )
    )
    return render_template(
        "conversation_view.html", conversation=convo, messages=messages
    )


@chat.route("/conversation/<int:conversation_id>/delete", methods=["POST"])
@login_required
@require_active_subscription
def delete_conversation_route(conversation_id):
    convo = get_conversation(conversation_id)
    if not convo or convo.user_id != current_user.id:
        abort(404)  # Not found or unauthorized
    session.pop("conversation_id", None)  # In case it was active
    delete_conversation(conversation_id)
    flash("Conversation deleted.", "success")
    logger.info(
        (
            f"Conversation {conversation_id} deleted for user: "
            f"{current_user.get_id()}"
        )
    )
    return redirect(url_for("chat.conversations"))


@chat.route("/conversation/<int:conversation_id>/latest")
@login_required
@require_active_subscription
def latest_messages(conversation_id):
    # Ensure the conversation exists and belongs to the user
    convo = get_conversation(conversation_id)
    if convo is None or convo.user_id != current_user.id:
        abort(404)
    # Get the most recent 2 messages in reverse order (latest first)
    messages = (
        Message.query.filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at.desc())
        .limit(2)
        .all()
    )
    # Return most recent *assistant* and *user* message with IDs and tags
    return jsonify(
        [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "model": m.model,
                "tags": [{"id": t.id, "name": t.name} for t in m.tags],
            }
            for m in reversed(messages)
        ]
    )


@chat.route("/chat/new")
@login_required
@require_active_subscription
def new_chat():
    logger.info(f"New chat for user: {current_user.get_id()}")
    session.pop("conversation_id", None)
    return redirect(url_for("chat.chat_page"))


@chat.route("/chat")
@login_required
@require_active_subscription
def chat_page():
    logger.info(f"Current User: {current_user.get_id()}")
    conversation_id = session.get("conversation_id")
    messages = []

    if conversation_id:
        conversation = get_conversation(conversation_id)
        if conversation and conversation.user_id == current_user.id:
            messages = get_conversation_messages(conversation_id)
    return render_template("chat.html", messages=messages)


@chat.route("/answer", methods=["GET", "POST"])
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

    response = Response(generate(), content_type="text/plain")
    response.headers["X-Conversation-Id"] = str(conversation_id)
    return response
