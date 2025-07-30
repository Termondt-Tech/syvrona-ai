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
from flask_wtf.csrf import generate_csrf

from app.decorators import require_active_subscription
from app.services.conversation import (
    create_conversation,
    delete_conversation,
    get_conversation,
    search_conversations_by_message_paginated,
    update_conversation_title,
    get_conversation_messages,
)
from app.model_registry import DEFAULT_MODEL_KEY, MODEL_REGISTRY

from . import db

from app.models import Message, PromptChain, Tag, message_tags, Conversation


chat = Blueprint("chat", __name__)

logger = logging.getLogger(__name__)


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


@chat.route("/tag/<int:tag_id>")
@login_required
def tagged_messages(tag_id):
    # Get the tag
    tag = Tag.query.get_or_404(tag_id)
    # Ensure the tag belongs to the current user
    if tag.user_id != current_user.id:
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


@chat.route("/newtag", methods=["POST"])
@login_required
@require_active_subscription
def create_tag():
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Missing tag name"}), 400

    # Case-insensitive check for existing tag for this user
    tag = (
        Tag.query.filter_by(user_id=current_user.id)
        .filter(db.func.lower(Tag.name) == name.lower())
        .first()
    )
    if tag:
        # Return existing tag (idempotent)
        return jsonify({"id": tag.id, "name": tag.name}), 200

    tag = Tag(user_id=current_user.id, name=name)
    db.session.add(tag)
    db.session.commit()
    return jsonify({"id": tag.id, "name": tag.name}), 201


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
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    q = request.args.get("q", "").strip()

    if q:
        convos, convo_to_msg = search_conversations_by_message_paginated(
            current_user.id, q, page, per_page
        )
    else:
        convos = (
            Conversation.query.filter_by(user_id=current_user.id)
            .order_by(Conversation.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
        convo_to_msg = {}

    return render_template(
        "conversations.html",
        conversations=convos,
        search_query=q,
        convo_to_msg=convo_to_msg,
        active_tab="conversations",
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
    # Extract current pagination/search context from form
    page = request.form.get("page", 1, type=int)
    per_page = request.form.get("per_page", 10, type=int)
    q = request.form.get("q", "").strip()

    # Authorization and deletion
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

    # --- Edge case: If the page is now empty, go to previous page
    # Only possible if page > 1

    # Get current list of user's conversations (after deletion)
    query = Conversation.query.filter_by(user_id=current_user.id)
    if q:
        query = query.filter(Conversation.title.ilike(f"%{q}%"))
    # Count how many items left on the *now-current* page
    pagination = query.order_by(Conversation.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # If page > 1 and no items on this page, go back one page
    if page > 1 and len(pagination.items) == 0:
        page -= 1

    return redirect(url_for("chat.conversations", page=page, per_page=per_page, q=q))


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


@chat.route("/chat", methods=["GET", "POST"])
@login_required
@require_active_subscription
def chat_page():
    conversation_id = None
    prefilled_prompt = ""
    selected_model = DEFAULT_MODEL_KEY
    messages = []

    # Handle POST logic (form submits, prompt chain runs, continue conversation, etc.)
    if request.method == "POST":
        # Check for conversation resume
        conversation_id = request.form.get("conversation_id")
        # Check for prompt/chain prefill
        chain_id = request.form.get("chain_id")
        if chain_id:
            chain = PromptChain.query.filter_by(
                id=chain_id, user_id=current_user.id
            ).first_or_404()
            context = request.form.get("context", "").strip()
            prompt_bodies = [p.body for p in chain.prompts]
            if context:
                prompt_bodies.append(context)
            prefilled_prompt = "\n\n".join(prompt_bodies)
            selected_model = request.form.get("model", DEFAULT_MODEL_KEY)
        elif request.form.get("body") is not None:
            prefilled_prompt = request.form.get("body", "")
            selected_model = request.form.get("model", DEFAULT_MODEL_KEY)
        else:
            selected_model = (
                request.form.get("model", DEFAULT_MODEL_KEY) or DEFAULT_MODEL_KEY
            )

    # If conversation_id exists, load conversation and messages
    if conversation_id:
        conversation = get_conversation(conversation_id)
        if conversation and conversation.user_id == current_user.id:
            messages = get_conversation_messages(conversation_id)
            if messages:
                last_msg_with_model = next(
                    (m for m in reversed(messages) if m.model), None
                )
                if last_msg_with_model:
                    selected_model = last_msg_with_model.model

    # Build available models for selector
    available_models = [
        {
            "key": k,
            "provider": v.get("provider", "unknown"),
            "display_name": v.get("display_name", k),
        }
        for k, v in MODEL_REGISTRY.items()
    ]
    available_models.sort(key=lambda m: (m["provider"], m["key"]))

    return render_template(
        "chat.html",
        messages=messages,
        available_models=available_models,
        default_model=DEFAULT_MODEL_KEY,
        selected_model=selected_model,
        conversation_id=conversation_id,
        prefilled_prompt=prefilled_prompt,
    )


@chat.route("/answer", methods=["GET", "POST"])
@login_required
@require_active_subscription
def answer():
    try:
        data = request.get_json()
        message = data["message"]
        model = data.get("model", "gpt-3.5-turbo")  # default fallback
        raw_conversation_id = data.get("conversation_id")

        user_id = current_user.get_id()

        if raw_conversation_id in (None, "", "None", "null"):
            conversation_id = None
        else:
            try:
                conversation_id = int(raw_conversation_id)
            except (TypeError, ValueError):
                conversation_id = None

        if not conversation_id:
            conversation = create_conversation(user_id, message)
            conversation_id = conversation.id

        from app.services.ai_streamer import AIStreamer  # adjust path as needed

        streamer = AIStreamer()

        @stream_with_context
        def generate():
            response = streamer.chat(message, user_id, conversation_id, model)
            for res in response:
                yield res

        response = Response(generate(), content_type="text/plain")
        response.headers["X-Conversation-Id"] = str(conversation_id)
        # This line delivers a fresh CSRF token to the client for the next request
        response.headers["X-CSRFToken"] = generate_csrf()
        return response
    except Exception as e:
        logger.error(
            "Error in /answer: user_id=%s remote_addr=%s error=%s",
            current_user.get_id(),
            request.remote_addr,
            e,
        )
        return Response("Internal Server Error", status=500)
