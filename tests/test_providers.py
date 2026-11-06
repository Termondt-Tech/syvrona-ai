"""Provider adapters translate one ChatRequest into one SDK call (D10)."""

from types import SimpleNamespace as NS

import anthropic
import httpx
import openai
import pytest
from google.genai import errors as genai_errors

from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base_provider import (
    ChatMessage,
    ChatRequest,
    ModelAccessError,
    ProviderError,
)
from app.providers.gemini_provider import GeminiProvider
from app.providers.openai_provider import OpenAIProvider

HISTORY = (
    ChatMessage("user", "q1"),
    ChatMessage("assistant", "a1"),
    ChatMessage("user", "q2"),
)


def request(**overrides):
    base = dict(
        model="m",
        messages=HISTORY,
        system_prompt="be brief",
        max_output_tokens=500,
        user_id=1,
        conversation_id=2,
    )
    base.update(overrides)
    return ChatRequest(**base)


def http_error(cls, status):
    req = httpx.Request("POST", "https://api.invalid")
    return cls("err", response=httpx.Response(status, request=req), body=None)


class FakeStream:
    """Context-managed iterable, like the SDKs' stream objects."""

    def __init__(self, events):
        self.events = events
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True

    def __iter__(self):
        for event in self.events:
            if isinstance(event, BaseException):
                raise event
            yield event


