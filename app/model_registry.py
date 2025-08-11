# model_registry.py

DEFAULT_MODEL_KEY = "gpt-5-chat-latest"


MODEL_REGISTRY = {
    "gpt-5": {
        "provider": "openai",
        "display_name": "GPT-5",
        "openai_endpoint": "responses",
        "encoding": "cl100k_base",
    },
    "gpt-5-chat-latest": {
        "provider": "openai",
        "display_name": "GPT-5 Chat",
        "openai_endpoint": "responses",
        "encoding": "cl100k_base",
    },
    "gpt-5-mini": {
        "provider": "openai",
        "display_name": "GPT-5 Mini",
        "openai_endpoint": "responses",
        "encoding": "cl100k_base",
    },
    "gpt-5-nano": {
        "provider": "openai",
        "display_name": "GPT-5 Nano",
        "openai_endpoint": "responses",
        "encoding": "cl100k_base",
    },
    "gpt-4.1": {
        "provider": "openai",
        "display_name": "GPT-4.1",
        "openai_endpoint": "chat",
        "encoding": "cl100k_base",
    },
    "o3": {
        "provider": "openai",
        "display_name": "O3",
        "openai_endpoint": "responses",
        "encoding": "cl100k_base",
    },
    "claude-sonnet-4-20250514": {
        "provider": "anthropic",
        "display_name": "Claude 4 Sonnet",
        "max_tokens": 64000,
        "encoding": "cl100k_base",
    },
    "claude-opus-4-20250514": {
        "provider": "anthropic",
        "display_name": "Claude 4 Opus",
        "max_tokens": 32000,
        "encoding": "cl100k_base",
    },
    "claude-3-5-haiku-20241022": {
        "provider": "anthropic",
        "display_name": "Claude 3.5 Haiku",
        "max_tokens": 8192,
        "encoding": "cl100k_base",
    },
}


def get_model_metadata(model_name):
    return MODEL_REGISTRY.get(model_name, {})
