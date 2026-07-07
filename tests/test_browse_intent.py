"""Pure-regex test for browse-intent detection — no telegram deps needed.

Run: python3 -m tests.test_browse_intent
"""

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


def main() -> None:
    for q in BROWSE:
        assert is_browse_query(q), f"should be browse: {q!r}"
    for q in NOT_BROWSE:
        assert not is_browse_query(q), f"should NOT be browse: {q!r}"
    print(f"browse intent: ok ({len(BROWSE)} positive, {len(NOT_BROWSE)} negative)")


if __name__ == "__main__":
    main()
