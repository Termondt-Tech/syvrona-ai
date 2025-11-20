from __future__ import annotations

import logging
import time
from typing import Any, Dict, Generator, List, Optional, Tuple

from google import genai
from google.genai import types as genai_types
from google.api_core.exceptions import (
    GoogleAPICallError,
    NotFound,
    PermissionDenied,
    ResourceExhausted,
)

from app.providers.base_provider import AIProvider
from app.providers.openai_provider import ModelAccessError
from app.services.conversation import get_conversation_messages
from app.model_registry import get_model_metadata

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """
    Production Gemini provider for Syvrona using google-genai 1.51.0.

    - Uses google-genai Client + models.generate_content_stream.
    - Preserves conversation history with 'user' / 'assistant' mapped to
      'user' / 'model'.
    - Maps system_prompt → system_instruction in GenerateContentConfig.
    - Reads per-model `generation_config` from MODEL_REGISTRY and merges it
      into provider-level defaults.
    - DOES NOT enforce `max_tokens` for Gemini; the engine uses its own
      output limits unless you decide to add a cap later.
    """

    def __init__(
        self,
        client: Optional[genai.Client] = None,
        default_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Uses GEMINI_API_KEY / GOOGLE_API_KEY from env if set.
        self.client: genai.Client = client or genai.Client()

        # Provider-level defaults. Model-specific overrides will be merged in.
        self.default_config_dict: Dict[str, Any] = default_config or {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "candidate_count": 1,
        }

    def stream_response(
        self,
        message: str,
        user_id: int,
        conversation_id: Optional[int],
        model: str,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        logger.info(
            "GeminiProvider: user=%s conv=%s model=%s",
            user_id,
            conversation_id,
            model,
        )
        start = time.monotonic()

        # Look up model metadata (same key AIStreamer passes, e.g. "gemini-2.5-pro")
        meta = get_model_metadata(model)
        generation_overrides: Dict[str, Any] = meta.get("generation_config", {}) or {}

        contents, config = self._build_context_and_config(
            conversation_id=conversation_id,
            latest_user_msg=message,
            system_prompt=system_prompt,
            generation_overrides=generation_overrides,
        )

        try:
            # google-genai 1.51.0 accepts the short model name, e.g. "gemini-2.5-pro"
            stream = self.client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )

            for chunk in stream:
                text = getattr(chunk, "text", None)
                if text:
                    yield text

        # --- Errors where fallback makes sense -------------------------- #
        except (NotFound, PermissionDenied, ResourceExhausted) as e:
            logger.warning(
                "Gemini model access/quota error: user=%s conv=%s model=%s error=%s",
                user_id,
                conversation_id,
                model,
                e,
            )
            # Let AIStreamer handle fallback via `fallback_model`
            raise ModelAccessError(str(e)) from e

        # --- Other provider failures ----------------------------------- #
        except GoogleAPICallError as e:
            logger.error(
                "GeminiProvider API error: user=%s conv=%s model=%s error=%s",
                user_id,
                conversation_id,
                model,
                e,
            )
            raise

        except Exception as e:
            logger.error(
                "GeminiProvider unexpected error: user=%s conv=%s model=%s error=%s",
                user_id,
                conversation_id,
                model,
                e,
            )
            raise

        finally:
            elapsed = time.monotonic() - start
            logger.info(
                "GeminiProvider: user=%s conv=%s model=%s elapsed=%.2f",
                user_id,
                conversation_id,
                model,
                elapsed,
            )

    # ------------------------------------------------------------------ #
    #  Context + config builder                                         #
    # ------------------------------------------------------------------ #
    def _build_context_and_config(
        self,
        conversation_id: Optional[int],
        latest_user_msg: Optional[str],
        system_prompt: Optional[str],
        generation_overrides: Dict[str, Any],
    ) -> Tuple[List[genai_types.Content], genai_types.GenerateContentConfig]:
        contents: List[genai_types.Content] = []

        # 1) Conversation history from DB
        if conversation_id:
            for msg in get_conversation_messages(conversation_id):
                if msg.role not in ("user", "assistant"):
                    continue

                role = "user" if msg.role == "user" else "model"
                contents.append(
                    genai_types.Content(
                        role=role,
                        # Use Part(text=...) instead of Part.from_text(...)
                        parts=[genai_types.Part(text=msg.content)],
                    )
                )

        # 2) Latest user message
        if latest_user_msg:
            contents.append(
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=latest_user_msg)],
                )
            )

        # 3) Merge provider defaults + per-model overrides + system prompt
        cfg_kwargs: Dict[str, Any] = dict(self.default_config_dict)
        cfg_kwargs.update(generation_overrides or {})

        if system_prompt:
            cfg_kwargs["system_instruction"] = system_prompt

        config = genai_types.GenerateContentConfig(**cfg_kwargs)
        return contents, config