class Recorder:
    """Stands in for one SDK method: records kwargs, returns or raises."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


# ------------------------------------------------------------------ OpenAI
def openai_client(stream):
    responses = Recorder(stream)
    chat = Recorder(stream)
    client = NS(responses=NS(create=responses), chat=NS(completions=NS(create=chat)))
    return client, responses, chat


def test_openai_responses_request_and_text_deltas():
    stream = FakeStream(
        [
            NS(type="response.created"),
            NS(type="response.output_text.delta", delta="Hel"),
            NS(type="response.reasoning_summary_text.delta", delta="thinking"),
            NS(type="response.output_text.delta", delta="lo"),
            NS(type="response.completed"),
        ]
    )
    client, responses, _ = openai_client(stream)
    out = list(OpenAIProvider(client).stream(request()))
    assert out == ["Hel", "lo"]
    assert stream.closed
    kwargs = responses.calls[0]
    assert kwargs["model"] == "m"
    assert kwargs["instructions"] == "be brief"
    assert kwargs["store"] is False and kwargs["stream"] is True
    assert kwargs["max_output_tokens"] == 500
    assert kwargs["input"] == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
    ]
    assert "temperature" not in kwargs and "reasoning" not in kwargs


def test_openai_sampling_and_reasoning_are_forwarded_when_configured():
    client, responses, _ = openai_client(FakeStream([]))
    list(
        OpenAIProvider(client).stream(
            request(
                generation_config={"temperature": 0.2, "top_k": 5},
                options={"reasoning_effort": "none"},
            )
        )
    )
    kwargs = responses.calls[0]
    assert kwargs["temperature"] == 0.2
    assert "top_k" not in kwargs
    assert kwargs["reasoning"] == {"effort": "none"}


@pytest.mark.parametrize(
    "event",
    [
        NS(type="error", code="server_error", message="boom"),
        NS(
            type="response.failed",
            response=NS(error=NS(code="server_error", message="boom")),
        ),
    ],
)
def test_openai_in_stream_failure_raises_provider_error(event):
    client, _, _ = openai_client(
        FakeStream([NS(type="response.output_text.delta", delta="x"), event])
    )
    with pytest.raises(ProviderError):
        list(OpenAIProvider(client).stream(request()))


def test_openai_incomplete_response_keeps_the_text(caplog):
    incomplete = NS(
        type="response.incomplete",
        response=NS(incomplete_details=NS(reason="max_output_tokens")),
    )
    client, _, _ = openai_client(
        FakeStream([NS(type="response.output_text.delta", delta="x"), incomplete])
    )
    assert list(OpenAIProvider(client).stream(request())) == ["x"]
    assert "max_output_tokens" in caplog.text


@pytest.mark.parametrize(
    "cls, status, expected",
    [
        (openai.NotFoundError, 404, ModelAccessError),
        (openai.PermissionDeniedError, 403, ModelAccessError),
        (openai.RateLimitError, 429, ModelAccessError),
        (openai.InternalServerError, 500, openai.InternalServerError),
        (openai.BadRequestError, 400, openai.BadRequestError),
    ],
)
def test_openai_status_mapping(cls, status, expected):
    client, _, _ = openai_client(http_error(cls, status))
    with pytest.raises(expected):
        list(OpenAIProvider(client).stream(request()))


def test_openai_chat_endpoint():
    chunks = [
        NS(choices=[NS(delta=NS(content="Hi"))]),
        NS(choices=[]),
        NS(choices=[NS(delta=NS(content=None))]),
        NS(choices=[NS(delta=NS(content="!"))]),
    ]
    client, _, chat = openai_client(FakeStream(chunks))
    out = list(OpenAIProvider(client).stream(request(options={"endpoint": "chat"})))
    assert out == ["Hi", "!"]
    kwargs = chat.calls[0]
    assert kwargs["messages"][0] == {"role": "system", "content": "be brief"}
    assert kwargs["max_completion_tokens"] == 500


# ------------------------------------------------------------------ Anthropic
def anthropic_client(result):
    stream = Recorder(result)
    return NS(messages=NS(stream=stream)), stream


def delta(kind, **fields):
    return NS(type="content_block_delta", delta=NS(type=kind, **fields))


def test_anthropic_request_and_text_only():
    events = FakeStream(
        [
            NS(type="message_start"),
            delta("thinking_delta", thinking="hmm"),
            delta("text_delta", text="Hi"),
            delta("signature_delta", signature="sig"),
            delta("text_delta", text=" there"),
            NS(type="message_delta", delta=NS(stop_reason="end_turn")),
            NS(type="message_stop"),
        ]
    )
    client, stream = anthropic_client(events)
    out = list(
        AnthropicProvider(client).stream(request(generation_config={"temperature": 1}))
    )
    assert out == ["Hi", " there"]
    kwargs = stream.calls[0]
    assert kwargs == {
        "model": "m",
        "max_tokens": 500,
        "system": "be brief",
        "messages": [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
        ],
    }  # no sampling keys: the 2.x SDK and Claude 5.5 reject them


@pytest.mark.parametrize(
    "cls, status, expected",
    [
        (anthropic.NotFoundError, 404, ModelAccessError),
        (anthropic.PermissionDeniedError, 403, ModelAccessError),
        (anthropic.InternalServerError, 500, anthropic.InternalServerError),
    ],
)
def test_anthropic_status_mapping(cls, status, expected):
    client, _ = anthropic_client(http_error(cls, status))
    with pytest.raises(expected):
        list(AnthropicProvider(client).stream(request()))


# ------------------------------------------------------------------ Gemini
def gemini_client(result):
    call = Recorder(result)
    return NS(models=NS(generate_content_stream=call)), call


def test_gemini_request_roles_and_config():
    client, call = gemini_client([NS(text="Hi"), NS(text=None), NS(text="!")])
    out = list(
        GeminiProvider(client).stream(
            request(generation_config={"temperature": 0.4, "candidate_count": 2})
        )
    )
    assert out == ["Hi", "!"]
    kwargs = call.calls[0]
    assert [c.role for c in kwargs["contents"]] == ["user", "model", "user"]
    assert [c.parts[0].text for c in kwargs["contents"]] == ["q1", "a1", "q2"]
    config = kwargs["config"]
    assert config.system_instruction == "be brief"
    assert config.max_output_tokens == 500
    assert config.temperature == 0.4
    assert config.candidate_count is None


@pytest.mark.parametrize(
    "error, expected",
    [
        (genai_errors.ClientError(404, {"error": {"message": "x"}}), ModelAccessError),
        (genai_errors.ClientError(429, {"error": {"message": "x"}}), ModelAccessError),
        (
            genai_errors.ClientError(400, {"error": {"message": "x"}}),
            genai_errors.ClientError,
        ),
        (
            genai_errors.ServerError(503, {"error": {"message": "x"}}),
            genai_errors.ServerError,
        ),
    ],
)
def test_gemini_status_mapping(error, expected):
    client, _ = gemini_client(error)
    with pytest.raises(expected):
        list(GeminiProvider(client).stream(request()))
