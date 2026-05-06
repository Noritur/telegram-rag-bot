from supabase import Client, create_client

from bot.config import SUPABASE_KEY, SUPABASE_URL

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL or SUPABASE_KEY missing in .env")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def murmure():
    return get_client().schema("murmure")
