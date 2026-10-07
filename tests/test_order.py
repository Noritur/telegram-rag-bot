"""Order button and catalog navigation: bot/handlers/order.py."""

import json
from pathlib import Path

import pytest

from bot.handlers.order import (
    CATALOG_EMPTY_NAV,
    ORDER_CONFIRM,
    ORDER_ERROR,
    reply_cta_markup,
    short_title,
)
from tests.conftest import ADMIN_ID, CLIENT_ID, PRODUCT

CATALOG = json.loads((Path(__file__).parent.parent / "bot" / "data" / "catalog.json").read_text())


async def test_order_click_saves_lead_pings_owner_and_confirms(bot, db):
    db.tables["products"] = [PRODUCT]

    await bot.send(bot.click("order:amethyst-bracelet"))

    [order] = db.inserted("orders")
    assert order.row == {
        "user_id": CLIENT_ID,
        "username": "olena_buyer",
        "product_id": "amethyst-bracelet",
        "product_name": "Браслет з аметисту",
    }
    # Regression guard (July 2026): RLS gives the bot role INSERT but no SELECT
    # on orders, so asking for the row back rejects the whole insert (42501).
    assert order.returning == "minimal"
    [ping] = bot.texts_to(ADMIN_ID)
    assert "Браслет з аметисту" in ping and "@olena_buyer" in ping
    assert "увага" not in ping
    assert bot.texts_to(CLIENT_ID) == [ORDER_CONFIRM["uk"]]
    assert len(bot.calls("answerCallbackQuery")) == 1
    # Buttons removed from the answered message, so a second tap cannot double-order.
    [cleared] = bot.calls("editMessageReplyMarkup")
    assert cleared["message_id"] == 50


async def test_failed_db_write_still_reaches_the_owner(bot, db):
    db.tables["products"] = [PRODUCT]
    db.fail["orders"] = RuntimeError("42501 permission denied")

    await bot.send(bot.click("order:amethyst-bracelet"))

    [ping] = bot.texts_to(ADMIN_ID)
    assert "Браслет з аметисту" in ping
    assert "запис у базу не пройшов" in ping
    assert bot.texts_to(CLIENT_ID) == [ORDER_CONFIRM["uk"]]


async def test_unknown_product_is_refused_without_side_effects(bot, db):
    db.tables["products"] = []

    await bot.send(bot.click("order:no-such-thing"))

    assert bot.texts_to(CLIENT_ID) == [ORDER_ERROR["uk"]]
    assert db.inserted("orders") == []
    assert bot.texts_to(ADMIN_ID) == []


async def test_product_lookup_failure_is_refused(bot, db):
    db.fail["products"] = RuntimeError("supabase down")

    await bot.send(bot.click("order:amethyst-bracelet", lang="en"))

    assert bot.texts_to(CLIENT_ID) == [ORDER_ERROR["en"]]
    assert db.inserted("orders") == []


async def test_catalog_button_shows_categories(bot, db):
    db.tables["products"] = [PRODUCT]

    await bot.send(bot.click("nav:catalog"))

    [reply] = bot.texts_to(CLIENT_ID)
    assert "• Браслети: 1" in reply


async def test_catalog_button_with_empty_catalog(bot, db):
    db.tables["products"] = []

    await bot.send(bot.click("nav:catalog", lang="ru"))

    assert bot.texts_to(CLIENT_ID) == [CATALOG_EMPTY_NAV["ru"]]


def test_every_product_id_fits_telegram_callback_limit():
    # Telegram rejects callback_data over 64 bytes, and with it the whole answer.
    too_long = [p["id"] for p in CATALOG if len(f"order:{p['id']}".encode()) > 64]
    assert too_long == []


@pytest.mark.parametrize(
    ("name", "title"),
    [
        ("Кольє 'Лавандова Ніч' з аметисту", "Лавандова Ніч"),
        ("Браслет 'Тигрове Око'", "Тигрове Око"),
        ("Кольє «Місячна Дорога»", "Місячна Дорога"),
        ("Браслет з аметисту", "Браслет з аметисту"),
    ],
)
def test_order_button_label_uses_the_quoted_title(name, title):
    assert short_title(name) == title


def test_every_catalog_product_gets_a_short_named_button():
    for p in CATALOG:
        [order_btn], _ = reply_cta_markup("uk", p).inline_keyboard
        assert order_btn.callback_data == f"order:{p['id']}"
        assert order_btn.text.startswith("Хочу замовити: ")
        assert "'" not in order_btn.text and len(order_btn.text) <= 40, order_btn.text


def test_no_product_means_catalog_button_only():
    [[only]] = reply_cta_markup("en", None).inline_keyboard
    assert only.callback_data == "nav:catalog"
