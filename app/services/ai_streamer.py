"""The single boundary every model call crosses.

``AIStreamer.chat`` owns one chat turn end to end:

1. Load the conversation once and trim it, oldest first, to the model's input budget
   (D5). Providers receive the finished message list and never read the database.
2. Stream from the provider. If the provider says the model is unavailable before any
   text arrived, retry once per hop along the registry's ``fallback_model`` chain.
3. On success, save the user turn, the assistant turn and the usage increment in one
   transaction (D3, D4). On failure nothing is saved, so a retry does not leave an
   orphaned or duplicated user message; tokens already streamed are still charged.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from types import MappingProxyType
from typing import Any

from app.model_registry import DEFAULT_SYSTEM_PROMPT, get_model_metadata
from app.models import (
    Message,
    add_usage_tokens,
    db,
    get_conversation_messages,
    usage_period_start,
)
from app.providers.base_provider import (
    AIProvider,
    ChatMessage,
    ChatRequest,
    ModelAccessError,
    ProviderError,
)
from app.tokenizer import count_tokens

logger = logging.getLogger(__name__)

# Local counts approximate every provider's tokenizer (see app.tokenizer), so only
# three quarters of the window left after the output reservation is used for input.
CONTEXT_SAFETY_FACTOR = 0.75


class PromptTooLongError(ValueError):
    """The new prompt alone does not fit the model's input budget."""


# ---------------------------------------------------------------------- #
#  Providers                                                             #
# ---------------------------------------------------------------------- #
def _default_factories() -> dict[str, Callable[[], AIProvider]]:
    from app.providers.anthropic_provider import AnthropicProvider
    from app.providers.gemini_provider import GeminiProvider
    from app.providers.openai_provider import OpenAIProvider

    return {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
    }


class ProviderRegistry:
    """Builds each provider on first use and keeps it for the life of the process.

    Lazy construction means a missing API key breaks only that provider's models,
    and one SDK client (with its connection pool) serves every request.
    """

    def __init__(
        self, factories: Mapping[str, Callable[[], AIProvider]] | None = None
    ) -> None:
        self._factories = dict(factories or _default_factories())
        self._instances: dict[str, AIProvider] = {}
        self._lock = threading.Lock()

    @classmethod
    def of(cls, **providers: AIProvider) -> ProviderRegistry:
        """A registry over ready-made instances (tests, scripts)."""
        return cls({key: (lambda p=p: p) for key, p in providers.items()})

    def get(self, key: str) -> AIProvider:
        instance = self._instances.get(key)
        if instance is not None:
            return instance
        with self._lock:
            if key not in self._instances:
                try:
                    factory = self._factories[key]
                except KeyError as exc:
                    raise ValueError(f"No provider registered for {key!r}") from exc
                self._instances[key] = factory()
            return self._instances[key]


# ---------------------------------------------------------------------- #
#  Context budget                                                        #
# ---------------------------------------------------------------------- #
def input_token_budget(meta: Mapping[str, Any]) -> int:
    return int(
        (meta["context_window"] - meta["max_output_tokens"]) * CONTEXT_SAFETY_FACTOR
    )


def system_prompt_for(meta: Mapping[str, Any]) -> str:
    return meta.get("system_prompt") or DEFAULT_SYSTEM_PROMPT


def fit_history(
    history: Sequence[ChatMessage], prompt: str, budget: int, system_prompt: str
) -> list[ChatMessage]:
    """Return the newest turns that fit ``budget``, then the new prompt.

    The result starts on a user turn (Anthropic and Gemini expect that) and always
    ends with ``prompt``. Raises ``PromptTooLongError`` if the prompt alone is over.
    """
    remaining = budget - count_tokens(system_prompt) - count_tokens(prompt)
    if remaining < 0:
        raise PromptTooLongError("The message is too long for this model.")
    kept: list[ChatMessage] = []
    for message in reversed(history):
        cost = count_tokens(message.content)
        if cost > remaining:
            break
        kept.append(message)
        remaining -= cost
    kept.reverse()
    while kept and kept[0].role != "user":
        kept.pop(0)
    return [*kept, ChatMessage("user", prompt)]


