import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import RELEVANCE_THRESHOLD
from bot.data.prompts import HANDOFF, LLM_ERROR
from bot.handlers.commands import resolve_lang
from bot.rag.llm import generate_reply
from bot.rag.retriever import search
from bot.storage.logger import safe_log_message, safe_log_missed

log = logging.getLogger(__name__)


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text
    user = update.effective_user
    user_id = user.id if user else 0
    lang = resolve_lang(context, user.language_code if user else None)

    try:
        products = await asyncio.to_thread(search, text)
    except Exception:
        log.exception("retrieval failed")
        await update.message.reply_text(LLM_ERROR[lang])
        return

    top_sim = products[0]["similarity"] if products else None
    matched = bool(products and top_sim is not None and top_sim >= RELEVANCE_THRESHOLD)

    # Fire-and-forget logging — don't block user reply on Supabase latency.
    asyncio.create_task(
        asyncio.to_thread(safe_log_message, user_id, text, matched, top_sim)
    )

    if not matched:
        asyncio.create_task(asyncio.to_thread(safe_log_missed, user_id, text))
        log.info("handoff: query=%r top_sim=%s", text, top_sim)
        await update.message.reply_text(HANDOFF[lang])
        return

    try:
        reply = await asyncio.to_thread(generate_reply, text, products, lang)
    except Exception:
        log.exception("LLM call failed")
        await update.message.reply_text(LLM_ERROR[lang])
        return

    if not reply.strip():
        log.warning("empty LLM reply: query=%r", text)
        await update.message.reply_text(LLM_ERROR[lang])
        return

    log.info(
        "rag: query=%r matched=%d top_sim=%.3f", text, len(products), top_sim
    )
    await update.message.reply_text(reply)
