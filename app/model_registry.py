# model_registry.py

DEFAULT_MODEL_KEY = "gpt-5.1-2025-11-13"


MODEL_REGISTRY = {
    # -------------------- OpenAI -------------------- #
    "gpt-5.1-2025-11-13": {
        "provider": "openai",
        "display_name": "GPT-5.1",
        "openai_endpoint": "responses",
        "encoding": "cl100k_base",
        "generation_config": {
            # Balanced, general-purpose assistant
            "temperature": 0.4,
            "top_p": 1.0,
        },
    },
    "gpt-5": {
        "provider": "openai",
        "display_name": "GPT-5",
        "openai_endpoint": "responses",
        "encoding": "cl100k_base",
        "generation_config": {
            # Very similar to 5.1, slightly conservative
            "temperature": 0.4,
            "top_p": 1.0,
        },
    },
    "gpt-5-chat-latest": {
        "provider": "openai",
        "display_name": "GPT-5 Chat",
        "openai_endpoint": "responses",
        "encoding": "cl100k_base",
        "generation_config": {
            # More conversational / friendly
            "temperature": 0.6,
            "top_p": 1.0,
        },
    },
    "gpt-5-mini": {
        "provider": "openai",
        "display_name": "GPT-5 Mini",
        "openai_endpoint": "responses",
        "encoding": "cl100k_base",
        "generation_config": {
            # Fast, a bit more creative by default
            "temperature": 0.7,
            "top_p": 1.0,
        },
    },
    "gpt-5-nano": {
        "provider": "openai",
        "display_name": "GPT-5 Nano",
        "openai_endpoint": "responses",
        "encoding": "cl100k_base",
        "generation_config": {
            # Smallest / cheapest, we allow more creativity
            "temperature": 0.8,
            "top_p": 1.0,
        },
    },
    "gpt-4.1": {
        "provider": "openai",
        "display_name": "GPT-4.1",
        "openai_endpoint": "chat",
        "encoding": "cl100k_base",
        "generation_config": {
            # Slightly more deterministic, good for serious work
            "temperature": 0.35,
            "top_p": 1.0,
        },
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
    "claude-sonnet-4-20250514": {
        "provider": "anthropic",
        "display_name": "Claude 4 Sonnet",
        "max_tokens": 64000,
        "encoding": "cl100k_base",
        "generation_config": {
            "temperature": 0.35,
            "top_p": 0.95,
        },
    },
    "claude-opus-4-1-20250805": {
        "provider": "anthropic",
        "display_name": "Claude 4.1 Opus",
        "max_tokens": 32000,
        "encoding": "cl100k_base",
        "generation_config": {
            # Flagship “thinking” model – keep outputs tight & reliable
            "temperature": 0.3,
            "top_p": 0.9,
        },
    },
    "claude-3-5-haiku-20241022": {
        "provider": "anthropic",
        "display_name": "Claude 3.5 Haiku",
        "max_tokens": 8192,
        "encoding": "cl100k_base",
        "generation_config": {
            # Fast and chatty; a bit more open
            "temperature": 0.6,
            "top_p": 0.95,
        },
    },

    # -------------------- Gemini -------------------- #
    "gemini-2.5-flash": {
        "provider": "gemini",
        "display_name": "Gemini 2.5 Flash",
        "encoding": "cl100k_base",
        "system_prompt": "You are Syvrona, a helpful and concise assistant.",
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
        "system_prompt": "You are Syvrona, a thorough and intelligent assistant.",
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


def get_model_metadata(model_name):
    return MODEL_REGISTRY.get(model_name, {})
