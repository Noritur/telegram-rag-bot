"""Gift-question parser.

"Що подарувати мамі до 1000 грн?" is the most common question a jewelry shop
gets, and it fell into the handoff branch: a generic question embeds far from
any single product description (0.33-0.38 against the 0.4 threshold), and a
vector cannot filter by price at all. So gift questions skip the threshold:
the budget becomes a hard price filter, the recipient and the occasion become
catalog tags to rank by (bot.rag.retriever.search_gift).

Questions about delivery, payment, returns or gift wrapping mention a gift too,
but a person has to answer those - they stay on the ordinary path.
"""

import re
from dataclasses import dataclass

_GIFT = re.compile(r"подар\w*|\bgift\w*|\bpresent\b")

# Catalog tags (bot/data/catalog.json) per recipient. Stems, so the Ukrainian
# and Russian case endings match: мамі, маме, мамочці.
_RECIPIENTS = [
    (r"\bмам\w*|\bматер\w*|\bсвекру\w*|\bтещ\w*|\bбабус\w*|\bбабуш\w*"
     r"|\bmom\b|\bmum\b|\bmother\b|\bgrandma\b|\bgrandmother\b", {"для мами"}),
    (r"\bдружин\w*|\bдівчин(?![кц])\w*|\bдевушк\w*|\bжен(?:а|е|у|ой|ы)\b|\bжінц\w*|\bжінк\w*"
     r"|\bженщин\w*|\bкохан(?:ій|а|у|ої)\b|\bлюбим(?:ой|ая|ую)\b|\bсестр\w*"
     r"|\bwife\b|\bgirlfriend\b|\bher\b|\bwoman\b|\bwomen\b|\blady\b|\bsister\b", {"для неї"}),
    (r"\bподруг\w*|\bподружк\w*|\bподружц\w*|\bfriend\w*|\bbestie\b", {"для подруги"}),
    (r"\bчоловік\w*|\bхлоп\w*|\bтат(?:о|ові|у|а|ом|ка|кові|ку)\b|\bбрат\w*|\bсин(?:а|у|ові|ом)?\b"
     r"|\bмуж(?:у|а|ем|чин\w*)?\b|\bпарн(?:ю|я|ем)\b|\bпап\w*|\bкохан(?:ому|ий|ого)\b"
     r"|\bлюбим(?:ому|ый|ого)\b|\bhusband\b|\bboyfriend\b|\bdad\b|\bfather\b|\bbrother\b"
     r"|\bson\b|\bhim\b|\bmen\b|\bman\b|\bguy\b", {"для чоловіка"}),
    (r"\bдон[ьеі]\w*|\bдоч\w*|\bдитин\w*|\bдіт\w*|\bребен\w*|\bребён\w*|\bдет(?:ям|ей|и)\b"
     r"|\bдівчинк\w*|\bдівчинц\w*|\bдевочк\w*|\bпідліт\w*|\bподрост\w*|\bшкіл\w*|\bшкол\w*"
     r"|\bdaughter\b|\bkids?\b|\bchild\w*|\bteen\w*", {"для дитини", "для підлітка"}),
    (r"\bнарече\w*|\bневест\w*|\bbride\b", {"для нареченої"}),
]

# Occasion tags exist in both languages in the catalog: match either.
_OCCASIONS = [
    (r"день\s+народжен|днем\s+народжен|днюх|день\s+рожден|днем\s+рожден|birthday|\bbday\b",
     {"на день народження", "birthday"}),
    (r"річниц|годовщин|anniversar", {"на річницю", "anniversary"}),
    (r"ювіле|юбиле|jubilee", {"на ювілей", "jubilee"}),
    (r"весілл|свадьб|wedding", {"весілля", "wedding"}),
    (r"заручин|помолвк|engagement", {"на заручини", "engagement"}),
    (r"валентин|valentine|14\s+лютого|14\s+февраля", {"Valentine", "для закоханих", "couple"}),
]

# A person answers these, even when a gift is mentioned.
_SERVICE = re.compile(
    r"достав|відправ|отправ|оплат|платіж|поверн|возврат|обмін|обмен|упаков|листівк"
    r"|открытк|сертифікат|сертификат|коли\s+прийде|когда\s+прид|deliver|shipping|\bship\b"
    r"|return|refund|\bpay|wrap|gift\s+card|voucher|exchange"
)

_NUMBER = r"(\d+(?:[.,]\d+)?)\s*(к|k|тис\w*|тыс\w*)?"
_BUDGET_BEFORE = re.compile(
    r"(?:\bдо|в\s+межах|у\s+межах|в\s+пределах|не\s+дорожче|не\s+дороже|\bмаксимум|\bмакс"
    r"|\bбюджет\w*|\bunder|up\s+to|\bbelow|less\s+than|\bwithin|\bmax\w*|\bbudget(?:\s+of)?"
    r"|\bза)\s*" + _NUMBER
)
_BUDGET_CURRENCY = re.compile(_NUMBER + r"\s*(?:грн|гривен\w*|гривн\w*|uah|₴|hrn)")
_CHEAP = re.compile(r"недорог|дешев|бюджетн|\bcheap|inexpensive|affordable")
CHEAP_BUDGET = 1000
_MIN_BUDGET, _MAX_BUDGET = 100, 100_000


@dataclass(frozen=True)
class GiftQuery:
    budget: int | None
    recipients: frozenset[str]
    occasions: frozenset[str]


def _amount(value: str, multiplier: str | None) -> int | None:
    amount = float(value.replace(",", "."))
    if multiplier:
        amount *= 1000
    amount = int(round(amount))
    return amount if _MIN_BUDGET <= amount <= _MAX_BUDGET else None


def parse_budget(text: str) -> int | None:
    text = re.sub(r"(\d)[\s ](\d{3})\b", r"\1\2", text)  # "1 000" -> "1000"
    for pattern in (_BUDGET_BEFORE, _BUDGET_CURRENCY):
        for m in pattern.finditer(text):
            amount = _amount(m.group(1), m.group(2))
            if amount is not None:
                return amount
    return CHEAP_BUDGET if _CHEAP.search(text) else None


def _tags(text: str, table) -> frozenset[str]:
    found: set[str] = set()
    for pattern, tags in table:
        if re.search(pattern, text):
            found |= tags
    return frozenset(found)


def parse_gift(text: str) -> GiftQuery | None:
    text = text.strip().lower()
    if _SERVICE.search(text):
        return None
    budget = parse_budget(text)
    recipients = _tags(text, _RECIPIENTS)
    occasions = _tags(text, _OCCASIONS)
    if not (_GIFT.search(text) or budget or recipients or occasions):
        return None
    return GiftQuery(budget, recipients, occasions)
