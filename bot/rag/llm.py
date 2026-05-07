import logging
import time

from google.genai import errors, types

from bot.config import GEMINI_LLM_MODEL
from bot.data.prompts import build_system_prompt
from bot.rag.embeddings import get_genai_client

log = logging.getLogger(__name__)

# Fallback chain — якщо primary 503, пробуємо легший lite, потім старший 2.0-flash.
MODEL_FALLBACK = [GEMINI_LLM_MODEL, "gemini-2.5-flash-lite", "gemini-2.0-flash"]
MAX_RETRIES_PER_MODEL = 2
BACKOFF_SECONDS = 1.5


def _call(model: str, query: str, system: str) -> str:
    result = get_genai_client().models.generate_content(
        model=model,
        contents=query,
        config=types.GenerateContentConfig(system_instruction=system),
    )
    return result.text or ""


def generate_reply(query: str, products: list[dict], lang: str) -> str:
    system = build_system_prompt(lang, products)
    last_error: Exception | None = None

    for model in MODEL_FALLBACK:
        for attempt in range(MAX_RETRIES_PER_MODEL):
            try:
                return _call(model, query, system)
            except errors.ServerError as e:
                last_error = e
                code = getattr(e, "code", None)
                if code not in (429, 503):
                    raise
                log.warning(
                    "LLM transient error (model=%s attempt=%d code=%s) — backing off",
                    model,
                    attempt + 1,
                    code,
                )
                time.sleep(BACKOFF_SECONDS * (attempt + 1))
        log.warning("LLM model %s exhausted retries — falling back", model)

    if last_error:
        raise last_error
    return ""
