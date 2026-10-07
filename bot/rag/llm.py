import logging
import time

from google.genai import errors, types

from bot.config import GEMINI_LLM_MODEL
from bot.data.prompts import build_system_prompt
from bot.rag.embeddings import get_genai_client

log = logging.getLogger(__name__)

# Fallback chain — якщо primary 503 або 429, пробуємо легший lite, потім старший 2.0-flash.
MODEL_FALLBACK = [GEMINI_LLM_MODEL, "gemini-2.5-flash-lite", "gemini-2.0-flash"]
MAX_RETRIES_PER_MODEL = 2
BACKOFF_SECONDS = 1.5

# 503: Google's side is overloaded and usually recovers within seconds, so the
# same model is retried with backoff. 429: our quota for this model is spent and
# will not come back in seconds, but every model has its own free-tier quota, so
# move to the next model at once instead of sleeping.
OVERLOADED = 503
RATE_LIMITED = 429


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
            # google-genai raises ClientError for 4xx (429 included) and
            # ServerError for 5xx: catch their common base and decide by code.
            except errors.APIError as e:
                last_error = e
                code = getattr(e, "code", None)
                if code not in (RATE_LIMITED, OVERLOADED):
                    raise
                if code == RATE_LIMITED:
                    log.warning("LLM rate-limited (model=%s) — switching model", model)
                    break
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
