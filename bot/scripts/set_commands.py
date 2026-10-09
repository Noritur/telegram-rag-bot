"""Register the bot's command menu with Telegram, once per bot.

The menu behind the "Menu" button (/start, /catalog, /help in uk/ru/en, plus
/stats and /missed for the owner only) is stored on Telegram's side. bot.main
sets it on startup, but that only runs in local polling mode, so a bot that has
only ever run as a webhook on Vercel has no menu at all.

Prompts for the bot token (hidden input), runs the same setup_commands as
bot.main and reads the menu back. Prints statuses only, never the token.

Usage: .venv/bin/python bot/scripts/set_commands.py
"""

import asyncio
import getpass
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from telegram import Bot, BotCommandScopeChat  # noqa: E402

from bot.config import ADMIN_USER_ID  # noqa: E402
from bot.main import setup_commands  # noqa: E402

# bot.main turns on INFO logging; httpx would print request URLs with the token.
logging.getLogger("httpx").setLevel(logging.WARNING)


async def register_menu(bot: Bot) -> tuple[str, list[str], list[str]]:
    """Set the menu and read it back: (username, public commands, owner commands)."""
    me = await bot.get_me()
    await setup_commands(SimpleNamespace(bot=bot))
    public = [c.command for c in await bot.get_my_commands(language_code="uk")]
    owner = (
        [c.command for c in await bot.get_my_commands(scope=BotCommandScopeChat(ADMIN_USER_ID))]
        if ADMIN_USER_ID
        else []
    )
    return me.username, public, owner


async def run(token: str) -> None:
    async with Bot(token) as bot:
        username, public, owner = await register_menu(bot)
    print(f"@{username}: меню для клієнтів {['/' + c for c in public]}")
    print(f"           меню для тебе {['/' + c for c in owner] or '— ADMIN_USER_ID не задано'}")


def main() -> None:
    token = getpass.getpass("Токен бота від @BotFather (ввід прихований): ").strip()
    if not token:
        sys.exit("Порожній ввід. Нічого не змінено.")
    try:
        asyncio.run(run(token))
    except Exception as e:  # InvalidToken, network: say what, not the token
        sys.exit(f"Не вдалося: {type(e).__name__}. Меню не змінено.")
    print("\nDONE: перезапусти чат з ботом, і з'явиться кнопка «Меню».")


if __name__ == "__main__":
    main()
