# providers/openai_provider.py
import logging
from openai import OpenAI
from app.providers.base_provider import AIProvider
from app.handler.conversation_handler import get_conversation_messages
from app.models import create_message

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    def __init__(self):
        self.client = OpenAI()

    def stream_response(self, message, user_id, conversation_id, model):
        logger.info(
            f"OpenAIProvider: User ID {user_id}, Conversation ID {conversation_id}"
        )
        logger.info(f"User message: {message}")

        context = []
        conversation_history = get_conversation_messages(conversation_id)

        for msg in conversation_history:
            if msg.role in ["user", "assistant"]:
                context.append({"role": msg.role, "content": msg.content})

        if message:
            context.append({"role": "user", "content": message})

            collected_chunks = []

            try:
                stream = self.client.chat.completions.create(
                    model=model, messages=context, stream=True
                )

                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        collected_chunks.append(text)
                        yield text

            except Exception as e:
                logger.error(f"OpenAI stream error: {e}")
                raise
