from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Dict, List, Optional, Any

from openai import OpenAI, Stream
from openai._exceptions import OpenAIError

from app.providers.base_provider import AIProvider
from app.services.conversation import get_conversation_messages
from app.model_registry import MODEL_REGISTRY

logger = logging.getLogger(__name__)


class ModelAccessError(RuntimeError):
    """Raised when the org is not verified or the model is otherwise unavailable."""


class _EndpointStrategy:
    """Encapsulates how to call a given OpenAI endpoint and iterate the stream."""

    def __init__(self, endpoint_name: str):
        self.endpoint_name = endpoint_name

    def create_stream(
        self,
        client: OpenAI,
        model: str,
        messages: List[Dict[str, str]],
    ) -> Stream:
        if self.endpoint_name == "chat":
            return client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
            )
        elif self.endpoint_name == "responses":
            return client.responses.create(
                model=model,
                input=messages,
                stream=True,
            )
        else:
            raise ValueError(f"Unknown strategy '{self.endpoint_name}'")


def build_strategy_registry() -> dict[str, _EndpointStrategy]:
    strat = {}
    for model, meta in MODEL_REGISTRY.items():
        if meta.get("provider") == "openai":
            endpoint = meta.get("openai_endpoint", "chat")
            strat[model] = _EndpointStrategy(endpoint)
    return strat


STRATEGY_REGISTRY: Dict[str, _EndpointStrategy] = build_strategy_registry()


class OpenAIProvider(AIProvider):
    """Streams tokens from any OpenAI model supported by the account."""

    def __init__(
        self,
        client: Optional[OpenAI] = None,
        strategy_registry: Optional[Dict[str, _EndpointStrategy]] = None,
    ):
        self.client: OpenAI = client or OpenAI()
        self.strategy_registry = strategy_registry or STRATEGY_REGISTRY

    def stream_response(
        self,
        message: str,
        user_id: int,
        conversation_id: Optional[int],
        model: str,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        logger.info(
            "OpenAIProvider: user=%s  conv=%s  model=%s",
            user_id,
            conversation_id,
            model,
        )

        messages = self._build_context(conversation_id, message, system_prompt)
        try:
            strategy = self.strategy_registry[model]
        except KeyError:
            raise ModelAccessError(
                f"Unknown or disabled model '{model}'. "
                "Check app.config['OPENAI_MODELS']."
            )
        try:
            stream = strategy.create_stream(self.client, model, messages)
            for chunk in stream:
                # 1. O3: handle response.output_text.delta event (OpenAI o3)
                if getattr(chunk, "type", None) == "response.output_text.delta":
                    text = getattr(chunk, "delta", None)
                    if text:
                        yield text
                        continue

                # 2. Legacy/fallback extraction (for gpt-4, gpt-3.5, etc)
                if hasattr(chunk, "choices"):
                    delta = chunk.choices[0].delta
                    text = getattr(delta, "text", None) or getattr(
                        delta, "content", None
                    )
                    if text:
                        yield text
                        continue

                delta = getattr(chunk, "delta", None)
                if isinstance(delta, dict):
                    text = delta.get("text") or delta.get("content")
                    if text:
                        yield text
                        continue
                elif isinstance(delta, str):
                    yield delta
                    continue

                # 3. Candidates structure for some O-model events
                cands = getattr(chunk, "candidates", None)
                if cands:
                    cand = cands[0]
                    delta = getattr(cand, "delta", None)
                    text = getattr(delta, "text", None) or getattr(
                        delta, "content", None
                    )
                    if text:
                        yield text
                        continue

        except OpenAIError as e:
            if getattr(e, "code", "") == "model_not_found":
                raise ModelAccessError(str(e)) from e
            logger.error("OpenAI error: %s", e)
            raise

    @staticmethod
    def _build_context(
        conversation_id: Optional[int],
        latest_user_msg: Optional[str],
        system_prompt: Optional[str],
    ) -> List[Dict[str, str]]:
        context: List[Dict[str, str]] = []
        if system_prompt:
            context.append({"role": "system", "content": system_prompt})

        if conversation_id:
            for msg in get_conversation_messages(conversation_id):
                if msg.role in ("user", "assistant"):
                    context.append({"role": msg.role, "content": msg.content})

        if latest_user_msg:
            context.append({"role": "user", "content": latest_user_msg})

        return context


# Optional: keep _extract_token as legacy/future helper,
# but **don't** collapse all in main flow
def _extract_token(chunk: Any) -> Optional[str]:
    text = getattr(chunk, "output_text", None)
    if text:
        return text
    delta = getattr(chunk, "delta", None)
    if delta:
        if isinstance(delta, dict):
            return delta.get("text") or delta.get("content")
        return getattr(delta, "text", None) or getattr(delta, "content", None)
    return None
