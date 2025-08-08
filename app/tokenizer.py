import tiktoken
from functools import lru_cache
from app.model_registry import MODEL_REGISTRY


@lru_cache(maxsize=None)
def get_tokenizer(model: str):
    enc = MODEL_REGISTRY.get(model, {}).get("encoding", "cl100k_base")
    return tiktoken.get_encoding(enc)
