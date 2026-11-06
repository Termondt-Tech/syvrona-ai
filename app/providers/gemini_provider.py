"""Gemini adapter (google-genai>=2.34, ``models.generate_content_stream``).

History roles map ``user`` to ``user`` and ``assistant`` to ``model``; the system
prompt becomes ``system_instruction``. The SDK raises ``google.genai.errors.APIError``
(``ClientError`` for 4xx, ``ServerError`` for 5xx) with the HTTP status in ``code``.
The adapter previously caught ``google.api_core`` exceptions, which this SDK never
raises, so the Gemini fallback could not fire.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.providers.base_provider import (
    MODEL_ACCESS_STATUS_CODES,
    AIProvider,
    ChatRequest,
    ModelAccessError,
)

SAMPLING_KEYS = ("temperature", "top_p", "top_k")


class GeminiProvider(AIProvider):
    def __init__(self, client: genai.Client | None = None) -> None:
        # Reads GEMINI_API_KEY (or GOOGLE_API_KEY) from the environment.
        self._client = client or genai.Client()

    def stream(self, request: ChatRequest) -> Iterator[str]:
        contents = [
            genai_types.Content(
                role="user" if m.role == "user" else "model",
                parts=[genai_types.Part(text=m.content)],
            )
            for m in request.messages
        ]
        config_kwargs: dict[str, Any] = {
            k: request.generation_config[k]
            for k in SAMPLING_KEYS
            if k in request.generation_config
        }
        config_kwargs["max_output_tokens"] = request.max_output_tokens
        if request.system_prompt:
            config_kwargs["system_instruction"] = request.system_prompt

        try:
            for chunk in self._client.models.generate_content_stream(
                model=request.model,
                contents=contents,
                config=genai_types.GenerateContentConfig(**config_kwargs),
            ):
                if text := chunk.text:
                    yield text
        except genai_errors.APIError as err:
            if err.code in MODEL_ACCESS_STATUS_CODES:
                raise ModelAccessError(str(err)) from err
            raise
