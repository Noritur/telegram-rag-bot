import logging
from datetime import datetime, timedelta, timezone

from bot.rag.store import murmure

log = logging.getLogger(__name__)


def log_message(user_id: int, text: str, matched: bool, top_score: float | None) -> None:
    murmure().table("messages").insert(
        {
            "user_id": user_id,
            "text": text,
            "matched": matched,
            "top_score": top_score,
        }
    ).execute()


def log_missed(user_id: int, text: str) -> None:
    murmure().table("missed").insert(
        {
            "user_id": user_id,
            "text": text,
        }
    ).execute()


def safe_log_message(user_id: int, text: str, matched: bool, top_score: float | None) -> None:
    try:
        log_message(user_id, text, matched, top_score)
    except Exception:
        log.exception("log_message failed")


def safe_log_missed(user_id: int, text: str) -> None:
    try:
        log_missed(user_id, text)
    except Exception:
        log.exception("log_missed failed")


def get_stats(days: int = 7) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    msgs = (
        murmure()
        .table("messages")
        .select("matched")
        .gte("ts", since)
        .execute()
        .data
        or []
    )
    missed = (
        murmure()
        .table("missed")
        .select("id", count="exact")
        .gte("ts", since)
        .execute()
    )
    total = len(msgs)
    matched = sum(1 for m in msgs if m.get("matched"))
    return {
        "days": days,
        "total_messages": total,
        "matched": matched,
        "handoff": total - matched,
        "missed_logged": missed.count if missed.count is not None else len(missed.data or []),
    }


def get_recent_missed(limit: int = 20) -> list[dict]:
    res = (
        murmure()
        .table("missed")
        .select("ts, user_id, text")
        .order("ts", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []
