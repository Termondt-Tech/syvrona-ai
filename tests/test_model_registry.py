"""The model registry validates itself (D6, D7) and carries current models only."""

import copy

import pytest

from app.model_registry import (
    DEFAULT_MODEL_KEY,
    MODEL_REGISTRY,
    RegistryError,
    validate_registry,
)

RETIRED_IDS = {
    "gpt-3.5-turbo",
    "gpt-5.2-chat-latest",
    "gpt-5.1-2025-11-13",
    "gpt-5.1-codex",
    "claude-sonnet-4-5-20250929",
    "claude-opus-4-5-20251101",
    "claude-haiku-4-5-20251001",
    "gemini-3-pro-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
}


def entry(**overrides):
    base = {
        "provider": "openai",
        "display_name": "X",
        "context_window": 1000,
        "max_output_tokens": 100,
        "generation_config": {},
        "options": {},
    }
    base.update(overrides)
    return base


def test_shipped_registry_is_valid():
    validate_registry(MODEL_REGISTRY, DEFAULT_MODEL_KEY)
    assert DEFAULT_MODEL_KEY in MODEL_REGISTRY


def test_no_retired_model_ids():
    assert RETIRED_IDS.isdisjoint(MODEL_REGISTRY)


def test_every_fallback_chain_ends_on_a_registry_entry():
    for key, meta in MODEL_REGISTRY.items():
        seen = {key}
        nxt = meta.get("fallback_model")
        while nxt is not None:
            assert nxt in MODEL_REGISTRY, f"{key} falls back to unknown {nxt}"
            assert nxt not in seen
            seen.add(nxt)
            nxt = MODEL_REGISTRY[nxt].get("fallback_model")


def test_three_providers_offered():
    assert {m["provider"] for m in MODEL_REGISTRY.values()} == {
        "openai",
        "anthropic",
        "gemini",
    }


@pytest.mark.parametrize(
    "registry, default, message",
    [
        ({"a": entry()}, "missing", "DEFAULT_MODEL_KEY"),
        ({"a": entry(fallback_model="gone")}, "a", "fallback_model 'gone'"),
        (
            {"a": entry(fallback_model="b"), "b": entry(fallback_model="a")},
            "a",
            "fallback cycle",
        ),
        ({"a": entry(provider="nope")}, "a", "unknown provider"),
        (
            {"a": entry(max_output_tokens=1000)},
            "a",
            "max_output_tokens < context_window",
        ),
        (
            {"a": entry(provider="anthropic", generation_config={"temperature": 0.5})},
            "a",
            "anthropic does not accept",
        ),
        (
            {"a": entry(generation_config={"temperature": 0.5})},
            "a",
            "reasoning_effort = 'none'",
        ),
        ({"a": entry(options={"endpoint": "completions"})}, "a", "option endpoint"),
        ({"a": entry(options={"speed": "fast"})}, "a", "unknown openai option"),
        ({"a": entry(encoding="cl100k_base")}, "a", "unknown fields"),
        ({"a": {"provider": "openai"}}, "a", "missing display_name"),
    ],
)
def test_validation_rejects(registry, default, message):
    with pytest.raises(RegistryError, match=message):
        validate_registry(registry, default)


def test_openai_sampling_allowed_with_reasoning_effort_none():
    registry = {
        "a": entry(
            generation_config={"temperature": 0.2},
            options={"reasoning_effort": "none"},
        )
    }
    validate_registry(registry, "a")


def test_validation_does_not_mutate_registry():
    before = copy.deepcopy(MODEL_REGISTRY)
    validate_registry(MODEL_REGISTRY, DEFAULT_MODEL_KEY)
    assert MODEL_REGISTRY == before
