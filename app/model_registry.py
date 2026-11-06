"""The models Syvrona offers, and everything the chat path needs to know about each.

Keys are the providers' own API model IDs. Refreshed 2026-11-06 from each provider's
models, deprecations and migration pages; see the change record in ``docs/`` for the
sources and for what replaced each retired ID.

Entry fields:

``provider``           ``"openai"`` | ``"anthropic"`` | ``"gemini"``.
``display_name``       Shown in model selectors and the help pages.
``context_window``     Total tokens the model accepts per request (input + output).
``max_output_tokens``  Cap sent with every request; reserved out of the context window.
``generation_config``  Sampling settings. Current models mostly refuse them:
                       Claude 5.5 answers 400 to ``temperature``, ``top_p`` and
                       ``top_k``; Gemini 3.6+ and 4 ignore them; GPT-5/6-family
                       models accept ``temperature``/``top_p`` only with
                       ``reasoning_effort`` ``"none"``. Validation enforces this.
``options``            Provider-specific settings (OpenAI: ``endpoint``,
                       ``reasoning_effort``). Opaque to the chat service.
``system_prompt``      Optional; ``DEFAULT_SYSTEM_PROMPT`` otherwise.
``fallback_model``     Optional; tried when the provider says this model is unavailable.
                       Must be another registry key, and fallback chains must end.

``validate_registry()`` runs at import, so a bad entry stops the app from starting
instead of failing one chat request at a time.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DEFAULT_SYSTEM_PROMPT = "You are an intelligent assistant."

DEFAULT_MODEL_KEY = "gpt-6.1-sol"

MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    # -------------------- OpenAI (Responses API) -------------------- #
    "gpt-6-astra": {
        "provider": "openai",
        "display_name": "GPT-6 Astra",
        "context_window": 1_050_000,
        "max_output_tokens": 128_000,
        "generation_config": {},
        "options": {"endpoint": "responses"},
        "fallback_model": "gpt-6.1-sol",
    },
    "gpt-6.1-sol": {
        "provider": "openai",
        "display_name": "GPT-6.1 Sol",
        "context_window": 1_050_000,
        "max_output_tokens": 128_000,
        "generation_config": {},
        "options": {"endpoint": "responses"},
        "fallback_model": "gpt-6-luna",
    },
    "gpt-6-luna": {
        "provider": "openai",
        "display_name": "GPT-6 Luna",
        "context_window": 1_050_000,
        "max_output_tokens": 128_000,
        "generation_config": {},
        "options": {"endpoint": "responses"},
    },
    # -------------------- Anthropic (Messages API) -------------------- #
    "claude-opus-5-5": {
        "provider": "anthropic",
        "display_name": "Claude Opus 5.5",
        "context_window": 1_000_000,
        "max_output_tokens": 128_000,
        "generation_config": {},
        "options": {},
        "fallback_model": "claude-sonnet-5-5",
    },
    "claude-sonnet-5-5": {
        "provider": "anthropic",
        "display_name": "Claude Sonnet 5.5",
        "context_window": 1_000_000,
        "max_output_tokens": 128_000,
        "generation_config": {},
        "options": {},
        "fallback_model": "claude-haiku-5-5",
    },
    "claude-haiku-5-5": {
        "provider": "anthropic",
        "display_name": "Claude Haiku 5.5",
        "context_window": 1_000_000,
        "max_output_tokens": 128_000,
        "generation_config": {},
        "options": {},
    },
    # -------------------- Google Gemini (generateContent) -------------------- #
    "gemini-4-argon": {
        "provider": "gemini",
        "display_name": "Gemini 4 Argon",
        "context_window": 1_048_576,
        "max_output_tokens": 65_536,
        "generation_config": {},
        "options": {},
        "system_prompt": "You are a thorough and intelligent assistant.",
        "fallback_model": "gemini-3.8-flash",
    },
    "gemini-3.8-flash": {
        "provider": "gemini",
        "display_name": "Gemini 3.8 Flash",
        "context_window": 1_048_576,
        "max_output_tokens": 65_536,
        "generation_config": {},
        "options": {},
        "system_prompt": "You are a helpful and concise assistant.",
        "fallback_model": "gemini-3.5-flash-lite",
    },
    "gemini-3.5-flash-lite": {
        "provider": "gemini",
        "display_name": "Gemini 3.5 Flash-Lite",
        "context_window": 1_048_576,
        "max_output_tokens": 65_536,
        "generation_config": {},
        "options": {},
        "system_prompt": "You are a helpful and concise assistant.",
    },
}

_REQUIRED = ("provider", "display_name", "context_window", "max_output_tokens")
_KNOWN = frozenset(
    _REQUIRED + ("generation_config", "options", "system_prompt", "fallback_model")
)
_SAMPLING = {
    "openai": frozenset({"temperature", "top_p"}),
    "anthropic": frozenset(),
    "gemini": frozenset({"temperature", "top_p", "top_k"}),
}
_OPTIONS = {
    "openai": {
        "endpoint": frozenset({"responses", "chat"}),
        "reasoning_effort": frozenset(
            {"none", "minimal", "low", "medium", "high", "xhigh"}
        ),
    },
    "anthropic": {},
    "gemini": {},
}


class RegistryError(ValueError):
    """A registry entry is malformed."""


def validate_registry(
    registry: Mapping[str, Mapping[str, Any]], default_key: str
) -> None:
    """Raise ``RegistryError`` naming every problem in ``registry``."""
    problems: list[str] = []
    if default_key not in registry:
        problems.append(f"DEFAULT_MODEL_KEY {default_key!r} is not a registry key")

    for key, meta in registry.items():
        where = f"{key}:"
        missing = [f for f in _REQUIRED if f not in meta]
        if missing:
            problems.append(f"{where} missing {', '.join(missing)}")
            continue
        unknown = set(meta) - _KNOWN
        if unknown:
            problems.append(f"{where} unknown fields {sorted(unknown)}")
        provider = meta["provider"]
        if provider not in _SAMPLING:
            problems.append(f"{where} unknown provider {provider!r}")
            continue

        window, max_out = meta["context_window"], meta["max_output_tokens"]
        if not (isinstance(window, int) and isinstance(max_out, int)):
            problems.append(f"{where} token limits must be integers")
        elif not 0 < max_out < window:
            problems.append(f"{where} need 0 < max_output_tokens < context_window")

        sampling = set(meta.get("generation_config") or {})
        bad = sampling - _SAMPLING[provider]
        if bad:
            problems.append(f"{where} {provider} does not accept {sorted(bad)}")

        options = meta.get("options") or {}
        for opt, value in options.items():
            allowed = _OPTIONS[provider].get(opt)
            if allowed is None:
                problems.append(f"{where} unknown {provider} option {opt!r}")
            elif value not in allowed:
                problems.append(
                    f"{where} option {opt}={value!r} not in {sorted(allowed)}"
                )
        if (
            provider == "openai"
            and sampling
            and options.get("reasoning_effort") != "none"
        ):
            problems.append(
                f"{where} temperature/top_p need options.reasoning_effort = 'none'"
            )

        fallback = meta.get("fallback_model")
        if fallback is not None and fallback not in registry:
            problems.append(
                f"{where} fallback_model {fallback!r} is not a registry key"
            )

    for key in registry:
        seen = [key]
        nxt = registry[key].get("fallback_model")
        while nxt is not None and nxt in registry:
            if nxt in seen:
                problems.append(f"{key}: fallback cycle {' -> '.join(seen + [nxt])}")
                break
            seen.append(nxt)
            nxt = registry[nxt].get("fallback_model")

    if problems:
        raise RegistryError("Invalid model registry:\n  " + "\n  ".join(problems))


def is_known_model(model_name: str) -> bool:
    return model_name in MODEL_REGISTRY


def get_model_metadata(model_name: str) -> dict[str, Any]:
    """Return the entry for ``model_name``; ``KeyError`` if it is not offered."""
    return MODEL_REGISTRY[model_name]


validate_registry(MODEL_REGISTRY, DEFAULT_MODEL_KEY)
