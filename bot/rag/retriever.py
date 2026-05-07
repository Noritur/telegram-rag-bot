from bot.config import TOP_K
from bot.rag.embeddings import embed
from bot.rag.store import murmure


def search(query: str, k: int = TOP_K) -> list[dict]:
    emb = embed(query)
    res = (
        murmure()
        .rpc("match_products", {"query_embedding": emb, "match_count": k})
        .execute()
    )
    rows = res.data or []
    return [r for r in rows if r.get("in_stock")]
