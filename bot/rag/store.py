from supabase import Client, create_client

from bot.config import SUPABASE_KEY, SUPABASE_SERVICE_KEY, SUPABASE_URL

_client: Client | None = None


def _resolve_key() -> str:
    """Prefer service_role for server-side bot work (bypasses RLS).
    Fallback to anon key only if service key missing — useful for local dev
    that hasn't set up service key yet.
    """
    key = SUPABASE_SERVICE_KEY or SUPABASE_KEY
    if not key:
        raise RuntimeError(
            "Neither SUPABASE_SERVICE_KEY nor SUPABASE_KEY set in .env"
        )
    return key


def get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL:
            raise RuntimeError("SUPABASE_URL missing in .env")
        _client = create_client(SUPABASE_URL, _resolve_key())
    return _client


def murmure():
    return get_client().schema("murmure")
