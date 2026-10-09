import json
import logging
import time
from typing import NamedTuple

from google.genai import errors, types

from bot.config import GEMINI_LLM_MODEL
from bot.data.prompts import build_system_prompt
from bot.rag.embeddings import get_genai_client

log = logging.getLogger(__name__)

# Fallback chain — якщо primary 503 або 429, пробуємо легший lite, потім 3.8-flash
# (інше покоління, окрема квота). gemini-2.0-flash Google вимкнув: 404 з 2026-10.
MODEL_FALLBACK = [GEMINI_LLM_MODEL, "gemini-2.5-flash-lite", "gemini-3.8-flash"]
MAX_RETRIES_PER_MODEL = 2
BACKOFF_SECONDS = 1.5

# 503: Google's side is overloaded and usually recovers within seconds, so the
# same model is retried with backoff. 429: our quota for this model is spent and
# will not come back in seconds, but every model has its own free-tier quota, so
# move to the next model at once instead of sleeping.
OVERLOADED = 503
RATE_LIMITED = 429


# The order button under an answer must point at the product the answer
# recommends - not simply the top retrieval hit, which can be a different item.
# So the model returns JSON and names its choice; the enum holds only the
# retrieved ids, so it cannot invent one.
NO_PRODUCT = "none"


class Reply(NamedTuple):
    text: str
    product_id: str | None  # retrieved product the reply recommends, if any


def reply_schema(product_ids: list[str]) -> types.Schema:
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "reply": types.Schema(type=types.Type.STRING),
            "product_id": types.Schema(
                type=types.Type.STRING, enum=[*product_ids, NO_PRODUCT]
            ),
        },
        required=["reply", "product_id"],
        property_ordering=["reply", "product_id"],
    )


def parse_reply(raw: str, product_ids: list[str]) -> Reply:
    """Never guesses a product: anything unexpected means no order button."""
    try:
        data = json.loads(raw)
        text = str(data.get("reply") or "").strip()
        product_id = data.get("product_id")
    except (ValueError, AttributeError):
        log.warning("LLM reply is not the expected JSON — answering without an order button")
        return Reply(raw.strip(), None)
    return Reply(text, product_id if product_id in product_ids else None)


def _call(model: str, query: str, system: str, schema: types.Schema) -> str:
    result = get_genai_client().models.generate_content(
        model=model,
        contents=query,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    return result.text or ""


def generate_reply(query: str, products: list[dict], lang: str, note: str | None = None) -> Reply:
    system = build_system_prompt(lang, products, note)
    product_ids = [p["id"] for p in products]
    schema = reply_schema(product_ids)
    last_error: Exception | None = None

    for model in MODEL_FALLBACK:
        for attempt in range(MAX_RETRIES_PER_MODEL):
            try:
                return parse_reply(_call(model, query, system, schema), product_ids)
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
    return Reply("", None)
