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


def answer(text: str, product_id: str = "amethyst-bracelet") -> dict:
    return {"reply": text, "product_id": product_id}


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
    genai.reply = lambda model, query: server_error(503) if model == PRIMARY else answer("from lite")

    assert llm.generate_reply("q", [PRODUCT], "uk").text == "from lite"
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


def test_rate_limited_primary_switches_model_without_waiting(genai, sleeps):
    # google-genai raises 429 as ClientError (4xx). It used to slip past an
    # `except ServerError` and skip the fallback models entirely.
    genai.reply = lambda model, query: (
        client_error(429, "RESOURCE_EXHAUSTED") if model == PRIMARY else answer("from lite")
    )

    assert llm.generate_reply("q", [PRODUCT], "uk").text == "from lite"
    # A spent quota does not come back in seconds: no retry, no sleep.
    assert models_called(genai) == [PRIMARY, LITE]
    assert sleeps == []


def test_rate_limit_then_overload_follows_both_rules(genai, sleeps):
    lite_calls = []

    def reply(model, query):
        if model == PRIMARY:
            return client_error(429, "RESOURCE_EXHAUSTED")
        lite_calls.append(model)
        return server_error(503) if len(lite_calls) == 1 else answer("from lite, second try")

    genai.reply = reply

    assert llm.generate_reply("q", [PRODUCT], "uk").text == "from lite, second try"
    assert models_called(genai) == [PRIMARY, LITE, LITE]
    assert sleeps == [1.5]


def test_every_model_rate_limited_raises_after_one_call_each(genai, sleeps):
    genai.reply = lambda model, query: client_error(429, "RESOURCE_EXHAUSTED")

    with pytest.raises(errors.ClientError):
        llm.generate_reply("q", [PRODUCT], "uk")
    assert models_called(genai) == [PRIMARY, LITE, OLDER]
    assert sleeps == []


# --- the model names the product it recommends ---------------------------------


def test_reply_is_requested_as_json_restricted_to_retrieved_ids(genai):
    second = {**PRODUCT, "id": "neck-amethyst-001"}

    reply = llm.generate_reply("q", [PRODUCT, second], "uk")

    assert reply == llm.Reply(genai.reply["reply"], "amethyst-bracelet")
    [call] = genai.generate_calls
    assert call["mime_type"] == "application/json"
    assert call["schema"].properties["product_id"].enum == ["amethyst-bracelet", "neck-amethyst-001", "none"]
    assert call["schema"].required == ["reply", "product_id"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"reply": "є кольє", "product_id": "p2"}', llm.Reply("є кольє", "p2")),
        ('{"reply": "нема", "product_id": "none"}', llm.Reply("нема", None)),
        ('{"reply": "є перстень", "product_id": "not-retrieved"}', llm.Reply("є перстень", None)),
        ('{"reply": "є", "product_id": null}', llm.Reply("є", None)),
        ("plain text, not json", llm.Reply("plain text, not json", None)),
        ('["a", "list"]', llm.Reply('["a", "list"]', None)),
        ("", llm.Reply("", None)),
    ],
    ids=["chosen", "none", "outside-retrieved", "null", "not-json", "not-an-object", "empty"],
)
def test_parse_reply_never_guesses_a_product(raw, expected):
    assert llm.parse_reply(raw, ["p1", "p2"]) == expected


# --- prompt grounding --------------------------------------------------------


def test_prompt_lists_only_the_retrieved_products_in_the_client_language():
    prompt = build_system_prompt("ru", [PRODUCT])

    assert "Respond ONLY in Russian" in prompt
    assert "- [amethyst-bracelet] Браслет з аметисту | аметист, фіолетовий, 1200 UAH" in prompt
    assert "product_id" in prompt
    assert "do not invent items" in prompt


def test_prompt_with_nothing_retrieved_says_empty():
    assert build_system_prompt("en", []).endswith("CATALOG:\n(empty)")


def test_prompt_falls_back_to_english_for_unknown_language():
    assert "Respond ONLY in English" in build_system_prompt("de", [PRODUCT])
