import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

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
