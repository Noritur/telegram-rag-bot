"""Gift-question parser: bot/handlers/gift_intent.py."""

import pytest

from bot.handlers.gift_intent import CHEAP_BUDGET, GiftQuery, parse_budget, parse_gift


@pytest.mark.parametrize(
    ("text", "budget"),
    [
        ("що подарувати до 1100 грн", 1100),
        ("подарунок мамі до 1000 грн", 1000),
        ("подарунок до 1 000 грн", 1000),
        ("подарунок у межах 1500", 1500),
        ("не дорожче 2000 гривень", 2000),
        ("подарок до 1,5к", 1500),
        ("подарунок до 2 тис", 2000),
        ("gift under 1000", 1000),
        ("a present up to 800 uah", 800),
        ("бюджет 1500", 1500),
        ("подарунок за 900 грн", 900),
        ("щось недороге для подруги", CHEAP_BUDGET),
        ("cheap gift", CHEAP_BUDGET),
        ("подарунок", None),
        # a date or a size is not a budget
        ("подарунок до 14 лютого", None),
        ("кольє 45 см", None),
    ],
)
def test_budget(text, budget):
    assert parse_budget(text.lower()) == budget


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Подарунок мамі до 1000 грн", GiftQuery(1000, frozenset({"для мами"}), frozenset())),
        ("що подарувати дружині на річницю?",
         GiftQuery(None, frozenset({"для неї"}), frozenset({"на річницю", "anniversary"}))),
        ("подарок маме на день рождения",
         GiftQuery(None, frozenset({"для мами"}), frozenset({"на день народження", "birthday"}))),
        ("gift for my wife under 1500", GiftQuery(1500, frozenset({"для неї"}), frozenset())),
        ("what do you have for a gift?", GiftQuery(None, frozenset(), frozenset())),
        ("а є щось для чоловіків?", GiftQuery(None, frozenset({"для чоловіка"}), frozenset())),
        ("подарунок доньці", GiftQuery(None, frozenset({"для дитини", "для підлітка"}), frozenset())),
        ("подарунок для дівчинки", GiftQuery(None, frozenset({"для дитини", "для підлітка"}), frozenset())),
        ("подарунок дівчині", GiftQuery(None, frozenset({"для неї"}), frozenset())),
        ("що подарувати на 14 лютого",
         GiftQuery(None, frozenset(), frozenset({"Valentine", "для закоханих", "couple"}))),
        ("браслет до 1000 грн", GiftQuery(1000, frozenset(), frozenset())),
    ],
)
def test_gift_questions(text, expected):
    assert parse_gift(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "кольє з аметисту",
        "хочу замовити",
        "коли прийде замовлення?",
        "а є щось синє?",  # "син" (son) must not catch "синє"
        # a person answers these, even with a gift in them
        "подарункова упаковка є?",
        "чи доставите подарунок у Польщу?",
        "як оплатити подарунок?",
        "can I return a gift?",
        "є подарунковий сертифікат?",
    ],
)
def test_not_a_gift_question(text):
    assert parse_gift(text) is None
