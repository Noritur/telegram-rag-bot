"""Data integrity of bot/data/catalog.json - the content the bot answers from.

A broken entry fails silently in production: a duplicate id overwrites another
product on reseed, a name without a quoted title gives a clumsy order button,
a product missing the gift tag never surfaces for the most common question.
"""

import json
import re
from pathlib import Path

import pytest

CATALOG = json.loads((Path(__file__).parent.parent / "bot" / "data" / "catalog.json").read_text())
REQUIRED = {"id", "name", "category", "stone", "price_uah", "color", "description", "tags", "vibes", "in_stock"}
ID_PREFIX = {"кольє": "neck-", "браслети": "brace-", "сережки": "earr-", "перстні": "ring-", "кулони": "pend-"}


def test_ids_and_names_are_unique():
    ids = [p["id"] for p in CATALOG]
    names = [p["name"] for p in CATALOG]
    assert len(ids) == len(set(ids))
    assert len(names) == len(set(names))


@pytest.mark.parametrize("product", CATALOG, ids=lambda p: p["id"])
def test_product_is_complete_and_consistent(product):
    assert REQUIRED <= set(product)
    assert product["id"].startswith(ID_PREFIX[product["category"]])
    assert re.search(r"'[^']+'", product["name"]), "name needs a quoted title for the order button"
    assert 100 <= product["price_uah"] <= 10_000
    assert len(product["description"]) >= 80, "too thin to answer questions from"
    assert {"подарунок", "gift"} <= set(product["tags"])


def test_catalog_covers_budget_premium_and_men():
    prices = [p["price_uah"] for p in CATALOG]
    assert sum(price <= 1000 for price in prices) >= 8
    assert sum(price >= 3000 for price in prices) >= 3
    assert sum("для чоловіка" in p["tags"] for p in CATALOG) >= 4
