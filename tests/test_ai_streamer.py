"""AIStreamer: one history load, budgets, fallback, atomic persistence (D3-D6)."""

from datetime import UTC, datetime

import pytest

from app import db
from app.models import (
    Conversation,
    Message,
    UsageStat,
    get_conversation_messages,
    usage_period_start,
)
from app.providers.base_provider import ChatMessage, ModelAccessError, ProviderError
from app.services import ai_streamer
from app.services.ai_streamer import (
    AIStreamer,
    PromptTooLongError,
    ProviderRegistry,
    fit_history,
)
from app.tokenizer import count_tokens


@pytest.fixture
def conversation(create_user):
    user = create_user(subscription_status="active")
    convo = Conversation(user_id=user.id, title="t")
    db.session.add(convo)
    db.session.commit()
    return convo


@pytest.fixture
def streamer(app):
    return AIStreamer(app.extensions["ai_providers"])


def run(streamer, convo, prompt="Hi there", model="gpt-6.1-sol"):
    return "".join(streamer.chat(prompt, convo.user_id, convo.id, model))


def rows(convo):
    return [
        (m.role, m.content, m.model)
        for m in Message.query.filter_by(conversation_id=convo.id).order_by(
            Message.created_at, Message.id
        )
    ]


def usage(user_id):
    stat = UsageStat.query.filter_by(
        user_id=user_id, period_start=usage_period_start()
    ).first()
    return stat.tokens if stat else 0


# ---------------------------------------------------------------- history fit
def test_fit_history_keeps_newest_turns_that_fit_and_starts_on_user():
    history = [
        ChatMessage("user", "one " * 50),
        ChatMessage("assistant", "two " * 50),
        ChatMessage("user", "three"),
        ChatMessage("assistant", "four"),
    ]
    budget = count_tokens("sys") + count_tokens("new") + 10
    result = fit_history(history, "new", budget, "sys")
    assert [m.content for m in result] == ["three", "four", "new"]
    assert result[0].role == "user"


def test_fit_history_drops_a_leading_assistant_turn():
    history = [ChatMessage("user", "q " * 200), ChatMessage("assistant", "a")]
    budget = count_tokens("s") + count_tokens("new") + 5
    assert [m.content for m in fit_history(history, "new", budget, "s")] == ["new"]


def test_fit_history_rejects_a_prompt_over_budget():
    with pytest.raises(PromptTooLongError):
        fit_history([], "word " * 100, 10, "sys")


# ---------------------------------------------------------------- success path
def test_success_saves_both_turns_and_usage_atomically(streamer, conversation):
    assert run(streamer, conversation) == "Hello, world"
    assert rows(conversation) == [
        ("user", "Hi there", "gpt-6.1-sol"),
        ("assistant", "Hello, world", "gpt-6.1-sol"),
    ]
    assert usage(conversation.user_id) == count_tokens("Hi there") + count_tokens(
        "Hello, world"
    )


def test_usage_accumulates_across_turns(streamer, conversation):
    run(streamer, conversation, "first")
    run(streamer, conversation, "second")
    expected = sum(count_tokens(t) for t in ("first", "second")) + 2 * count_tokens(
        "Hello, world"
    )
    assert usage(conversation.user_id) == expected
    assert UsageStat.query.count() == 1


def test_prompt_is_sent_exactly_once_with_prior_history(
    streamer, conversation, fake_provider
):
    run(streamer, conversation, "first")
    run(streamer, conversation, "second")
    sent = [m.content for m in fake_provider.requests[-1].messages]
    assert sent == ["first", "Hello, world", "second"]


def test_request_carries_registry_settings(streamer, conversation, fake_provider):
    run(streamer, conversation, model="claude-sonnet-5-5")
    request = fake_provider.requests[-1]
    assert request.model == "claude-sonnet-5-5"
    assert request.max_output_tokens == 128_000
    assert request.system_prompt
    assert request.user_id == conversation.user_id
    assert request.conversation_id == conversation.id


