import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import RELEVANCE_THRESHOLD
from bot.data.prompts import HANDOFF, LLM_ERROR
from bot.handlers.browse import is_browse_query
from bot.handlers.commands import catalog, catalog_text, resolve_lang
from bot.handlers.notify import format_client, notify_owner
from bot.handlers.order import ORDER_WHAT, reply_cta_markup
from bot.handlers.order_intent import is_order_intent
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
    lang = await resolve_lang(update, context)

    # Generic "what do you have?" belongs to the catalog, not per-product RAG.
    if is_browse_query(text):
        log.info("browse intent shortcut: query=%r", text)
        asyncio.create_task(
            asyncio.to_thread(safe_log_message, user_id, text, True, None)
        )
        await catalog(update, context)
        return

    # Bare "хочу замовити": ask what to order instead of a "we don't have it"
    # handoff, and tell the owner a buyer is warming up.
    if is_order_intent(text):
        log.info("order intent without a product: query=%r", text)
        asyncio.create_task(
            asyncio.to_thread(safe_log_message, user_id, text, True, None)
        )
        try:
            summary = await asyncio.to_thread(catalog_text, lang)
        except Exception:
            log.exception("catalog fetch failed")
            summary = None
        await update.message.reply_text(
            ORDER_WHAT[lang] + (f"\n\n{summary}" if summary else "")
        )
        await notify_owner(
            context.bot,
            "Клієнт хоче замовити, але ще не обрав виріб.\n"
            f"Від: {format_client(user)} — можна написати напряму.",
        )
        return

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
        # The handoff promise must be real: ping the owner right away.
        await notify_owner(
            context.bot,
            "Питання без відповіді:\n"
            f"“{text}”\n"
            f"Від: {format_client(user)} — можна відповісти напряму.",
        )
        return

    try:
        reply = await asyncio.to_thread(generate_reply, text, products, lang)
    except Exception:
        log.exception("LLM call failed")
        await update.message.reply_text(LLM_ERROR[lang])
        return

    if not reply.text.strip():
        log.warning("empty LLM reply: query=%r", text)
        await update.message.reply_text(LLM_ERROR[lang])
        return

    # The button orders what the answer recommends, not the top retrieval hit.
    chosen = next((p for p in products if p["id"] == reply.product_id), None)
    log.info(
        "rag: query=%r matched=%d top_sim=%.3f chosen=%s",
        text, len(products), top_sim, reply.product_id,
    )
    await update.message.reply_text(
        reply.text, reply_markup=reply_cta_markup(lang, chosen)
    )
