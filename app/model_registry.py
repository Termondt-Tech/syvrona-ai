# model_registry.py

DEFAULT_MODEL_KEY = "gpt-4.1"


MODEL_REGISTRY = {
    "gpt-4.1": {
        "provider": "openai",
        "display_name": "GPT-4.1",
        "openai_endpoint": "chat",
    },
    "gpt-4.1-mini": {
        "provider": "openai",
        "display_name": "GPT-4.1 Mini",
        "openai_endpoint": "chat",
    },
    "gpt-4o": {
        "provider": "openai",
        "display_name": "GPT-4o",
        "openai_endpoint": "chat",
    },
    "gpt-4o-mini": {
        "provider": "openai",
        "display_name": "GPT-4o Mini",
        "openai_endpoint": "chat",
    },
    "gpt-4.1-nano": {
        "provider": "openai",
        "display_name": "GPT-4.1 Nano",
        "openai_endpoint": "chat",
    },
    "o3": {
        "provider": "openai",
        "display_name": "O3",
        "openai_endpoint": "responses",
    },
    "o3-mini": {
        "provider": "openai",
        "display_name": "O3 Mini",
        "openai_endpoint": "responses",
    },
    "o4-mini": {
        "provider": "openai",
        "display_name": "O4 Mini",
        "openai_endpoint": "responses",
    },
    "gpt-4.5": {
        "provider": "openai",
        "display_name": "GPT-4.5",
        "openai_endpoint": "chat",
    },
    "gpt-3.5-turbo": {
        "provider": "openai",
        "display_name": "GPT-3.5 Turbo",
        "openai_endpoint": "chat",
    },
    "claude-sonnet-4-20250514": {
        "provider": "anthropic",
        "display_name": "Claude 4 Sonnet",
        "max_tokens": 64000,
    },
    "claude-opus-4-20250514": {
        "provider": "anthropic",
        "display_name": "Claude 4 Opus",
        "max_tokens": 32000,
    },
    "claude-3-7-sonnet-20250219": {
        "provider": "anthropic",
        "display_name": "Claude 3 Sonnet",
        "max_tokens": 64000,  # 128k with beta header, see docs
    },
    "claude-3-5-sonnet-20241022": {
        "provider": "anthropic",
        "display_name": "Claude 3.5 Sonnet",
        "max_tokens": 8192,
    },
    "claude-3-5-haiku-20241022": {
        "provider": "anthropic",
        "display_name": "Claude 3.5 Haiku",
        "max_tokens": 8192,
    },
    "claude-3-haiku-20240307": {
        "provider": "anthropic",
        "display_name": "Claude 3 Haiku",
        "max_tokens": 4096,
    },
    "claude-3-opus-20240229": {
        "provider": "anthropic",
        "display_name": "Claude 3 Opus",
        "max_tokens": 4096,
    },
}


def get_model_metadata(model_name):
    return MODEL_REGISTRY.get(model_name, {})
