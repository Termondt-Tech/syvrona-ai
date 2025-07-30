import logging
from typing import Any, Generator, List, Optional, Dict

import time

from app.model_registry import get_model_metadata
from app.providers.openai_provider import OpenAIProvider, ModelAccessError
from app.providers.anthropic_provider import AnthropicProvider
from app.models import create_message

logger = logging.getLogger(__name__)


class MessagePersister:
    def save_user(self, conv_id: Optional[int], user_msg: str, model: str) -> Any:
        msg = create_message(conv_id, "user", user_msg, model)
        logger.info(
            "User message saved: id=%s conv=%s model=%s", msg.id, conv_id, model
        )
        return msg

    def save_assistant(self, conv_id: Optional[int], text: str, model: str) -> Any:
        msg = create_message(conv_id, "assistant", text, model)
        logger.info(
            "Assistant message saved: id=%s conv=%s model=%s", msg.id, conv_id, model
        )
        return msg


class ProviderRegistry:
    """Resolves provider instances based on provider key."""

    def __init__(self, providers: Optional[Dict[str, Any]] = None) -> None:
        # Dependency injection for testability/extensibility
        self._providers = providers or {
            "openai": OpenAIProvider(),
            "anthropic": AnthropicProvider(),
        }

    def get_provider(self, provider_key: str) -> Any:
        try:
            return self._providers[provider_key]
        except KeyError:
            raise ValueError(f"No provider registered for key '{provider_key}'")


class AIStreamer:
    """
    High-level facade for provider selection, token streaming, and message persistence.
    """

    def __init__(
        self,
        provider_registry: Optional[ProviderRegistry] = None,
        persister: Optional[MessagePersister] = None,
        logger_: Optional[logging.Logger] = None,
    ) -> None:
        self._provider_registry = provider_registry or ProviderRegistry()
        self._persister = persister or MessagePersister()
        self._logger = logger_ or logger

    def chat(
        self,
        user_prompt: str,
        user_id: int,
        conversation_id: Optional[int],
        model_name: str,
    ) -> Generator[str, None, None]:

        start = time.monotonic()
        """
        Yields assistant tokens as they arrive. Persists both user and
        assistant messages (if streaming succeeds and tokens are produced).
        Handles fallback_model on ModelAccessError.
        """
        metadata = get_model_metadata(model_name)
        provider_key: Optional[str] = metadata.get("provider")
        if not provider_key:
            raise ValueError(f"No provider registered for model '{model_name}'")

        provider = self._provider_registry.get_provider(provider_key)
        system_prompt: str = metadata.get(
            "system_prompt", "You are an intelligent assistant."
        )
        fallback_model: Optional[str] = metadata.get("fallback_model")

        # Persist user message (SRP - extracted)
        self._persister.save_user(conversation_id, user_prompt, model_name)

        tokens: List[str] = []

        try:
            for token in provider.stream_response(
                message=user_prompt,
                user_id=user_id,
                conversation_id=conversation_id,
                model=model_name,
                system_prompt=system_prompt,
            ):
                tokens.append(token)
                yield token

        except ModelAccessError as err:
            self._logger.warning(
                "Model access error: user=%s conv=%s model=%s provider=%s error=%s",
                user_id,
                conversation_id,
                model_name,
                provider_key,
                err,
            )
            if fallback_model:
                self._logger.info(
                    "Retrying with fallback model '%s' for user=%s conv=%s",
                    fallback_model,
                    user_id,
                    conversation_id,
                )
                # Recursion is safe here (no unbounded chains in registry)
                yield from self.chat(
                    user_prompt, user_id, conversation_id, fallback_model
                )
                return
            raise

        except Exception as err:
            self._logger.error(
                "Provider error: user=%s conv=%s model=%s provider=%s error=%s",
                user_id,
                conversation_id,
                model_name,
                provider_key,
                err,
            )
            raise
        finally:
            elapsed = time.monotonic() - start
            self._logger.info(
                "AIStreamer: user=%s  conv=%s  model=%s  elapsed=%.2f seconds",
                user_id,
                conversation_id,
                model_name,
                elapsed,
            )

        # Persist assistant message (SRP - extracted)
        if tokens:
            assistant_text = "".join(tokens)
            self._persister.save_assistant(conversation_id, assistant_text, model_name)
