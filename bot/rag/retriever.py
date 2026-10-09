from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from bot.config import TOP_K
from bot.rag.embeddings import embed
from bot.rag.store import murmure

if TYPE_CHECKING:  # rag must not import handlers at runtime
    from bot.handlers.gift_intent import GiftQuery

# More than the whole catalog: rank every product, then filter in code.
GIFT_POOL = 100


def search(query: str, k: int = TOP_K) -> list[dict]:
    emb = embed(query)
    res = (
        murmure()
        .rpc("match_products", {"query_embedding": emb, "match_count": k})
        .execute()
    )
    rows = res.data or []
    return [r for r in rows if r.get("in_stock")]


class GiftResult(NamedTuple):
    products: list[dict]
    over_budget: bool  # nothing fits the budget: these are the cheapest instead


def search_gift(query: str, gift: GiftQuery, k: int = TOP_K) -> GiftResult:
    """Budget is a hard price filter; recipient and occasion tags only rank,
    because most items for women carry no "для неї" tag and a filter would
    drop them. Similarity breaks ties, and orders the pool when no tag matches."""
    db = murmure()
    rows = (
        db.rpc("match_products", {"query_embedding": embed(query), "match_count": GIFT_POOL})
        .execute()
        .data
        or []
    )
    # match_products returns no tags: fetch them in one query.
    tag_rows = db.table("products").select("id,tags").eq("in_stock", True).execute().data or []
    tags = {r["id"]: set(r.get("tags") or []) for r in tag_rows}

    pool = [r for r in rows if r.get("in_stock")]
    fits = [
        r for r in pool
        if gift.budget is None or (r.get("price_uah") is not None and r["price_uah"] <= gift.budget)
    ]
    if not fits:
        cheapest = sorted(
            (r for r in pool if r.get("price_uah") is not None), key=lambda r: r["price_uah"]
        )[:k]
        return GiftResult(cheapest, over_budget=bool(cheapest))

    def rank(r: dict) -> tuple:
        product_tags = tags.get(r["id"], set())
        return (
            bool(product_tags & gift.recipients),
            bool(product_tags & gift.occasions),
            r.get("similarity") or 0.0,
        )

    return GiftResult(sorted(fits, key=rank, reverse=True)[:k], over_budget=False)
