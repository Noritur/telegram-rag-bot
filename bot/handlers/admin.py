import asyncio
import logging
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import ADMIN_USER_ID
from bot.storage.logger import get_recent_missed, get_stats

log = logging.getLogger(__name__)


def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not user or user.id != ADMIN_USER_ID:
            log.warning(
                "admin command rejected: user_id=%s expected=%s",
                user.id if user else None,
                ADMIN_USER_ID,
            )
            if update.message:
                await update.message.reply_text("Not authorized.")
            return
        await func(update, context)

    return wrapper


@admin_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        s = await asyncio.to_thread(get_stats, 7)
    except Exception:
        log.exception("/stats failed")
        await update.message.reply_text("Stats query failed — see logs.")
        return

    text = (
        f"Stats (last {s['days']}d):\n"
        f"• Total messages: {s['total_messages']}\n"
        f"• Matched: {s['matched']}\n"
        f"• Handoff: {s['handoff']}\n"
        f"• Missed logged: {s['missed_logged']}"
    )
    await update.message.reply_text(text)


@admin_only
async def missed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        items = await asyncio.to_thread(get_recent_missed, 20)
    except Exception:
        log.exception("/missed failed")
        await update.message.reply_text("Missed query failed — see logs.")
        return

    if not items:
        await update.message.reply_text("No missed questions yet.")
        return

    lines = [f"Recent missed ({len(items)}):"]
    for it in items:
        ts = (it.get("ts") or "")[:19].replace("T", " ")
        text = (it.get("text") or "")[:80]
        lines.append(f"[{ts}] {it.get('user_id')}: {text}")
    await update.message.reply_text("\n".join(lines))
