from functools import lru_cache

import tiktoken

from config.settings import get_settings


@lru_cache(maxsize=1)
def get_token_encoder():
    """Return tokenizer yang sesuai dengan model, dengan fallback stabil."""
    model = get_settings().llm_model
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("o200k_base")


def count_tokens(text: str) -> int:
    return len(get_token_encoder().encode(text))


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Potong teks pada batas token tanpa menghasilkan byte UTF-8 rusak."""
    if max_tokens <= 0 or not text:
        return ""

    encoder = get_token_encoder()
    encoded = encoder.encode(text)
    if len(encoded) <= max_tokens:
        return text
    return encoder.decode(encoded[:max_tokens]).rstrip()
