"""The contract between the chat service and every model provider.

A provider is a pure I/O adapter. It receives one fully built ``ChatRequest``
(history already loaded, trimmed and ordered by ``AIStreamer``), translates it into
its SDK's call, and yields text deltas. It never touches the database or Flask.

Errors:

* ``ModelAccessError``: the model cannot serve this account right now (unknown,
  retired, not permitted, or rate limited). ``AIStreamer`` answers it by trying the
  registry entry's ``fallback_model``.
* ``ProviderError``: the provider reported a failure inside an otherwise healthy
  stream (for example an OpenAI ``error`` event). No fallback.
* SDK exceptions for everything else propagate unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal

# HTTP statuses that mean "this model is not available to us now", across providers.
MODEL_ACCESS_STATUS_CODES = frozenset({403, 404, 429})


class ModelAccessError(RuntimeError):
    """The requested model is unavailable to this account; try the fallback."""


class ProviderError(RuntimeError):
    """The provider reported a failure inside the stream."""


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """Everything a provider needs for one streamed reply.

    ``messages`` is oldest first, starts with a user turn and ends with the new
    user prompt. ``generation_config`` holds sampling settings and ``options`` holds
    provider-specific settings, both copied from the model's registry entry and
    validated there. ``user_id`` and ``conversation_id`` exist for structured logging.
    """

    model: str
    messages: Sequence[ChatMessage]
    system_prompt: str | None
    max_output_tokens: int
    generation_config: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    options: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    user_id: int | None = None
    conversation_id: int | None = None


class AIProvider(ABC):
    @abstractmethod
    def stream(self, request: ChatRequest) -> Iterator[str]:
        """Yield the reply as text deltas, in order."""
        raise NotImplementedError
