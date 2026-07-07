"""Vercel Function entry — Telegram webhook receiver.

Each invocation builds a fresh PTB Application via async context manager,
then dispatches one Update. Cold start ~2-3s, warm ~500ms-1s. Acceptable
for Telegram (60s server timeout).

Security: incoming POST must carry header `X-Telegram-Bot-Api-Secret-Token`
matching WEBHOOK_SECRET env var. Telegram sends this on every webhook delivery
when secret_token was passed at setWebhook time. Without match → 403 before
any LLM/Supabase work.
"""

import asyncio
import json
import logging
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# When running inside Vercel, project root may not be on sys.path automatically.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.config import TELEGRAM_BOT_TOKEN, WEBHOOK_SECRET
from bot.handlers.admin import missed, stats
from bot.handlers.chat import chat
from bot.handlers.commands import catalog, help_cmd, start, switch_lang
from bot.handlers.order import nav_catalog, order_callback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

TELEGRAM_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


def _build_app() -> Application:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("catalog", catalog))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("missed", missed))
    app.add_handler(CallbackQueryHandler(switch_lang, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(order_callback, pattern=r"^order:"))
    app.add_handler(CallbackQueryHandler(nav_catalog, pattern=r"^nav:catalog$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    return app


async def _process(body: dict) -> None:
    app = _build_app()
    async with app:
        update = Update.de_json(body, app.bot)
        await app.process_update(update)


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        # Verify Telegram secret token before any work.
        sent_secret = self.headers.get(TELEGRAM_SECRET_HEADER, "")
        if not WEBHOOK_SECRET or sent_secret != WEBHOOK_SECRET:
            log.warning("rejected webhook POST: bad or missing secret token")
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"forbidden"}')
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(length) if length else b"{}"
            body = json.loads(body_bytes)
            asyncio.run(_process(body))
        except Exception:
            log.exception("webhook handler failed")
        # Always return 200 — Telegram retries are not helpful for app-side bugs.
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_GET(self) -> None:
        # Don't reveal internals — return 404 for any GET.
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error":"not_found"}')
