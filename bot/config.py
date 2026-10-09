import os
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
# Postgres schema (same tables) through env. Defaults keep the original bot.
SHOP_NAME = os.environ.get("SHOP_NAME") or "Murmure"
DB_SCHEMA = os.environ.get("DB_SCHEMA") or "murmure"

GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"
GEMINI_EMBEDDING_DIM = 1536
GEMINI_LLM_MODEL = "gemini-2.5-flash"
RELEVANCE_THRESHOLD = 0.4
TOP_K = 3
