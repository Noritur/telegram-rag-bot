import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID") or "0")

OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_LLM_MODEL = "gpt-4o-mini"
RELEVANCE_THRESHOLD = 0.4
TOP_K = 3
