"""Retrieval, model fallback and prompt grounding: bot/rag/ and bot/data/prompts.py."""

import pytest
from google.genai import errors

import bot.rag.llm as llm
from bot.data.prompts import build_system_prompt
from bot.rag.retriever import search
from tests.conftest import PRODUCT

PRIMARY, LITE, OLDER = llm.MODEL_FALLBACK


def server_error(code: int = 503) -> errors.ServerError:
    return errors.ServerError(code, {"error": {"code": code, "message": "x", "status": "UNAVAILABLE"}})


def client_error(code: int, status: str) -> errors.ClientError:
    return errors.ClientError(code, {"error": {"code": code, "message": "x", "status": status}})


@pytest.fixture
def sleeps(monkeypatch):
    """Records backoff instead of sleeping, so retry tests stay instant."""
    recorded: list[float] = []
    monkeypatch.setattr(llm.time, "sleep", recorded.append)
    return recorded


def models_called(genai) -> list[str]:
    return [c["model"] for c in genai.generate_calls]


# --- retriever ---------------------------------------------------------------


def test_search_asks_for_top_k_by_embedding_and_drops_out_of_stock(db, genai):
    db.rpc_results["match_products"] = [
        {**PRODUCT, "similarity": 0.9},
        {**PRODUCT, "id": "sold-out", "in_stock": False, "similarity": 0.8},
    ]

    results = search("аметист")

    assert [r["id"] for r in results] == ["amethyst-bracelet"]
    [(name, params)] = db.rpc_calls
    assert name == "match_products"
    assert params == {"query_embedding": [0.1, 0.2, 0.3], "match_count": 3}
    assert genai.embed_calls == ["аметист"]
    assert db.schemas == ["murmure"]


# --- model fallback ----------------------------------------------------------


def test_overloaded_primary_falls_back_to_lite(genai, sleeps):
    genai.reply = lambda model, query: server_error(503) if model == PRIMARY else "from lite"

    assert llm.generate_reply("q", [PRODUCT], "uk") == "from lite"
    assert models_called(genai) == [PRIMARY, PRIMARY, LITE]
    assert sleeps == [1.5, 3.0]


def test_all_models_overloaded_raises_the_last_error(genai, sleeps):
    genai.reply = lambda model, query: server_error(503)

    with pytest.raises(errors.ServerError):
        llm.generate_reply("q", [PRODUCT], "uk")
    assert models_called(genai) == [PRIMARY, PRIMARY, LITE, LITE, OLDER, OLDER]


def test_non_transient_server_error_is_not_retried(genai, sleeps):
    genai.reply = lambda model, query: server_error(500)

    with pytest.raises(errors.ServerError):
        llm.generate_reply("q", [PRODUCT], "uk")
    assert models_called(genai) == [PRIMARY]
    assert sleeps == []


def test_bad_request_is_not_retried(genai, sleeps):
    genai.reply = lambda model, query: client_error(400, "INVALID_ARGUMENT")

    with pytest.raises(errors.ClientError):
        llm.generate_reply("q", [PRODUCT], "uk")
    assert models_called(genai) == [PRIMARY]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "known bug: google-genai raises ClientError for 4xx, llm.py catches only "
        "ServerError, so the 429 branch is dead and a free-tier rate limit skips the "
        "fallback models (which have their own quota) - the client sees LLM_ERROR"
    ),
)
def test_rate_limited_primary_falls_back_to_lite(genai, sleeps):
    genai.reply = lambda model, query: (
        client_error(429, "RESOURCE_EXHAUSTED") if model == PRIMARY else "from lite"
    )

    assert llm.generate_reply("q", [PRODUCT], "uk") == "from lite"


# --- prompt grounding --------------------------------------------------------


def test_prompt_lists_only_the_retrieved_products_in_the_client_language():
    prompt = build_system_prompt("ru", [PRODUCT])

    assert "Respond ONLY in Russian" in prompt
    assert "- Браслет з аметисту | аметист, фіолетовий, 1200 UAH" in prompt
    assert "do not invent items" in prompt


def test_prompt_with_nothing_retrieved_says_empty():
    assert build_system_prompt("en", []).endswith("CATALOG:\n(empty)")


def test_prompt_falls_back_to_english_for_unknown_language():
    assert "Respond ONLY in English" in build_system_prompt("de", [PRODUCT])
