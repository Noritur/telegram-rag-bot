"""Smoke test for retriever.

Run: python -m tests.test_retriever_smoke
Requires: live Gemini API key + Supabase + seeded murmure.products.
"""

from bot.rag.retriever import search


def assert_match(query: str, expected_id_substring: str) -> None:
    results = search(query)
    assert results, f"no results for {query!r}"
    ids = [r.get("id", "") for r in results]
    found = any(expected_id_substring in id_ for id_ in ids)
    assert found, (
        f"no {expected_id_substring!r} match for {query!r}: got {ids}"
    )
    print(f"OK  {query!r:45} → {ids[0]} (sim={results[0].get('similarity', 0):.3f})")


def main() -> None:
    cases = [
        ("аметист фіолетовий", "amethyst"),
        ("лабрадорит синьо-зелений", "labradorite"),
        ("blue agate bracelet", "agate"),
        ("браслет з тигрового ока", "tiger-eye"),
        ("opal ring rainbow", "opal"),
    ]
    for query, expected in cases:
        assert_match(query, expected)
    print(f"\nAll {len(cases)} retriever smoke tests passed.")


if __name__ == "__main__":
    main()
