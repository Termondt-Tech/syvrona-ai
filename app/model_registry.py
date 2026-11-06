"""
MODEL CONFIGURATION & TUNING REFERENCE
--------------------------------------

This registry exposes each model's **sampling defaults** so developers can:

    • See, at a glance, how the model is configured by default
    • Override behavior in a controlled, explicit way
    • Keep model identity (provider, endpoint, encoding) separate from tuning

The values in `generation_config` are chosen to match the *provider defaults*
as closely as possible at the time of writing:

    OpenAI  : temperature = 1.0, top_p = 1.0
    Anthropic (Claude) : temperature = 1.0, top_p = 1.0
    Gemini  : temperature = 1.0, top_p ≈ 0.95, top_k = 64, candidate_count = 1

If a provider changes their documented defaults in the future, we should update
the corresponding block here so this file continues to reflect “true defaults”.

---------------------------------------------------------------------------
HOW TO TUNE (WHEN NEEDED)
---------------------------------------------------------------------------

To tune a model, change or add fields under `generation_config` for that model:

    temperature       0–2 (OpenAI, Gemini) or 0–1 (Anthropic).
                      • Lower  (0–0.3): more deterministic, good for coding,
                        reasoning, tests.
                      • Medium (0.4–0.8): balanced general chat.
                      • Higher (0.9+): more creative, more variance.

    top_p             0–1 nucleus sampling cutoff.
                      • 1.0 = use full distribution.
                      • Lower values (0.8–0.95) = more conservative.

    top_k             (Gemini only) number of candidate tokens to sample from.
                      • Higher (e.g. 64) = more variety.
                      • Lower (e.g. 1–10) = very deterministic.

    candidate_count   (Gemini) number of alternative responses to generate.
                      • >1 multiplies cost and latency; keep at 1 unless you
                        actually use multiple candidates.

    max_output_tokens / max_tokens
                      • Caps the length of the model’s response. Anthropic
                        requires `max_tokens`; for others it’s optional and
                        often better set per-feature rather than globally.

---------------------------------------------------------------------------
FUTURE: USER-SELECTABLE TUNING PROFILES
---------------------------------------------------------------------------

A future version of Syvrona might let the *end user* choose a profile, for
example:

    • Precise (low temperature)
    • Balanced (default)
    • Creative (higher temperature)
    • Coding (very low temperature, stricter top_p)
    • Summarization (short, low temperature)

Implementation idea (for later):

    1. Keep this registry as “base defaults”.
    2. Define a separate PROFILE_OVERRIDES dict (e.g. in profiles.py).
    3. At request time, merge:
           model_defaults
        →  profile_overrides (if any)
        →  per-call overrides (if any)

For now, this file simply documents and exposes the default settings.
"""

DEFAULT_MODEL_KEY = "gpt-5.2-chat-latest"


