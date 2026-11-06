"""Local token estimates for quotas and context budgets.

Every model is counted with tiktoken's ``o200k_base``, the GPT-5/6 encoding. For
Claude and Gemini this is an approximation: neither publishes a tiktoken encoding, and
Anthropic says the Claude 5.5 tokenizer counts about 30% more tokens than Claude 4.5
did for the same text. Budgets built on these counts therefore keep headroom (see
``AIStreamer``), and monthly quotas are approximate by design.
"""

from functools import lru_cache

import tiktoken

ENCODING_NAME = "o200k_base"


@lru_cache(maxsize=1)
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(ENCODING_NAME)


def count_tokens(text: str) -> int:
    return len(_encoding().encode(text, disallowed_special=())) if text else 0
