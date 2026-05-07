from google import genai
from google.genai import types

from bot.config import GEMINI_API_KEY, GEMINI_EMBEDDING_DIM, GEMINI_EMBEDDING_MODEL

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY missing in .env")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def get_genai_client() -> genai.Client:
    return _get_client()


def _embed_config() -> types.EmbedContentConfig:
    return types.EmbedContentConfig(output_dimensionality=GEMINI_EMBEDDING_DIM)


def embed(text: str) -> list[float]:
    result = _get_client().models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=text,
        config=_embed_config(),
    )
    return list(result.embeddings[0].values)


def embed_batch(texts: list[str]) -> list[list[float]]:
    result = _get_client().models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=texts,
        config=_embed_config(),
    )
    return [list(e.values) for e in result.embeddings]
