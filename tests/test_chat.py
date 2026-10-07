"""Free-text path: bot/handlers/chat.py, driven through the real app."""

import pytest
from google.genai import errors

from bot.data.prompts import HANDOFF, LLM_ERROR
from bot.handlers.commands import CATALOG_INTRO
from tests.conftest import ADMIN_ID, CLIENT_ID, PRODUCT


def matches(similarity: float, **overrides) -> list[dict]:
    return [{**PRODUCT, **overrides, "similarity": similarity}]


async def test_browse_question_goes_to_catalog_without_rag(bot, db, genai):
    db.tables["products"] = [PRODUCT, {**PRODUCT, "id": "moon-necklace", "category": "кольє"}]

    await bot.send(bot.text("Шо у вас є?"))

    [reply] = bot.texts_to(CLIENT_ID)
    assert reply.startswith(CATALOG_INTRO["uk"])
    assert "• Кольє: 1" in reply and "• Браслети: 1" in reply
    assert genai.embed_calls == []
    assert db.rpc_calls == []


async def test_relevant_question_gets_grounded_answer_with_order_button(bot, db, genai):
    db.rpc_results["match_products"] = matches(0.82)

    await bot.send(bot.text("хочу браслет з аметисту"))

    assert bot.texts_to(CLIENT_ID) == [genai.reply]
    assert bot.buttons_to(CLIENT_ID) == ["order:amethyst-bracelet", "nav:catalog"]
    [call] = genai.generate_calls
    assert call["query"] == "хочу браслет з аметисту"
    assert "Браслет з аметисту" in call["system"]
    assert "Respond ONLY in Ukrainian" in call["system"]
    assert bot.texts_to(ADMIN_ID) == []
    [logged] = db.inserted("messages")
    assert logged.row == {
        "user_id": CLIENT_ID,
        "text": "хочу браслет з аметисту",
        "matched": True,
        "top_score": 0.82,
    }


@pytest.mark.parametrize(
    ("similarity", "answered"),
    [(0.4, True), (0.39, False)],
    ids=["at-threshold", "just-below"],
)
async def test_relevance_threshold_boundary(bot, db, genai, similarity, answered):
    db.rpc_results["match_products"] = matches(similarity)

    await bot.send(bot.text("щось про аметист"))

    assert (bot.texts_to(CLIENT_ID) == [genai.reply]) is answered
    assert (bot.texts_to(CLIENT_ID) == [HANDOFF["uk"]]) is not answered


async def test_unknown_question_hands_off_and_pings_owner(bot, db, genai):
    db.rpc_results["match_products"] = matches(0.31)

    await bot.send(bot.text("чи робите гравіювання?"))

    assert bot.texts_to(CLIENT_ID) == [HANDOFF["uk"]]
    [ping] = bot.texts_to(ADMIN_ID)
    assert "чи робите гравіювання?" in ping
    assert "@olena_buyer" in ping
    assert genai.generate_calls == []
    assert [m.row["text"] for m in db.inserted("missed")] == ["чи робите гравіювання?"]
    assert db.inserted("messages")[0].row["matched"] is False


async def test_out_of_stock_match_is_not_offered(bot, db, genai):
    db.rpc_results["match_products"] = matches(0.9, in_stock=False)

    await bot.send(bot.text("браслет з аметисту"))

    assert bot.texts_to(CLIENT_ID) == [HANDOFF["uk"]]
    assert genai.generate_calls == []


async def test_no_matches_at_all_hands_off(bot, db):
    db.rpc_results["match_products"] = []

    await bot.send(bot.text("а є щось зелене?"))

    assert bot.texts_to(CLIENT_ID) == [HANDOFF["uk"]]
    assert db.inserted("messages")[0].row["top_score"] is None


async def test_retrieval_failure_apologises_without_bothering_owner(bot, db):
    db.fail["match_products"] = RuntimeError("supabase down")

    await bot.send(bot.text("браслет з аметисту"))

    assert bot.texts_to(CLIENT_ID) == [LLM_ERROR["uk"]]
    assert bot.texts_to(ADMIN_ID) == []


@pytest.mark.parametrize(
    "outcome",
    ["   ", errors.ClientError(400, {"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}})],
    ids=["empty-reply", "llm-error"],
)
async def test_llm_trouble_apologises(bot, db, genai, outcome):
    db.rpc_results["match_products"] = matches(0.8)
    genai.reply = outcome

    await bot.send(bot.text("браслет з аметисту"))

    assert bot.texts_to(CLIENT_ID) == [LLM_ERROR["uk"]]
    assert bot.buttons_to(CLIENT_ID) == []


async def test_russian_speaking_client_gets_russian(bot, db, genai):
    db.rpc_results["match_products"] = matches(0.1)

    await bot.send(bot.text("есть гравировка?", lang="ru"))

    assert bot.texts_to(CLIENT_ID) == [HANDOFF["ru"]]
