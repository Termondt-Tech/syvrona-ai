"""OpenAI adapter: the Responses API by default, Chat Completions on request.

Registry ``options`` for OpenAI entries:

* ``endpoint``: ``"responses"`` (default) or ``"chat"``.
* ``reasoning_effort``: forwarded as ``reasoning={"effort": ...}`` on the Responses
  API. GPT-5-family models accept ``temperature``/``top_p`` only when the effort is
  ``"none"``; the registry enforces that pairing.

Responses are created with ``store=False``: Syvrona keeps its own history, so there is
no reason to leave a copy of every conversation on OpenAI's side.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from openai import APIStatusError, OpenAI

from app.providers.base_provider import (
    MODEL_ACCESS_STATUS_CODES,
    AIProvider,
    ChatRequest,
    ModelAccessError,
    ProviderError,
)

logger = logging.getLogger(__name__)

SAMPLING_KEYS = ("temperature", "top_p")


class OpenAIProvider(AIProvider):
    def __init__(self, client: OpenAI | None = None) -> None:
        self._client = client or OpenAI()

    def stream(self, request: ChatRequest) -> Iterator[str]:
        endpoint = request.options.get("endpoint", "responses")
        try:
            if endpoint == "responses":
                yield from self._stream_responses(request)
            elif endpoint == "chat":
                yield from self._stream_chat(request)
            else:
                raise ValueError(f"Unknown OpenAI endpoint {endpoint!r}")
        except APIStatusError as err:
            if err.status_code in MODEL_ACCESS_STATUS_CODES:
                raise ModelAccessError(str(err)) from err
            raise

    def _stream_responses(self, request: ChatRequest) -> Iterator[str]:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "input": [{"role": m.role, "content": m.content} for m in request.messages],
            "max_output_tokens": request.max_output_tokens,
            "store": False,
            "stream": True,
        }
        if request.system_prompt:
            kwargs["instructions"] = request.system_prompt
        if effort := request.options.get("reasoning_effort"):
            kwargs["reasoning"] = {"effort": effort}
        kwargs.update(_sampling(request))

        with self._client.responses.create(**kwargs) as stream:
            for event in stream:
                if event.type == "response.output_text.delta":
                    if event.delta:
                        yield event.delta
                elif event.type == "error":
                    raise ProviderError(
                        f"OpenAI stream error {event.code}: {event.message}"
                    )
                elif event.type == "response.failed":
                    error = event.response.error
                    detail = f"{error.code}: {error.message}" if error else "unknown"
                    raise ProviderError(f"OpenAI response failed: {detail}")
                elif event.type == "response.incomplete":
                    details = event.response.incomplete_details
                    logger.warning(
                        "OpenAI response incomplete: "
                        "user=%s conv=%s model=%s reason=%s",
                        request.user_id,
                        request.conversation_id,
                        request.model,
                        details.reason if details else "unknown",
                    )

    def _stream_chat(self, request: ChatRequest) -> Iterator[str]:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages += [{"role": m.role, "content": m.content} for m in request.messages]
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_completion_tokens": request.max_output_tokens,
            "stream": True,
        }
        kwargs.update(_sampling(request))

        with self._client.chat.completions.create(**kwargs) as stream:
            for chunk in stream:
                if chunk.choices and (content := chunk.choices[0].delta.content):
                    yield content


def _sampling(request: ChatRequest) -> dict[str, Any]:
    return {
        k: request.generation_config[k]
        for k in SAMPLING_KEYS
        if k in request.generation_config
    }
