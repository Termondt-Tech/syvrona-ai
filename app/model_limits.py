# model_utils.py (or just keep in model_registry.py)

from app.model_registry import MODEL_REGISTRY


def get_max_tokens(model_name, requested=None):
    info = MODEL_REGISTRY.get(model_name, {})
    max_allowed = info.get("max_tokens")
    if max_allowed is None:
        # fallback default
        max_allowed = 4096
    if requested:
        return min(max_allowed, requested)
    return max_allowed
