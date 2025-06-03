# ai_streamer.py
import logging
from app.model_registry import MODEL_REGISTRY
from app.providers.openai_provider import OpenAIProvider
from app.providers.anthropic_provider import AnthropicProvider

logger = logging.getLogger(__name__)


class AIStreamer:
    def __init__(self):
        self.providers = {
            "openai": OpenAIProvider(),
            "anthropic": AnthropicProvider(),
        }

    def chat(self, message, user_id, conversation_id, model):
        from app.models import create_message
        from app.handler.conversation_handler import get_conversation_messages

        context = [{"role": "system", "content": "You are an intelligent assistant."}]
        context += [
            {"role": msg.role, "content": msg.content}
            for msg in get_conversation_messages(conversation_id)
        ]

        user_message = create_message(conversation_id, "user", message)
        logger.info(f"User message created with ID: {user_message.id}")
        collected_chunks = []

        provider_key = MODEL_REGISTRY.get(model)
        if not provider_key:
            raise ValueError(f"No provider registered for model '{model}'")

        provider = self.providers[provider_key]

        provider = self.providers[provider_key]
        logger.info(f"Using provider '{provider_key}' for model '{model}'")
        logger.info("Calling provider.stream_response...")

        try:
            for chunk in provider.stream_response(
                message, user_id, conversation_id, model
            ):
                collected_chunks.append(chunk)
                yield chunk
        except Exception as e:
            logger.error(f"Error in provider.stream_response: {e}")

        assistant_message = create_message(
            conversation_id, "assistant", "".join(collected_chunks)
        )
        logger.info(f"Assistant message created with ID: {assistant_message.id}")
