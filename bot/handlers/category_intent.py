"""Category-listing detector.

"Які кольє є, перелічи" showed 3 of 9 necklaces - retrieval always returns the
top 3 - and "а напиши всі 9" then went to the owner as an unanswered question,
while /catalog itself says "Кольє: 9". A request to list one category is
answered straight from the database: every in-stock item of that category,
optionally within a budget.

A category plus an attribute ("покажи кольє з аметисту") stays on the RAG path,
which finds exactly the amethyst; a category for someone or for an occasion
("браслети для мами") belongs to the gift route, which ranks by those tags.
"""

import re
from dataclasses import dataclass

from bot.handlers.gift_intent import GIFT_WORD, parse_budget, parse_gift

# Keys are the catalog's category values (bot.handlers.commands.CATEGORY_ORDER).
_CATEGORIES = {
    "кольє": r"кольє|колье|намист\w*|necklaces?\b",
    "браслети": r"браслет\w*|bracelets?\b",
    "сережки": r"сережк\w*|серёжк\w*|серьг\w*|earrings?\b",
    "перстні": r"перст\w*|каблуч\w*|кільц\w*|кольц\w*|колечк\w*|\brings?\b",
    "кулони": r"кулон\w*|підвіс\w*|подвес\w*|pendants?\b",
}
_LIST = re.compile(
    r"\bвсі\b|\bусі\b|\bвсе\b|\bвсё\b|перелічи\w*|перерахуй\w*|перечисл\w*|покажи\w*"
    r"|покажіть|\bсписок\b|\bякі\b|\bкакие\b|\bshow\b|\blist\b|\ball\b|\bwhich\b"
    r"|\bwhat\b.*\bhave\b"
)
# "з аметисту", "с жемчугом", "with pearls": a specific item, not the whole category.
_ATTRIBUTE = re.compile(r"\bз\b|\bіз\b|\bзі\b|\bс\b|\bсо\b|\bиз\b|\bwith\b|\bmade of\b")


@dataclass(frozen=True)
class CategoryQuery:
    category: str
    budget: int | None


def parse_category(text: str) -> CategoryQuery | None:
    text = text.strip().lower()
    found = [key for key, pattern in _CATEGORIES.items() if re.search(pattern, text)]
    if len(found) != 1 or not _LIST.search(text) or _ATTRIBUTE.search(text):
        return None
    gift = parse_gift(text)
    if gift and (gift.recipients or gift.occasions or GIFT_WORD.search(text)):
        return None
    return CategoryQuery(found[0], parse_budget(text))
