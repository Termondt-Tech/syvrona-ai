# app/providers/anthropic_provider.py
from __future__ import annotations
from anthropic.types import (
    MessageStreamEvent,
    ContentBlockDeltaEvent,
)

import time
import logging
import os
from collections.abc import Generator
from typing import Dict, List, Any

from anthropic import Anthropic, APIConnectionError, APIStatusError

from app.providers.base_provider import AIProvider
from app.services.conversation import get_conversation_messages
from app.model_registry import get_model_metadata

logger = logging.getLogger(__name__)


class AnthropicProvider(AIProvider):
    """
    Streams tokens from any Claude-3/4 model.

    Matches the interface used by AIStreamer:
        stream_response(message, user_id, conversation_id, model, system_prompt=...)
    """

    def __init__(self, *, client: Anthropic | None = None) -> None:
        self.client: Anthropic = client or Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )

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

        # ---------- per-model config ---------- #
        metadata: Dict[str, Any] = get_model_metadata(model) or {}

        # Hard cap from registry (existing pattern)
        max_tokens: int = metadata.get("max_tokens", 4096)

        # New: generation_config (temperature, top_p, etc.)
        gen_cfg: Dict[str, Any] = metadata.get("generation_config", {}) or {}
        temperature: float | None = gen_cfg.get("temperature")
        top_p: float | None = gen_cfg.get("top_p")

        # Anthropic: cannot specify both temperature and top_p
        if temperature is not None and top_p is not None:
            logger.warning(
                "AnthropicProvider: both temperature and top_p specified for model=%s; "
                "Anthropic does not allow both. Using temperature and ignoring top_p.",
                model,
            )
            top_p = None

        # System prompt: caller overrides registry default
        system_prompt = system_prompt or metadata.get(
            "system_prompt", "You are an intelligent assistant."
        )

        # ---------- stream ---------- #
        try:
            stream_kwargs: Dict[str, Any] = dict(
                model=model,
                system=system_prompt,
                messages=msg_history,
                max_tokens=max_tokens,
            )
            if temperature is not None:
                stream_kwargs["temperature"] = temperature
            if top_p is not None:
                stream_kwargs["top_p"] = top_p

            stream_ctx = self.client.messages.stream(**stream_kwargs)

            with stream_ctx as stream:
                for event in stream:
                    text = _extract_text_from_event(event)
                    if text:
                        yield text

        except (APIConnectionError, APIStatusError) as err:
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


def _extract_text_from_event(event: MessageStreamEvent) -> str | None:
    if isinstance(event, ContentBlockDeltaEvent):
        return event.delta.text
    return None
