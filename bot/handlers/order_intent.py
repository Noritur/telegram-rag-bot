"""Bare order-intent detector.

"Хочу замовити" typed as text (often the label of the order button, retyped)
embeds poorly against product vectors, fell below the relevance threshold and
got a "we don't have this" handoff - while the client was ready to buy. Only a
bare intent matches here; "хочу замовити кольє з аметисту" names a product and
stays on the RAG path, which answers with a proper order button.
"""

import re

_GREETING = r"(?:(?:привіт|привет|здравствуйте|добрий день|добрый день|hi|hello|hey)[\s,!.\-]*)?"

_CORE = [
    # uk: "[хочу|хотіла б|можна] замовити [щось]", "як замовити", "оформити замовлення"
    r"(?:(?:я\s+)?(?:хочу|хотів\s+би|хотіла\s+б|можна|бажаю)\s+)?замовити(?:\s+(?:щось|у\s+вас))?",
    r"як\s+(?:можна\s+)?(?:замовити|зробити\s+замовлення|оформити\s+замовлення)",
    r"(?:оформити|зробити)\s+замовлення",
    # ru
    r"(?:(?:я\s+)?(?:хочу|хотел\s+бы|хотела\s+бы|можно)\s+)?(?:заказать|сделать\s+заказ)(?:\s+(?:что-нибудь|у\s+вас))?",
    r"как\s+(?:можно\s+)?(?:заказать|сделать\s+заказ|оформить\s+заказ)",
    r"оформить\s+заказ",
    # en
    r"(?:i\s+(?:want|would\s+like|'d\s+like)\s+to\s+)?(?:order|place\s+an\s+order|buy)(?:\s+something)?",
    r"how\s+(?:do\s+i|can\s+i|to)\s+(?:order|place\s+an\s+order|buy)",
]

ORDER_INTENT_RE = re.compile(
    r"^" + _GREETING + r"(?:" + "|".join(_CORE) + r")[\s?!.)]*$",
    re.IGNORECASE,
)


def is_order_intent(text: str) -> bool:
    return bool(ORDER_INTENT_RE.match(text.strip().lower()))
