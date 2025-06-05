# model_registry.py

MODEL_REGISTRY = {
    "gpt-4.1": {
        "provider": "openai",
        # You can add openai token limits here if you want
    },
    # ... other OpenAI models ...
    "gpt-4.1-mini": {
        "provider": "openai",
    },
    "gpt-4o": {
        "provider": "openai",
    },
    "gpt-4o-mini": {
        "provider": "openai",
    },
    "gpt-4.1-nano": {
        "provider": "openai",
    },
    "o3": {
        "provider": "openai",
    },
    "o3-mini": {
        "provider": "openai",
    },
    "o4-mini": {
        "provider": "openai",
    },
    "gpt-4.5": {
        "provider": "openai",
    },
    "gpt-3.5-turbo": {
        "provider": "openai",
    },
    "claude-sonnet-4-20250514": {
        "provider": "anthropic",
        "max_tokens": 64000,
    },
    "claude-opus-4-20250514": {
        "provider": "anthropic",
        "max_tokens": 32000,
    },
    "claude-3-7-sonnet-20250219": {
        "provider": "anthropic",
        "max_tokens": 64000,  # 128k with beta header, see docs
    },
    "claude-3-5-sonnet-20241022": {
        "provider": "anthropic",
        "max_tokens": 8192,
    },
    "claude-3-5-haiku-20241022": {
        "provider": "anthropic",
        "max_tokens": 8192,
    },
    "claude-3-haiku-20240307": {
        "provider": "anthropic",
        "max_tokens": 4096,
    },
    "claude-3-opus-20240229": {
        "provider": "anthropic",
        "max_tokens": 4096,
    },
}


def get_model_metadata(model_name):
    return MODEL_REGISTRY.get(model_name, {})
