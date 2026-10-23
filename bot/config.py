import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID") or "0")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

# One codebase, several shops: each deployment names its brand and its own
# Postgres schema (same tables) through env. Both are required, so a
# deployment can never fall back to another shop's name or data.
SHOP_NAME = os.environ.get("SHOP_NAME", "").strip()
DB_SCHEMA = os.environ.get("DB_SCHEMA", "").strip()
_missing = [name for name, value in (("SHOP_NAME", SHOP_NAME), ("DB_SCHEMA", DB_SCHEMA)) if not value]
if _missing:
    raise RuntimeError(f"Set {', '.join(_missing)} in the environment (see .env.example).")
if not re.fullmatch(r"[a-z_][a-z0-9_]*", DB_SCHEMA):
    raise RuntimeError("DB_SCHEMA must be a plain Postgres schema name: lowercase letters, digits, _.")

GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"
GEMINI_EMBEDDING_DIM = 1536
GEMINI_LLM_MODEL = "gemini-2.5-flash"
RELEVANCE_THRESHOLD = 0.4
TOP_K = 3
