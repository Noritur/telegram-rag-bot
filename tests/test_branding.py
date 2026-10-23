"""One codebase, several shops: brand and schema come from env (bot.config)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from bot import config
from bot.data.prompts import build_system_prompt
from bot.handlers.commands import greeting
from tests.conftest import CLIENT_ID, PRODUCT

ROOT = Path(__file__).resolve().parent.parent


def import_config(**env: str) -> subprocess.CompletedProcess:
    """Imports bot.config in a fresh interpreter with the given shop settings.

    Empty strings count as set for load_dotenv, so a local .env cannot fill
    them back in.
    """
    full_env = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, "-c", "import bot.config"],
        cwd=ROOT, env=full_env, capture_output=True, text=True,
    )


def test_the_configured_shop_greets():
    assert greeting("uk").startswith(f"Вітаю в {config.SHOP_NAME}.")


@pytest.mark.parametrize(
    ("env", "missing"),
    [
        ({"SHOP_NAME": "", "DB_SCHEMA": ""}, "SHOP_NAME, DB_SCHEMA"),
        ({"SHOP_NAME": "Some Shop", "DB_SCHEMA": ""}, "DB_SCHEMA"),
        ({"SHOP_NAME": "  ", "DB_SCHEMA": "some_shop"}, "SHOP_NAME"),
    ],
)
def test_there_is_no_fallback_shop(env, missing):
    result = import_config(**env)
    assert result.returncode != 0
    assert f"Set {missing} in the environment" in result.stderr


@pytest.mark.parametrize("schema", ["Shop", "shop-1", "shop; drop table orders", "1shop"])
def test_the_schema_must_be_a_plain_name(schema):
    result = import_config(SHOP_NAME="Some Shop", DB_SCHEMA=schema)
    assert result.returncode != 0
    assert "DB_SCHEMA must be a plain Postgres schema name" in result.stderr


def test_a_valid_configuration_imports():
    assert import_config(SHOP_NAME="Some Shop", DB_SCHEMA="some_shop").returncode == 0


async def test_another_shop_greets_answers_and_stores_under_its_own_name(bot, db, genai, monkeypatch):
    original = config.SHOP_NAME
    monkeypatch.setattr(config, "SHOP_NAME", "Lumina Stones")
    monkeypatch.setattr(config, "DB_SCHEMA", "lumina")
    db.rpc_results["match_products"] = [{**PRODUCT, "similarity": 0.8}]

    await bot.send(bot.text("/start"))
    await bot.send(bot.text("браслет з аметисту"))

    greeting_text, _answer = bot.texts_to(CLIENT_ID)
    assert greeting_text.startswith("Вітаю в Lumina Stones.")
    [call] = genai.generate_calls
    assert "consultant for Lumina Stones" in call["system"]
    assert original not in call["system"]
    assert db.schemas and set(db.schemas) == {"lumina"}


def test_prompt_names_the_configured_shop(monkeypatch):
    monkeypatch.setattr(config, "SHOP_NAME", "Lumina Stones")
    prompt = build_system_prompt("en", [PRODUCT])
    assert "consultant for Lumina Stones" in prompt
    assert "Lumina Stones customers value" in prompt
