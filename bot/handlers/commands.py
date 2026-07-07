import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.rag.store import murmure

log = logging.getLogger(__name__)

GREETINGS = {
    "uk": (
        "Вітаю в Murmure.\n\n"
        "Я допоможу обрати прикраси з натурального каміння — "
        "просто напишіть, що шукаєте.\n\n"
        "/catalog — переглянути асортимент\n"
        "/help — як це працює"
    ),
    "ru": (
        "Здравствуйте, это Murmure.\n\n"
        "Помогу подобрать украшения из натурального камня — "
        "просто напишите, что ищете.\n\n"
        "/catalog — посмотреть ассортимент\n"
        "/help — как это работает"
    ),
    "en": (
        "Welcome to Murmure.\n\n"
        "I'll help you find natural stone jewelry — "
        "just tell me what you're looking for.\n\n"
        "/catalog — browse the collection\n"
        "/help — how this works"
    ),
}

LANG_BUTTONS = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("Українська", callback_data="lang:uk"),
            InlineKeyboardButton("Русский", callback_data="lang:ru"),
            InlineKeyboardButton("English", callback_data="lang:en"),
        ]
    ]
)


def detect_lang(code: str | None) -> str:
    if not code:
        return "en"
    code = code.lower()[:2]
    if code == "uk":
        return "uk"
    if code == "ru":
        return "ru"
    return "en"


def resolve_lang(context: ContextTypes.DEFAULT_TYPE, raw_code: str | None) -> str:
    saved = context.user_data.get("lang") if context.user_data else None
    return saved or detect_lang(raw_code)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    raw_code = user.language_code if user else None
    lang = resolve_lang(context, raw_code)
    log.info(
        "start: user_id=%s tg_lang=%r → resolved=%s",
        user.id if user else None,
        raw_code,
        lang,
    )
    await update.message.reply_text(GREETINGS[lang], reply_markup=LANG_BUTTONS)


async def switch_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    if not query.data.startswith("lang:"):
        return
    lang = query.data.split(":", 1)[1]
    if lang not in GREETINGS:
        return
    if context.user_data is not None:
        context.user_data["lang"] = lang
    log.info("lang switch: user_id=%s → %s", query.from_user.id, lang)
    await query.edit_message_text(GREETINGS[lang], reply_markup=LANG_BUTTONS)


HELP = {
    "uk": (
        "Опишіть, що шукаєте — камінь, колір, бюджет, привід. "
        "Я підберу серед своїх 15 виробів.\n\n"
        "/catalog — категорії з кількістю\n"
        "Кнопки нижче — перемикання мови.\n\n"
        "Складні питання передаю власниці."
    ),
    "ru": (
        "Опишите, что ищете — камень, цвет, бюджет, повод. "
        "Подберу из своих 15 изделий.\n\n"
        "/catalog — категории с количеством\n"
        "Кнопки ниже — переключение языка.\n\n"
        "Сложные вопросы передаю владелице."
    ),
    "en": (
        "Tell me what you're after — stone, color, budget, occasion. "
        "I'll match from my 15 pieces.\n\n"
        "/catalog — categories with counts\n"
        "Buttons below — switch language.\n\n"
        "Complex questions go to the owner."
    ),
}


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = resolve_lang(context, user.language_code if user else None)
    await update.message.reply_text(HELP[lang], reply_markup=LANG_BUTTONS)


CATALOG_INTRO = {
    "uk": "Наш асортимент:",
    "ru": "Наш ассортимент:",
    "en": "Our collection:",
}

CATEGORY_LABELS = {
    "uk": {
        "кольє": "Кольє",
        "браслети": "Браслети",
        "сережки": "Сережки",
        "перстні": "Перстні",
        "кулони": "Кулони",
    },
    "ru": {
        "кольє": "Колье",
        "браслети": "Браслеты",
        "сережки": "Серьги",
        "перстні": "Кольца",
        "кулони": "Кулоны",
    },
    "en": {
        "кольє": "Necklaces",
        "браслети": "Bracelets",
        "сережки": "Earrings",
        "перстні": "Rings",
        "кулони": "Pendants",
    },
}

CATALOG_FOOTER = {
    "uk": "Напишіть, що цікавить — допоможу обрати.",
    "ru": "Напишите, что интересует — помогу подобрать.",
    "en": "Tell me what catches your eye and I'll help you pick.",
}

CATALOG_EMPTY = {
    "uk": "Каталог тимчасово порожній. Спробуйте пізніше.",
    "ru": "Каталог временно пуст. Попробуйте позже.",
    "en": "The catalog is temporarily empty. Please check back later.",
}


CATEGORY_ORDER = ["кольє", "браслети", "сережки", "перстні", "кулони"]


def catalog_text(lang: str) -> str | None:
    """Category summary for both the /catalog command and inline nav buttons.
    Returns None when the catalog is empty."""
    rows = (
        murmure()
        .table("products")
        .select("category,in_stock")
        .eq("in_stock", True)
        .execute()
        .data
    )

    if not rows:
        return None

    counts: dict[str, int] = {}
    for r in rows:
        cat = r.get("category")
        if not cat:
            continue
        counts[cat] = counts.get(cat, 0) + 1

    labels = CATEGORY_LABELS[lang]
    lines = [CATALOG_INTRO[lang], ""]
    for cat in CATEGORY_ORDER:
        n = counts.get(cat, 0)
        if n == 0:
            continue
        lines.append(f"• {labels.get(cat, cat)}: {n}")
    lines.append("")
    lines.append(CATALOG_FOOTER[lang])
    return "\n".join(lines)


async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = resolve_lang(context, user.language_code if user else None)
    text = catalog_text(lang)
    await update.message.reply_text(text if text else CATALOG_EMPTY[lang])
