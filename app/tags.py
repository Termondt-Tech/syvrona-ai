# tags.py
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from app.decorators import require_active_subscription
from app.models import (
    Conversation,
    Message,
    Tag,
    Prompt,
    PromptChain,
    message_tags,
    prompt_tags,
    chain_tags,
)
from .services.tags import TagService

from . import db

tags_bp = Blueprint("tags", __name__)


@tags_bp.route("/")
@login_required
@require_active_subscription
def get_tags():
    q = request.args.get("q", "").strip()
    tags_query = Tag.query.filter_by(user_id=current_user.id)
    if q:
        tags_query = tags_query.filter(Tag.name.ilike(f"%{q}%"))
    tags = tags_query.order_by(Tag.name).all()
    return jsonify([{"id": tag.id, "name": tag.name} for tag in tags])


@tags_bp.route("/my-tags", methods=["GET"])
@login_required
@require_active_subscription
def my_tags():
    user_id = current_user.get_id()
    TagObj = Tag  # Just for clarity

    # Message tag count
    msg_counts = (
        db.session.query(TagObj.id, db.func.count(Message.id))
        .join(message_tags, TagObj.id == message_tags.c.tag_id)
        .join(Message, Message.id == message_tags.c.message_id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(Conversation.user_id == user_id)
        .group_by(TagObj.id)
        .all()
    )
    # Prompt tag count
    prompt_counts = (
        db.session.query(TagObj.id, db.func.count(Prompt.id))
        .join(prompt_tags, TagObj.id == prompt_tags.c.tag_id)
        .join(Prompt, Prompt.id == prompt_tags.c.prompt_id)
        .filter(Prompt.user_id == user_id)
        .group_by(TagObj.id)
        .all()
    )
    # Chain tag count
    chain_counts = (
        db.session.query(TagObj.id, db.func.count(PromptChain.id))
        .join(chain_tags, TagObj.id == chain_tags.c.tag_id)
        .join(PromptChain, PromptChain.id == chain_tags.c.chain_id)
        .filter(PromptChain.user_id == user_id)
        .group_by(TagObj.id)
        .all()
    )

    # Gather all tags belonging to user (even unused, if desired)
    user_tags = (
        TagObj.query.filter_by(user_id=user_id).order_by(TagObj.name.asc()).all()
    )

    # Compose dicts for fast lookup
    msg_map = dict(msg_counts)
    prompt_map = dict(prompt_counts)
    chain_map = dict(chain_counts)

    # Compose final tag list
    tags_data = []
    for tag in user_tags:
        tags_data.append(
            {
                "tag": tag,
                "msg_count": msg_map.get(tag.id, 0),
                "prompt_count": prompt_map.get(tag.id, 0),
                "chain_count": chain_map.get(tag.id, 0),
            }
        )

    # Optionally, hide tags unused everywhere:
    # tags_data = [
    #    t for t in tags_data if t["msg_count"] or t["prompt_count"] or t["chain_count"]
    # ]

    return render_template("my_tags.html", tags=tags_data)


@tags_bp.route("/rename/<int:tag_id>", methods=["POST"])
@login_required
@require_active_subscription
def rename_tag(tag_id):
    new_name = request.json.get("new_name", "")
    if not new_name or len(new_name.strip()) < 2:
        return jsonify(success=False, error="Name invalid."), 400

    success, error = TagService.rename_tag(
        user_id=current_user.id, tag_id=tag_id, new_name=new_name
    )
    if not success:
        return jsonify(success=False, error=error or "Unknown error"), 400
    return jsonify(success=True)


@tags_bp.route("/delete/<int:tag_id>", methods=["POST"])
@login_required
@require_active_subscription
def delete_tag(tag_id):
    success, error = TagService.delete_tag(user_id=current_user.id, tag_id=tag_id)
    if not success:
        return jsonify(success=False, error=error or "Unknown error"), 400
    return jsonify(success=True)
