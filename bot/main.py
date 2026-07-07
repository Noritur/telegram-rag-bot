import logging

from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.config import ADMIN_USER_ID, TELEGRAM_BOT_TOKEN
from bot.handlers.admin import missed, stats
from bot.handlers.chat import chat
from bot.handlers.commands import catalog, help_cmd, start, switch_lang
from bot.handlers.order import nav_catalog, order_callback


PUBLIC_COMMANDS = {
    "uk": [
        ("start", "Привітання"),
        ("catalog", "Категорії"),
        ("help", "Як це працює"),
    ],
    "ru": [
        ("start", "Приветствие"),
        ("catalog", "Категории"),
        ("help", "Как это работает"),
    ],
    "en": [
        ("start", "Welcome"),
        ("catalog", "Browse collection"),
        ("help", "How this works"),
    ],
}

ADMIN_EXTRA = [
    ("stats", "Adm: статистика за 7 днів"),
    ("missed", "Adm: останні питання без відповіді"),
]


async def setup_commands(application: Application) -> None:
    bot = application.bot

    # Localized public command lists.
    for lang, cmds in PUBLIC_COMMANDS.items():
        await bot.set_my_commands(
            [BotCommand(c, d) for c, d in cmds],
            scope=BotCommandScopeDefault(),
            language_code=lang,
        )

    # Generic fallback (Telegram clients without specific lang).
    await bot.set_my_commands(
        [BotCommand(c, d) for c, d in PUBLIC_COMMANDS["en"]],
        scope=BotCommandScopeDefault(),
    )

    # Admin gets all public + extras, scoped to their chat only.
    if ADMIN_USER_ID:
        admin_cmds = PUBLIC_COMMANDS["uk"] + ADMIN_EXTRA
        await bot.set_my_commands(
            [BotCommand(c, d) for c, d in admin_cmds],
            scope=BotCommandScopeChat(chat_id=ADMIN_USER_ID),
        )
        logging.info("admin commands set for chat_id=%s", ADMIN_USER_ID)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing in .env")
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(setup_commands)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("catalog", catalog))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("missed", missed))
    app.add_handler(CallbackQueryHandler(switch_lang, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(order_callback, pattern=r"^order:"))
    app.add_handler(CallbackQueryHandler(nav_catalog, pattern=r"^nav:catalog$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    logging.info("Murmure bot starting in polling mode...")
    app.run_polling()


if __name__ == "__main__":
    main()
