import json
import logging
from pathlib import Path

from bot.rag.embeddings import embed_batch
from bot.rag.store import murmure

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).parent.parent / "data" / "catalog.json"


def build_embedding_text(item: dict) -> str:
    parts = [
        item.get("name", ""),
        item.get("category", ""),
        item.get("stone", ""),
        item.get("color", ""),
        item.get("description", ""),
        " ".join(item.get("tags", [])),
        " ".join(item.get("vibes", [])),
    ]
    return ". ".join(p for p in parts if p)


def main() -> None:
    items = json.loads(CATALOG_PATH.read_text())
    log.info("Loaded %d items from %s", len(items), CATALOG_PATH.name)

    texts = [build_embedding_text(item) for item in items]
    log.info("Embedding %d texts in one batch...", len(texts))
    embeddings = embed_batch(texts)

    client = murmure()
    for item, emb in zip(items, embeddings):
        record = {**item, "embedding": emb}
        client.table("products").upsert(record).execute()
        log.info("upsert: %s — %s", item["id"], item["name"])

    log.info("Seed complete (%d items)", len(items))


if __name__ == "__main__":
    main()
