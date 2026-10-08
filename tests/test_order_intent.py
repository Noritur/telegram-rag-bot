"""Bare order-intent detection: "хочу замовити" with no product asks what to
order; anything naming a product stays on the RAG path. Pure regex."""

import pytest

from bot.handlers.order_intent import is_order_intent

BARE_INTENT = [
    "Хочу замовити",
    "хочу замовити!",
    "Як замовити?",
    "привіт, хочу замовити",
    "Оформити замовлення",
    "можна замовити?",
    "хотіла б замовити щось",
    "замовити",
    "Хочу заказать",
    "Как заказать?",
    "оформить заказ",
    "I want to order",
    "how do I order?",
]

NOT_BARE_INTENT = [
    "хочу замовити кольє з аметисту",
    "Хочу замовити: Лавандова Ніч",
    "коли прийде замовлення?",
    "замовлення 123 де?",
    "скільки коштує доставка",
    "хочу браслет",
    "what do you have?",
    "order status",
]


@pytest.mark.parametrize("text", BARE_INTENT)
def test_bare_intent_is_recognised(text):
    assert is_order_intent(text)


@pytest.mark.parametrize("text", NOT_BARE_INTENT)
def test_anything_more_specific_stays_on_rag(text):
    assert not is_order_intent(text)
