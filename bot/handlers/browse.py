"""Browse-intent detector.

Generic "what do you have?"-style queries embed poorly against per-product
vectors and used to fall into the handoff branch — the single most common
first question a buyer asks. Full-match patterns keep specific queries
("що у вас є з аметисту?") on the RAG path.
"""

import re

_GREETING = r"(?:(?:привіт|привет|здравствуйте|добрий день|добрый день|hi|hello|hey)[\s,!.\-]*)?"

_CORE = [
    # uk/ru: "що(шо/что) [у вас] є(есть) [в наявності/в наличии]"
    r"(?:що|шо|что)\s+(?:у\s+вас\s+)?(?:є|есть)(?:\s+(?:в\s+наявності|в\s+наличии))?",
    r"(?:що|шо|что)\s+(?:ви\s+)?(?:продаєте|продаете|продаете)",
    r"каталог",
    r"асортимент",
    r"ассортимент",
    r"покаж(?:іть|ите|и)(?:\s+(?:все|всё))?",
    # en
    r"what\s+(?:do\s+you\s+have|have\s+you\s+got|is\s+available|'?s\s+available)",
    r"show\s+me(?:\s+(?:everything|all|the\s+catalog))?",
    r"catalog(?:ue)?",
]

BROWSE_RE = re.compile(
    r"^" + _GREETING + r"(?:" + "|".join(_CORE) + r")[\s?!.)]*$",
    re.IGNORECASE,
)


def is_browse_query(text: str) -> bool:
    return bool(BROWSE_RE.match(text.strip().lower()))
