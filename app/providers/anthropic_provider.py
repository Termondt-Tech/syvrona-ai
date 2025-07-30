# app/providers/anthropic_provider.py
# --- top of file ---
from __future__ import annotations
from anthropic.types import (
    MessageStreamEvent,  # ← union of all possible events
    ContentBlockDeltaEvent,  # ← the one that contains tokens
)

import time
import logging
import os
from collections.abc import Generator
from typing import Dict, List

from anthropic import Anthropic, APIConnectionError, APIStatusError

from app.providers.base_provider import AIProvider
from app.services.conversation import get_conversation_messages
from app.model_registry import get_model_metadata

logger = logging.getLogger(__name__)


class AnthropicProvider(AIProvider):
    """
    Streams tokens from any Claude‑3 model.

    Matches the interface used by AIStreamer:
        stream_response(message, user_id, conversation_id, model, system_prompt=...)
    """

    def __init__(self, *, client: Anthropic | None = None) -> None:
        # Dependency‑injectable for tests
        self.client: Anthropic = client or Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )

    # ------------------------------------------------------------------ #
    #  Public method required by AIStreamer                               #
    # ------------------------------------------------------------------ #

    def stream_response(
        self,
        message: str,
        user_id: int,
        conversation_id: int | None,
        model: str,
        system_prompt: str | None = None,
    ) -> Generator[str, None, None]:
        logger.info(
            "AnthropicProvider: user=%s  conv=%s  model=%s",
            user_id,
            conversation_id,
            model,
        )

        start = time.monotonic()

        # ---------- build message list ---------- #
        msg_history: List[Dict[str, str]] = [
            {"role": m.role, "content": m.content}
            for m in get_conversation_messages(conversation_id)
            if m.role in ("user", "assistant")
        ]
        if message:
            msg_history.append({"role": "user", "content": message})

        # ---------- pull per‑model defaults ---------- #
        metadata = get_model_metadata(model)
        max_tokens: int = metadata.get("max_tokens", 4096)
        temperature: float | None = metadata.get("temperature")

        # ---------- use caller‑supplied system prompt if provided ---------- #
        system_prompt = system_prompt or metadata.get(
            "system_prompt", "You are an intelligent assistant."
        )

        # ---------- stream! ---------- #
        try:
            stream_kwargs = dict(
                model=model,
                system=system_prompt,
                messages=msg_history,
                max_tokens=max_tokens,
            )
            if temperature is not None:
                stream_kwargs["temperature"] = temperature

            stream_ctx = self.client.messages.stream(**stream_kwargs)

            with stream_ctx as stream:
                for event in stream:
                    text = _extract_text_from_event(event)
                    if text:
                        yield text

        except (APIConnectionError, APIStatusError) as err:
            # Surface Anthropic‑specific errors so AIStreamer can handle/log them
            logger.error(
                "AnthropicProvider error: user=%s conv=%s model=%s error=%s",
                user_id,
                conversation_id,
                model,
                err,
            )
            raise
        finally:
            elapsed = time.monotonic() - start
            logger.info(
                "AnthropicProvider: user=%s  conv=%s  model=%s  elapsed=%.2f seconds",
                user_id,
                conversation_id,
                model,
                elapsed,
            )


# ---------------------------------------------------------------------- #
#  Helper for the new Claude‑3 event schema                              #
# ---------------------------------------------------------------------- #


def _extract_text_from_event(event: MessageStreamEvent) -> str | None:
    """
    Return the token string only for ContentBlockDeltaEvent.
    All other event types are ignored.
    """
    if isinstance(event, ContentBlockDeltaEvent):
        return event.delta.text  # ✔ correct for 0.52.0
    return None
