from app.models import (
    Conversation,
    create_conversation as db_create_conversation,
    get_conversation_messages as db_get_conversation_messages,
    get_user_conversations as db_get_user_conversations,
    update_conversation_title as db_update_conversation_title,
    delete_conversation as db_delete_conversation,
    search_conversations_by_message as db_search_conversations_by_message,
)


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
    conversation = Conversation.query.get(conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found")
    return conversation


def delete_conversation(conversation_id):
    db_delete_conversation(conversation_id)
    return True


def search_conversations_by_message(user_id, query):
    conversations, convo_to_msg = db_search_conversations_by_message(user_id, query)
    conversations = sorted(conversations, key=lambda x: x.created_at, reverse=True)
    # Sort conversations by created_at in descending order
    return conversations, convo_to_msg
