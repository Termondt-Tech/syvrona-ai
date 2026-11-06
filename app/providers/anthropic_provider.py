"""Anthropic adapter (anthropic>=2.3, Messages API, streaming).

The 2.x SDK no longer accepts ``temperature``, ``top_p`` or ``top_k``, so Anthropic
registry entries carry no sampling settings and the registry rejects any. Only text
deltas are forwarded: thinking, signature and tool deltas carry no ``text``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from anthropic import Anthropic, APIStatusError

from app.providers.base_provider import (
    MODEL_ACCESS_STATUS_CODES,
    AIProvider,
    ChatRequest,
    ModelAccessError,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(AIProvider):
    def __init__(self, client: Anthropic | None = None) -> None:
        # Reads ANTHROPIC_API_KEY from the environment.
        self._client = client or Anthropic()

    def stream(self, request: ChatRequest) -> Iterator[str]:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_output_tokens,
            "messages": [
                {"role": m.role, "content": m.content} for m in request.messages
            ],
        }
        if request.system_prompt:
            kwargs["system"] = request.system_prompt

        try:
            with self._client.messages.stream(**kwargs) as stream:
                for event in stream:
                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta" and event.delta.text:
                            yield event.delta.text
                    elif event.type == "message_delta":
                        if event.delta.stop_reason == "max_tokens":
                            logger.warning(
                                "Anthropic reply hit max_tokens: "
                                "user=%s conv=%s model=%s",
                                request.user_id,
                                request.conversation_id,
                                request.model,
                            )
        except APIStatusError as err:
            if err.status_code in MODEL_ACCESS_STATUS_CODES:
                raise ModelAccessError(str(err)) from err
            raise
