"""Token estimates never raise on user text (D22)."""

from app.tokenizer import count_tokens


def test_special_token_text_is_counted_as_text():
    # tiktoken's default refuses special tokens; user text may contain them.
    assert count_tokens("please explain <|endoftext|> and <|im_start|>") > 0


def test_empty_text_is_zero():
    assert count_tokens("") == 0
