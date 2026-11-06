from app.models import (
    Conversation,
    Message,
    create_conversation as db_create_conversation,
    get_conversation_messages as db_get_conversation_messages,
    get_user_conversations as db_get_user_conversations,
    update_conversation_title as db_update_conversation_title,
    delete_conversation as db_delete_conversation,
    search_conversations_by_message as db_search_conversations_by_message,
)
from app import db
from sqlalchemy import or_
from collections import defaultdict


def create_conversation(user_id, title=None):
    new_conversation = db_create_conversation(
        user_id=user_id, title=generate_conversation_title(title)
    )
    return new_conversation


def generate_conversation_title(initial_prompt):
    title = initial_prompt[:60] + "..." if len(initial_prompt) > 60 else initial_prompt
    return title


def get_conversation_messages(conversation_id):
    messages = db_get_conversation_messages(conversation_id)
    return messages


def get_user_conversations(user_id):
    conversations = db_get_user_conversations(user_id)
    conversations = sorted(conversations, key=lambda x: x.created_at, reverse=True)
    # Sort conversations by created_at in descending order
    return conversations


def update_conversation_title(conversation_id, title):
    result = db_update_conversation_title(conversation_id, title)
    return result


def get_conversation(conversation_id):
    """Return the conversation, or ``None`` if there is no such row."""
    return db.session.get(Conversation, conversation_id)


def get_user_conversation(conversation_id, user_id):
    """Return the conversation only if it exists and belongs to ``user_id``."""
    conversation = get_conversation(conversation_id)
    if conversation is None or conversation.user_id != user_id:
        return None
    return conversation


def delete_conversation(conversation_id):
    db_delete_conversation(conversation_id)
    return True


def search_conversations_by_message(user_id, query):
    conversations, convo_to_msg = db_search_conversations_by_message(user_id, query)
    conversations = sorted(conversations, key=lambda x: x.created_at, reverse=True)
    # Sort conversations by created_at in descending order
    return conversations, convo_to_msg


def search_conversations_by_message_paginated(user_id, query, page=1, per_page=10):
    """
    Returns:
        Pagination: conversations paginated (like SQLAlchemy Flask paginate)
        dict: convo_to_msg mapping conversation.id -> [matching messages]
    """
    query = query.strip()
    # 1: Find convos where title matches or any msg content matches
    # Create subquery for conversations that have a message matching the query AND
    # belong to this user
    subq = (
        db.session.query(Message.conversation_id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            Conversation.user_id == user_id,
            Message.content.ilike(f"%{query}%"),
        )
        .subquery()
    )

    convo_query = (
        Conversation.query.filter(Conversation.user_id == user_id)
        .filter(or_(Conversation.title.ilike(f"%{query}%"), Conversation.id.in_(subq)))
        .order_by(Conversation.created_at.desc())
    )

    convos_paginated = convo_query.paginate(
        page=page, per_page=per_page, error_out=False
    )

    # 2: For convos on this page, fetch their matching messages (which match the query)
    paged_convo_ids = [c.id for c in convos_paginated.items]
    if paged_convo_ids:
        msgs = (
            Message.query.filter(
                Message.conversation_id.in_(paged_convo_ids),
                Message.content.ilike(f"%{query}%"),
            )
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Conversation.user_id == user_id)
            .order_by(Message.created_at.asc())
            .all()
        )

        convo_to_msg = defaultdict(list)
        for msg in msgs:
            convo_to_msg[msg.conversation_id].append(msg)
    else:
        convo_to_msg = {}

    return convos_paginated, convo_to_msg