def test_same_second_rows_keep_user_before_assistant(streamer, conversation):
    frozen = datetime(2026, 11, 6, 12, 0, 0, tzinfo=UTC)
    run(streamer, conversation)
    Message.query.update({Message.created_at: frozen})
    db.session.commit()
    roles = [m.role for m in get_conversation_messages(conversation.id)]
    assert roles == ["user", "assistant"]


# ---------------------------------------------------------------- failures
def test_failure_before_any_text_saves_and_charges_nothing(
    streamer, conversation, fake_provider
):
    fake_provider.script["gpt-6.1-sol"] = RuntimeError("down")
    with pytest.raises(RuntimeError):
        run(streamer, conversation)
    assert rows(conversation) == []
    assert usage(conversation.user_id) == 0


def test_mid_stream_failure_saves_nothing_but_charges_streamed_tokens(
    streamer, conversation, fake_provider
):
    fake_provider.script["gpt-6.1-sol"] = ["partial ", RuntimeError("cut")]
    received = []
    with pytest.raises(RuntimeError):
        for delta in streamer.chat(
            "Hi", conversation.user_id, conversation.id, "gpt-6.1-sol"
        ):
            received.append(delta)
    assert received == ["partial "]
    assert rows(conversation) == []
    assert usage(conversation.user_id) == count_tokens("Hi") + count_tokens("partial ")


def test_client_disconnect_charges_streamed_tokens(streamer, conversation):
    gen = streamer.chat("Hi", conversation.user_id, conversation.id, "gpt-6.1-sol")
    assert next(gen) == "Hello"
    gen.close()
    assert rows(conversation) == []
    assert usage(conversation.user_id) == count_tokens("Hi") + count_tokens("Hello")


def test_empty_reply_is_a_failure(streamer, conversation, fake_provider):
    fake_provider.script["gpt-6.1-sol"] = []
    with pytest.raises(ProviderError):
        run(streamer, conversation)
    assert rows(conversation) == []


# ---------------------------------------------------------------- fallback (D6)
def test_model_access_error_falls_back_along_the_chain(
    streamer, conversation, fake_provider
):
    fake_provider.script["gemini-4-argon"] = ModelAccessError("retired")
    fake_provider.script["gemini-3.8-flash"] = ModelAccessError("quota")
    assert run(streamer, conversation, model="gemini-4-argon") == "Hello, world"
    assert [r.model for r in fake_provider.requests] == [
        "gemini-4-argon",
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
    ]
    # One user row, not one per attempt; both rows name the model that answered.
    assert rows(conversation) == [
        ("user", "Hi there", "gemini-3.5-flash-lite"),
        ("assistant", "Hello, world", "gemini-3.5-flash-lite"),
    ]


def test_end_of_chain_model_access_error_propagates(
    streamer, conversation, fake_provider
):
    fake_provider.script["gpt-6-luna"] = ModelAccessError("gone")
    with pytest.raises(ModelAccessError):
        run(streamer, conversation, model="gpt-6-luna")
    assert rows(conversation) == []


def test_no_fallback_after_text_has_streamed(streamer, conversation, fake_provider):
    fake_provider.script["gpt-6-astra"] = ["half", ModelAccessError("late")]
    with pytest.raises(ModelAccessError):
        run(streamer, conversation, model="gpt-6-astra")
    assert [r.model for r in fake_provider.requests] == ["gpt-6-astra"]


def test_check_prompt_uses_the_model_budget(monkeypatch):
    monkeypatch.setattr(ai_streamer, "input_token_budget", lambda meta: 20)
    AIStreamer.check_prompt("short", "gpt-6.1-sol")
    with pytest.raises(PromptTooLongError):
        AIStreamer.check_prompt("word " * 50, "gpt-6.1-sol")


# ---------------------------------------------------------------- registry
def test_provider_registry_builds_each_provider_once():
    calls = []

    def factory():
        calls.append(1)
        return object()

    registry = ProviderRegistry({"openai": factory})
    assert registry.get("openai") is registry.get("openai")
    assert len(calls) == 1
    with pytest.raises(ValueError, match="No provider registered"):
        registry.get("gemini")


def test_default_registry_does_not_build_sdk_clients_up_front():
    registry = ProviderRegistry()
    assert registry._instances == {}