# ---------------------------------------------------------------------- #
#  Main streamer                                                         #
# ---------------------------------------------------------------------- #
class AIStreamer:
    """Facade for provider selection, streaming, fallback, persistence and quota."""

    def __init__(
        self,
        providers: ProviderRegistry,
        logger_: logging.Logger | None = None,
    ) -> None:
        self._providers = providers
        self._log = logger_ or logger

    @staticmethod
    def check_prompt(prompt: str, model_name: str) -> None:
        """Raise ``PromptTooLongError`` before streaming, while a 4xx is possible."""
        meta = get_model_metadata(model_name)
        fit_history((), prompt, input_token_budget(meta), system_prompt_for(meta))

    def chat(
        self,
        user_prompt: str,
        user_id: int,
        conversation_id: int,
        model_name: str,
    ) -> Iterator[str]:
        history = [
            ChatMessage(m.role, m.content)
            for m in get_conversation_messages(conversation_id)
            if m.role in ("user", "assistant")
        ]
        # End the read transaction so no pooled connection is held while the
        # provider streams, which can take minutes.
        db.session.commit()

        start = time.monotonic()
        model, outcome = model_name, "error"
        streamed: list[str] = []
        try:
            while True:
                meta = get_model_metadata(model)
                request = self._build_request(
                    meta, model, history, user_prompt, user_id, conversation_id
                )
                provider = self._providers.get(meta["provider"])
                try:
                    for delta in provider.stream(request):
                        streamed.append(delta)
                        yield delta
                except ModelAccessError as err:
                    fallback = meta.get("fallback_model")
                    if streamed or not fallback:
                        raise
                    self._log.warning(
                        "Model unavailable, falling back: user=%s conv=%s model=%s "
                        "fallback=%s error=%s",
                        user_id,
                        conversation_id,
                        model,
                        fallback,
                        err,
                    )
                    model = fallback
                    continue
                break

            reply = "".join(streamed)
            if not reply:
                raise ProviderError(f"{model} returned an empty reply")
            self._save_turn(conversation_id, user_id, model, user_prompt, reply)
            outcome = "ok"
        except BaseException as err:
            # BaseException: a client disconnect closes this generator with
            # GeneratorExit, and the tokens already streamed were still billed.
            if not isinstance(err, GeneratorExit):
                self._log.error(
                    "Chat turn failed: user=%s conv=%s model=%s error=%r",
                    user_id,
                    conversation_id,
                    model,
                    err,
                )
            self._charge_partial(user_id, user_prompt, streamed)
            raise
        finally:
            self._log.info(
                "AIStreamer: user=%s conv=%s model=%s requested=%s outcome=%s "
                "elapsed=%.2f",
                user_id,
                conversation_id,
                model,
                model_name,
                outcome,
                time.monotonic() - start,
            )

    # ------------------------------------------------------------------ #
    def _build_request(
        self,
        meta: Mapping[str, Any],
        model: str,
        history: Sequence[ChatMessage],
        prompt: str,
        user_id: int,
        conversation_id: int,
    ) -> ChatRequest:
        system_prompt = system_prompt_for(meta)
        return ChatRequest(
            model=model,
            messages=tuple(
                fit_history(history, prompt, input_token_budget(meta), system_prompt)
            ),
            system_prompt=system_prompt,
            max_output_tokens=meta["max_output_tokens"],
            generation_config=MappingProxyType(
                dict(meta.get("generation_config") or {})
            ),
            options=MappingProxyType(dict(meta.get("options") or {})),
            user_id=user_id,
            conversation_id=conversation_id,
        )

    @staticmethod
    def _save_turn(
        conversation_id: int, user_id: int, model: str, prompt: str, reply: str
    ) -> None:
        # Added in order, so the user row gets the lower id: the tiebreak when both
        # rows share a created_at second.
        db.session.add(
            Message(
                conversation_id=conversation_id,
                role="user",
                content=prompt,
                model=model,
            )
        )
        db.session.add(
            Message(
                conversation_id=conversation_id,
                role="assistant",
                content=reply,
                model=model,
            )
        )
        add_usage_tokens(
            user_id, count_tokens(prompt) + count_tokens(reply), usage_period_start()
        )
        db.session.commit()

    def _charge_partial(self, user_id: int, prompt: str, streamed: list[str]) -> None:
        """Charge a failed turn for what was streamed; never mask the real error."""
        if not streamed:
            return
        try:
            db.session.rollback()
            add_usage_tokens(
                user_id,
                count_tokens(prompt) + count_tokens("".join(streamed)),
                usage_period_start(),
            )
            db.session.commit()
        except Exception:  # pragma: no cover - logged, then the original error wins
            db.session.rollback()
            self._log.exception(
                "Could not record usage for a failed turn: user=%s", user_id
            )
