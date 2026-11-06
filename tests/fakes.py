"""Test doubles for the model providers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from app.providers.base_provider import AIProvider, ChatRequest


class FakeProvider(AIProvider):
    """Streams a scripted reply per model and records every request.

    ``script[model]`` is either an exception (raised before any text) or a sequence
    whose items are yielded in order; an exception item is raised at that point,
    after the text before it has streamed.
    """

    DEFAULT_REPLY = ("Hello", ", ", "world")

    def __init__(self) -> None:
        self.script: dict[str, BaseException | Sequence[str | BaseException]] = {}
        self.requests: list[ChatRequest] = []

    def stream(self, request: ChatRequest) -> Iterator[str]:
        self.requests.append(request)
        action = self.script.get(request.model, self.DEFAULT_REPLY)
        if isinstance(action, BaseException):
            raise action
        for item in action:
            if isinstance(item, BaseException):
                raise item
            yield item
