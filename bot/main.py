import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from bot.config import TELEGRAM_BOT_TOKEN
from bot.handlers.commands import start, switch_lang

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing in .env")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(switch_lang, pattern=r"^lang:"))
    logging.info("Murmure bot starting in polling mode...")
    app.run_polling()


if __name__ == "__main__":
    main()
