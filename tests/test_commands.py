"""Commands, language, catalog summary, admin gate and owner notifications."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import bot.handlers.notify as notify
from bot.handlers.commands import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    GREETINGS,
    HELP,
    catalog_text,
    detect_lang,
)
from tests.conftest import ADMIN_ID, CLIENT_ID, PRODUCT

CATALOG = json.loads((Path(__file__).parent.parent / "bot" / "data" / "catalog.json").read_text())
LANG_BUTTONS = ["lang:uk", "lang:ru", "lang:en"]


@pytest.mark.parametrize(
    ("code", "expected"),
    [(None, "en"), ("uk", "uk"), ("uk-UA", "uk"), ("ru", "ru"), ("RU", "ru"), ("en-GB", "en"), ("pl", "en")],
)
def test_detect_lang(code, expected):
    assert detect_lang(code) == expected


async def test_start_greets_in_client_language_with_language_buttons(bot):
    await bot.send(bot.text("/start", lang="ru"))

    assert bot.texts_to(CLIENT_ID) == [GREETINGS["ru"]]
    assert bot.buttons_to(CLIENT_ID) == LANG_BUTTONS


async def test_language_button_rewrites_the_greeting(bot):
    await bot.send(bot.click("lang:en"))

    [edit] = bot.calls("editMessageText")
    assert edit["text"] == GREETINGS["en"]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "known bug: webhook mode builds a fresh Application per update with no "
        "persistence, so context.user_data is empty on the next message and the "
        "chosen language is forgotten - only the greeting text changes"
    ),
)
async def test_chosen_language_sticks_for_the_next_message(bot):
    await bot.send(bot.click("lang:en"))
    await bot.send(bot.text("/help"))

    assert bot.texts_to(CLIENT_ID)[-1] == HELP["en"]


def test_catalog_summary_follows_category_order_and_skips_empty(db):
    db.tables["products"] = [
        {**PRODUCT, "category": "кулони"},
        {**PRODUCT, "category": "кольє"},
        {**PRODUCT, "category": "кольє"},
        {**PRODUCT, "category": "сережки", "in_stock": False},
    ]

    text = catalog_text("en")

    assert text.splitlines()[2:4] == ["• Necklaces: 2", "• Pendants: 1"]
    assert "Earrings" not in text


def test_empty_catalog_summary_is_none(db):
    db.tables["products"] = []
    assert catalog_text("uk") is None


def test_every_catalog_category_is_listed_and_translated():
    # catalog_text() silently drops categories missing from CATEGORY_ORDER.
    categories = {p["category"] for p in CATALOG}
    assert categories <= set(CATEGORY_ORDER)
    for lang, labels in CATEGORY_LABELS.items():
        assert categories <= set(labels), lang


async def test_admin_commands_refuse_everyone_else(bot, db):
    db.fail["messages"] = AssertionError("stats must not be queried for a stranger")

    await bot.send(bot.text("/stats"))

    assert bot.texts_to(CLIENT_ID) == ["Not authorized."]


async def test_stats_for_the_owner(bot, db):
    db.tables["messages"] = [{"matched": True}, {"matched": False}, {"matched": True}]
    db.tables["missed"] = [{"id": 1}]

    await bot.send(bot.text("/stats", user_id=ADMIN_ID))

    [reply] = bot.texts_to(ADMIN_ID)
    assert "Total messages: 3" in reply
    assert "Matched: 2" in reply
    assert "Handoff: 1" in reply
    assert "Missed logged: 1" in reply


async def test_missed_lists_recent_questions_trimmed(bot, db):
    db.tables["missed"] = [{"ts": "2026-10-07T10:11:12.345+00:00", "user_id": 5, "text": "x" * 100}]

    await bot.send(bot.text("/missed", user_id=ADMIN_ID))

    [reply] = bot.texts_to(ADMIN_ID)
    assert reply.splitlines()[1] == "[2026-10-07 10:11:12] 5: " + "x" * 80


async def test_missed_when_there_is_nothing(bot, db):
    await bot.send(bot.text("/missed", user_id=ADMIN_ID))
    assert bot.texts_to(ADMIN_ID) == ["No missed questions yet."]


@pytest.mark.parametrize(
    ("user", "expected"),
    [
        (None, "(невідомий клієнт)"),
        (SimpleNamespace(id=7, first_name="Ira", username=None), "Ira (без ніка, id 7)"),
        (SimpleNamespace(id=7, first_name="Ira", username="ira"), "Ira @ira"),
    ],
)
def test_format_client(user, expected):
    assert notify.format_client(user) == expected


async def test_owner_ping_failure_never_breaks_the_client_flow():
    async def broken_send(chat_id, text):
        raise RuntimeError("telegram down")

    await notify.notify_owner(SimpleNamespace(send_message=broken_send), "hi")


async def test_no_owner_configured_means_no_ping(monkeypatch):
    sent = []

    async def send(chat_id, text):
        sent.append(chat_id)

    monkeypatch.setattr(notify, "ADMIN_USER_ID", 0)
    await notify.notify_owner(SimpleNamespace(send_message=send), "hi")
    assert sent == []
