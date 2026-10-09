"""Category-listing detector: bot/handlers/category_intent.py."""

import pytest

from bot.handlers.category_intent import CategoryQuery, parse_category


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # live phrases from 2026-10-09
        ("Які кольє є перечисли", CategoryQuery("кольє", None)),
        ("Тут написано що у тебе є 9 кольє можеш перечислити?", CategoryQuery("кольє", None)),
        ("покажи всі браслети", CategoryQuery("браслети", None)),
        ("покажи всі браслети до 1000 грн", CategoryQuery("браслети", 1000)),
        ("які сережки у вас є?", CategoryQuery("сережки", None)),
        ("перелічи каблучки", CategoryQuery("перстні", None)),
        ("какие кольца есть", CategoryQuery("перстні", None)),
        ("покажите все подвески", CategoryQuery("кулони", None)),
        ("show me all necklaces", CategoryQuery("кольє", None)),
        ("what earrings do you have?", CategoryQuery("сережки", None)),
        ("list rings under 1500", CategoryQuery("перстні", 1500)),
    ],
)
def test_listing_a_category(text, expected):
    assert parse_category(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "покажи кольє з аметисту",  # an attribute: RAG finds exactly that
        "earrings with pearls",
        "покажи всі браслети для мами",  # recipient: the gift route ranks by it
        "які сережки подарувати на день народження",
        "каблучка 17 розміру є?",  # no listing word
        "браслет з аметисту",
        "покажи кольє і браслети",  # two categories
        "хочу замовити",
        "що у вас є?",  # browse, not a category
        "А напиши всі 9",  # no category named: known limit, no memory of the chat
    ],
)
def test_not_a_category_listing(text):
    assert parse_category(text) is None
