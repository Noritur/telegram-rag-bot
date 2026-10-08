"""Reseed murmure.products from bot/data/catalog.json, end to end.

The murmure schema is closed to the anon key (it is public), so writing the
catalog needs the service_role key - the same one the bot runs on in Vercel.
It is asked for with getpass and lives only in this process: nothing is
written to .env.

  1. checks the key is service_role for this project (JWT claims, no network),
  2. runs seed_supabase.main(): one batch embedding call, upsert per product,
  3. counts the products now in the table.
Prints statuses only, never the key.

Usage: .venv/bin/python bot/scripts/reseed_catalog.py
"""

import getpass
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from bot.scripts.set_supabase_service_key import jwt_claims, read_env_value  # noqa: E402


def main() -> None:
    url = read_env_value("SUPABASE_URL")
    m = re.match(r"^https://([a-z0-9]+)\.supabase\.co/?$", url)
    if not m:
        sys.exit("SUPABASE_URL у .env не схожий на https://<ref>.supabase.co")

    key = getpass.getpass(
        "Supabase service_role key (Settings -> API Keys -> service_role, ввід прихований): "
    ).strip()
    try:
        claims = jwt_claims(key)
    except Exception:
        sys.exit("Це не схоже на JWT-ключ (має починатися з eyJ...).")
    if claims.get("role") != "service_role" or claims.get("ref") != m.group(1):
        sys.exit("Потрібен service_role ключ саме цього проєкту.")
    print("1/3 ключ: service_role цього проєкту")

    # bot.config reads the environment at import time: set the key first.
    os.environ["SUPABASE_SERVICE_KEY"] = key
    from bot.rag.store import murmure
    from bot.scripts import seed_supabase

    seed_supabase.main()
    print("2/3 каталог залито (ембединги + upsert)")

    res = murmure().table("products").select("id", count="exact").limit(1).execute()
    print(f"3/3 у murmure.products зараз {res.count} товарів")


if __name__ == "__main__":
    main()
