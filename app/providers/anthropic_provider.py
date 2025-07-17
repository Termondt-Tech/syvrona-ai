import os
import logging
from anthropic import Anthropic

from app.services.conversation import get_conversation_messages
from app.providers.base_provider import AIProvider
from app.model_registry import get_model_metadata

logger = logging.getLogger(__name__)


class AnthropicProvider(AIProvider):
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def stream_response(self, message, user_id, conversation_id, model):
        logger.info(
            f"AnthropicProvider: User ID {user_id}, Conversation ID {conversation_id}"
        )
        logger.info(f"User message: {message}")

        conversation_history = get_conversation_messages(conversation_id)

        # Claude 3 uses structured messages and an optional system prompt
        system_prompt = "You are an intelligent assistant."

        messages = []
        for msg in conversation_history:
            if msg.role in ["user", "assistant"]:
                messages.append({"role": msg.role, "content": msg.content})

        if message:
            messages.append({"role": "user", "content": message})
            # Only Anthropic needs this logic:
            metadata = get_model_metadata(model)
            max_tokens = metadata.get("max_tokens", 4096)  # default fallback
            collected_chunks = []

            try:
                with self.client.messages.stream(
                    model=model,
                    system=system_prompt,
                    messages=messages,
                    max_tokens=max_tokens,
                ) as stream:
                    for chunk in stream:
                        if chunk.type == "content_block_delta":
                            text = (
                                chunk.delta.text
                            )  # ✅ FIX: Access `text` as attribute, not with .get()
                            collected_chunks.append(text)
                            yield text
            except Exception as e:
                logger.error(f"Anthropic stream error: {e}")
                raise
