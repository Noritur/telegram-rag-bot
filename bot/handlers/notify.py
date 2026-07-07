"""Owner notifications — direct awaits, not fire-and-forget.

In the webhook execution model pending tasks can be dropped when the event
loop closes, so anything that must reach the owner is awaited inline.
"""

import logging

from telegram import Bot, User

from bot.config import ADMIN_USER_ID

log = logging.getLogger(__name__)


def format_client(user: User | None) -> str:
    if user is None:
        return "(невідомий клієнт)"
    name = user.first_name or ""
    handle = f"@{user.username}" if user.username else f"(без ніка, id {user.id})"
    return f"{name} {handle}".strip()


async def notify_owner(bot: Bot, text: str) -> None:
    """Never raises — a failed owner ping must not break the client flow."""
    if not ADMIN_USER_ID:
        return
    try:
        await bot.send_message(ADMIN_USER_ID, text)
    except Exception:
        log.exception("owner notification failed")
