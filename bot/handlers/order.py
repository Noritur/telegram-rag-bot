"""Order capture — the button under every product answer.

Click -> order row in murmure.orders + instant owner ping + confirmation to
the client. The reply keyboard is cleared after a click to prevent duplicate
orders from the same message.
"""

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.handlers.commands import catalog_text, resolve_lang
from bot.handlers.notify import format_client, notify_owner
from bot.rag.store import murmure

log = logging.getLogger(__name__)

ORDER_BTN = {
    "uk": "Хочу замовити",
    "ru": "Хочу заказать",
    "en": "I want to order",
}

CATALOG_BTN = {
    "uk": "Каталог",
    "ru": "Каталог",
    "en": "Catalog",
}

ORDER_CONFIRM = {
    "uk": "Передаю власниці — вона звʼяжеться з вами найближчим часом, щоб узгодити оплату і доставку.",
    "ru": "Передаю владелице — она свяжется с вами в ближайшее время, чтобы согласовать оплату и доставку.",
    "en": "Passing this to the owner — she'll contact you shortly to arrange payment and delivery.",
}

ORDER_ERROR = {
    "uk": "Не вдалося оформити — напишіть, будь ласка, ще раз за хвилину.",
    "ru": "Не получилось оформить — напишите, пожалуйста, ещё раз через минуту.",
    "en": "Couldn't place the order — please try again in a minute.",
}

CATALOG_EMPTY_NAV = {
    "uk": "Каталог тимчасово порожній.",
    "ru": "Каталог временно пуст.",
    "en": "The catalog is temporarily empty.",
}


def reply_cta_markup(lang: str, product_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(ORDER_BTN[lang], callback_data=f"order:{product_id}")],
            [InlineKeyboardButton(CATALOG_BTN[lang], callback_data="nav:catalog")],
        ]
    )


def _fetch_product_name(product_id: str) -> str | None:
    rows = (
        murmure()
        .table("products")
        .select("name")
        .eq("id", product_id)
        .limit(1)
        .execute()
        .data
    )
    return rows[0]["name"] if rows else None


def _insert_order(user_id: int, username: str | None, product_id: str, product_name: str) -> None:
    # returning="minimal": orders are write-only for the bot role — RLS has an
    # INSERT policy but deliberately no SELECT, so return=representation would
    # reject the whole insert.
    murmure().table("orders").insert(
        {
            "user_id": user_id,
            "username": username,
            "product_id": product_id,
            "product_name": product_name,
        },
        returning="minimal",
    ).execute()


async def order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    user = query.from_user
    lang = resolve_lang(context, user.language_code if user else None)
    product_id = query.data.split(":", 1)[1]

    try:
        product_name = await asyncio.to_thread(_fetch_product_name, product_id)
    except Exception:
        log.exception("product lookup failed: %s", product_id)
        product_name = None

    if not product_name:
        await query.message.reply_text(ORDER_ERROR[lang])
        return

    order_saved = True
    try:
        await asyncio.to_thread(
            _insert_order, user.id, user.username, product_id, product_name
        )
    except Exception:
        order_saved = False
        log.exception("order insert failed: %s", product_id)

    # Owner ping goes out even if the DB write failed — a lead is a lead.
    await notify_owner(
        context.bot,
        "Замовлення з бота:\n"
        f"{product_name}\n"
        f"Клієнт: {format_client(user)}"
        + ("" if order_saved else "\n(увага: запис у базу не пройшов, лід тільки тут)"),
    )

    # Clear buttons on the answered message to prevent duplicate clicks.
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        log.debug("could not clear reply markup", exc_info=True)

    await query.message.reply_text(ORDER_CONFIRM[lang])
    log.info("order: user_id=%s product=%s saved=%s", user.id, product_id, order_saved)


async def nav_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    lang = resolve_lang(context, user.language_code if user else None)
    try:
        text = await asyncio.to_thread(catalog_text, lang)
    except Exception:
        log.exception("catalog fetch failed")
        text = None
    await query.message.reply_text(text or CATALOG_EMPTY_NAV[lang])
