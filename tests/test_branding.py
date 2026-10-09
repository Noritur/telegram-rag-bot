"""One codebase, several shops: brand and schema come from env (bot.config)."""

from bot import config
from bot.data.prompts import build_system_prompt
from bot.handlers.commands import greeting
from tests.conftest import CLIENT_ID, PRODUCT


def test_defaults_keep_the_original_shop():
    assert config.SHOP_NAME == "Murmure" and config.DB_SCHEMA == "murmure"
    assert greeting("uk").startswith("Вітаю в Murmure.")


async def test_another_shop_greets_answers_and_stores_under_its_own_name(bot, db, genai, monkeypatch):
    monkeypatch.setattr(config, "SHOP_NAME", "Lumina Stones")
    monkeypatch.setattr(config, "DB_SCHEMA", "lumina")
    db.rpc_results["match_products"] = [{**PRODUCT, "similarity": 0.8}]

    await bot.send(bot.text("/start"))
    await bot.send(bot.text("браслет з аметисту"))

    greeting_text, _answer = bot.texts_to(CLIENT_ID)
    assert greeting_text.startswith("Вітаю в Lumina Stones.")
    [call] = genai.generate_calls
    assert "consultant for Lumina Stones" in call["system"]
    assert "Murmure" not in call["system"]
    assert db.schemas and set(db.schemas) == {"lumina"}


def test_prompt_names_the_configured_shop(monkeypatch):
    monkeypatch.setattr(config, "SHOP_NAME", "Lumina Stones")
    prompt = build_system_prompt("en", [PRODUCT])
    assert "consultant for Lumina Stones" in prompt
    assert "Lumina Stones customers value" in prompt
