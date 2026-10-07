"""Live retrieval check against the real Gemini embeddings and seeded Supabase.

Skipped by default. Run: RUN_LIVE=1 .venv/bin/python -m pytest -m live
Requires real GEMINI_API_KEY / SUPABASE_URL / SUPABASE_KEY in .env and a seeded
murmure.products table.
"""

import pytest

from bot.rag.retriever import search

pytestmark = pytest.mark.live


@pytest.mark.parametrize(
    ("query", "expected_id_part"),
    [
        ("аметист фіолетовий", "amethyst"),
        ("лабрадорит синьо-зелений", "labradorite"),
        ("blue agate bracelet", "agate"),
        ("браслет з тигрового ока", "tiger-eye"),
        ("opal ring rainbow", "opal"),
    ],
)
def test_query_finds_the_right_stone(query, expected_id_part):
    results = search(query)
    ids = [r.get("id", "") for r in results]
    assert any(expected_id_part in id_ for id_ in ids), f"{query!r} -> {ids}"
