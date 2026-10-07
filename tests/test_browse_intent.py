"""Browse-intent detection: generic "what do you have?" goes to the catalog,
anything specific stays on the RAG path. Pure regex, no fakes needed."""

import pytest

from bot.handlers.browse import is_browse_query

BROWSE = [
    "Шо у вас є?",
    "що у вас є",
    "Что есть?",
    "что у вас есть в наличии?",
    "каталог",
    "Асортимент",
    "покажіть все",
    "Покажите всё",
    "привіт, що є?",
    "Здравствуйте, что у вас есть?",
    "what do you have?",
    "Show me the catalog",
    "catalog",
]

NOT_BROWSE = [
    "що у вас є з аметисту?",
    "есть ли браслеты с бирюзой",
    "скільки коштує кольє з місячним каменем",
    "покажіть сережки з опалом",
    "what do you have for anniversaries?",
    "do you ship to spain",
    "хочу подарунок дружині до 50 евро",
    "чи є доставка в польщу",
]


@pytest.mark.parametrize("query", BROWSE)
def test_generic_question_is_browse(query):
    assert is_browse_query(query)


@pytest.mark.parametrize("query", NOT_BROWSE)
def test_specific_question_stays_on_rag(query):
    assert not is_browse_query(query)
