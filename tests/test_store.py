"""Key choice for Supabase: bot/rag/store.py.

The bot must run on the service_role key in production: the anon key is
public (a browser app shares the project), so anon policies cannot guard the
murmure log tables. Logging silently failed from May to October 2026 while
the service key was missing.
"""

import pytest

import bot.rag.store as store


def test_service_key_wins_when_set(monkeypatch):
    monkeypatch.setattr(store, "SUPABASE_SERVICE_KEY", "service")
    monkeypatch.setattr(store, "SUPABASE_KEY", "anon")
    assert store._resolve_key() == "service"


def test_anon_key_is_only_a_fallback(monkeypatch):
    monkeypatch.setattr(store, "SUPABASE_SERVICE_KEY", "")
    monkeypatch.setattr(store, "SUPABASE_KEY", "anon")
    assert store._resolve_key() == "anon"


def test_no_key_at_all_fails_loudly(monkeypatch):
    monkeypatch.setattr(store, "SUPABASE_SERVICE_KEY", "")
    monkeypatch.setattr(store, "SUPABASE_KEY", "")
    with pytest.raises(RuntimeError):
        store._resolve_key()