MODEL_REGISTRY = {
    # -------------------- OpenAI -------------------- #
    "gpt-5.2-chat-latest": {
        "provider": "openai",
        "display_name": "GPT-5.2 Chat Latest",
        "openai_endpoint": "responses",
        "encoding": "cl100k_base",
        "generation_config": {},
    },
    "gpt-5.1-2025-11-13": {
        "provider": "openai",
        "display_name": "GPT-5.1",
        "openai_endpoint": "responses",
        "encoding": "cl100k_base",
        "generation_config": {
            # Balanced, general-purpose assistant
            "temperature": 0.7,
            "top_p": 1.0,
        },
    },
    "gpt-5.1-codex": {
        "provider": "openai",
        "display_name": "GPT-5.1 Codex",
        "openai_endpoint": "responses",
        "encoding": "cl100k_base",
        "generation_config": {},
    },
    # -------------------- Anthropic -------------------- #
    "claude-sonnet-4-5-20250929": {
        "provider": "anthropic",
        "display_name": "Claude 4.5 Sonnet",
        "max_tokens": 64000,
        "encoding": "cl100k_base",
        "generation_config": {
            # High-quality, reasoning-focused; keep fairly low temp
            "temperature": 0.35,
            "top_p": 0.95,
        },
    },
    "claude-opus-4-5-20251101": {
        "provider": "anthropic",
        "display_name": "Claude 4.5 Opus",
        "max_tokens": 64000,
        "encoding": "cl100k_base",
        "generation_config": {
            # High-quality, reasoning-focused; keep fairly low temp
            "temperature": 0.35,
            "top_p": 0.95,
        },
    },
    "claude-haiku-4-5-20251001": {
        "provider": "anthropic",
        "display_name": "Claude 4.5 Haiku",
        "max_tokens": 64000,
        "encoding": "cl100k_base",
        "generation_config": {
            # High-quality, reasoning-focused; keep fairly low temp
            "temperature": 0.35,
            "top_p": 0.95,
        },
    },
    # -------------------- Gemini -------------------- #
    "gemini-3-pro-preview": {
        "provider": "gemini",
        "display_name": "Gemini 3 Pro Preview",
        "encoding": "cl100k_base",
        "system_prompt": "You are a thorough and intelligent assistant.",
        "fallback_model": "gemini-2.5-flash",
        "generation_config": {
            # Higher-quality, more careful answers
            "temperature": 0.3,
            "top_p": 0.9,
            "top_k": 40,
            "candidate_count": 1,
        },
    },
    "gemini-2.5-flash": {
        "provider": "gemini",
        "display_name": "Gemini 2.5 Flash",
        "encoding": "cl100k_base",
        "system_prompt": "You are a helpful and concise assistant.",
        "fallback_model": "gemini-2.0-flash",
        "generation_config": {
            # Fast, good default for general chat; slightly more creative
            "temperature": 0.6,
            "top_p": 0.9,
            "top_k": 40,
            "candidate_count": 1,
        },
    },
    "gemini-2.5-pro": {
        "provider": "gemini",
        "display_name": "Gemini 2.5 Pro",
        "encoding": "cl100k_base",
        "system_prompt": "You are a thorough and intelligent assistant.",
        "fallback_model": "gemini-2.5-flash",
        "generation_config": {
            # Higher-quality, more careful answers
            "temperature": 0.3,
            "top_p": 0.9,
            "top_k": 40,
            "candidate_count": 1,
        },
    },
}


# -------------------- Optional profile-based tuning -------------------- #
# These profiles are NOT used automatically. They are here so future UI /
# feature code can easily layer "profiles" on top of model defaults.
#
# All values are chosen to be valid across:
#   - OpenAI (temperature 0–2)
#   - Anthropic / Claude (temperature 0–1)
#   - Gemini (temperature 0–2)
#
# Example usage (later, in your providers):
#   cfg = build_generation_config("gpt-5.1-codex", profile="coding")
#
PROFILE_OVERRIDES = {
    # Slightly lower temperature, good for general reasoning & chat
    "balanced": {
        "temperature": 0.7,
        "top_p": 0.95,
    },
    # Very deterministic: coding, prompt-building, tools, tests
    "coding": {
        "temperature": 0.2,
        "top_p": 0.9,
    },
    # Low-temp summarization / analysis
    "summarize": {
        "temperature": 0.25,
        "top_p": 0.9,
    },
    # High-variability brainstorming / creative writing / ideation
    # Uses the *universal* safe max temp (1.0) so Claude stays happy.
    "creative": {
        "temperature": 1.0,
        "top_p": 0.95,
    },
    # Explicit "no-op" profile if you want to say "use model defaults as-is"
    "default": {
        # intentionally empty
    },
}


def build_generation_config(
    model_name: str,
    profile: str | None = None,
    overrides: dict | None = None,
) -> dict:
    """
    Build the generation_config for a request by merging:
        1. Model defaults from MODEL_REGISTRY
        2. Optional profile-level overrides (PROFILE_OVERRIDES)
        3. Optional per-call overrides (highest priority)

    If you never call this function, behavior is driven solely by the
    values in MODEL_REGISTRY["..."]["generation_config"].
    """
    metadata = MODEL_REGISTRY.get(model_name, {})
    base = (metadata.get("generation_config") or {}).copy()

    # 1) Apply profile overrides (if any)
    if profile:
        profile_cfg = PROFILE_OVERRIDES.get(profile)
        if profile_cfg:
            base.update(profile_cfg)

    # 2) Apply per-call overrides (highest precedence)
    if overrides:
        for key, value in overrides.items():
            if value is not None:
                base[key] = value

    return base


def get_model_metadata(model_name):
    return MODEL_REGISTRY.get(model_name, {})
