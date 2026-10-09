"""Connect a new Telegram bot to its own Vercel project and shop schema, end to end.

One codebase serves several shops (bot.config: SHOP_NAME, DB_SCHEMA). For a new
shop the Vercel project, the schema and the catalog already exist; this script
does the part that needs secrets. Prompts for two values (hidden input):

  1. the bot token from @BotFather -> getMe proves it,
  2. the Supabase service_role key -> JWT claims say it is for this project, and a
     counted read of <schema>.products proves the schema is exposed to the API
     and RLS is bypassed,
then:
  3. writes the env of the target Vercel project: TELEGRAM_BOT_TOKEN,
     SUPABASE_SERVICE_KEY, GEMINI_API_KEY (copied from the local .env) and a
     freshly generated WEBHOOK_SECRET as sensitive values via stdin (never argv,
     so nothing shows up in `ps`); SHOP_NAME, DB_SCHEMA, SUPABASE_URL and
     ADMIN_USER_ID as plain ones,
  4. redeploys production so the function sees the new env,
  5. registers the webhook with the secret and reads getWebhookInfo back,
  6. registers the command menu (bot.main sets it only in polling mode).
Prints statuses only, never a value.

Usage:
  .venv/bin/python bot/scripts/connect_bot.py --project-id prj_... \\
      --url https://<project>.vercel.app --shop "Lumina Stones" --schema lumina
"""

import argparse
import asyncio
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from bot.scripts.set_supabase_service_key import jwt_claims, read_env_value  # noqa: E402


def tg_api(token: str, method: str, params: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(params or {}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def vercel(args: list[str], env: dict, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["vercel", *args], cwd=ROOT, env=env, input=input_text, capture_output=True, text=True
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True, help="prj_... of the new Vercel project")
    ap.add_argument("--url", required=True, help="production url, e.g. https://x.vercel.app")
    ap.add_argument("--shop", required=True, help="shop name the bot introduces itself with")
    ap.add_argument("--schema", required=True, help="Postgres schema with this shop's tables")
    args = ap.parse_args()
    base_url = args.url.rstrip("/")

    # The target project, not the one this checkout is linked to.
    org_id = json.loads((ROOT / ".vercel" / "project.json").read_text())["orgId"]
    env = {**os.environ, "VERCEL_ORG_ID": org_id, "VERCEL_PROJECT_ID": args.project_id}

    token = input_secret("Токен нового бота від @BotFather")
    try:
        me = tg_api(token, "getMe")["result"]
    except Exception:
        sys.exit("getMe не пройшов: токен невірний або telegram недоступний. Нічого не записано.")
    print(f"1/6 токен живий: @{me['username']}")

    url = read_env_value("SUPABASE_URL")
    m = re.match(r"^https://([a-z0-9]+)\.supabase\.co/?$", url)
    if not m:
        sys.exit("SUPABASE_URL у .env не схожий на https://<ref>.supabase.co")
    key = input_secret("Supabase service_role key (Settings -> API Keys -> service_role)")
    try:
        claims = jwt_claims(key)
    except Exception:
        sys.exit("Це не схоже на JWT-ключ (має починатися з eyJ...). Нічого не записано.")
    if claims.get("role") != "service_role" or claims.get("ref") != m.group(1):
        sys.exit("Це не service_role ключ цього проєкту supabase. Нічого не записано.")
    count = count_products(url, key, args.schema)
    print(f"2/6 ключ бачить {args.schema}.products: {count} товарів")

    gemini = read_env_value("GEMINI_API_KEY")
    admin = read_env_value("ADMIN_USER_ID")
    if not gemini or not admin:
        sys.exit("У локальному .env нема GEMINI_API_KEY або ADMIN_USER_ID. Нічого не записано.")
    values = {
        "TELEGRAM_BOT_TOKEN": (token, True),
        "SUPABASE_SERVICE_KEY": (key, True),
        "GEMINI_API_KEY": (gemini, True),
        "WEBHOOK_SECRET": (secrets.token_urlsafe(32), True),
        "SUPABASE_URL": (url, False),
        "ADMIN_USER_ID": (admin, False),
        "SHOP_NAME": (args.shop, False),
        "DB_SCHEMA": (args.schema, False),
    }
    for name, (value, sensitive) in values.items():
        flags = ["--sensitive"] if sensitive else []
        r = vercel(["env", "add", name, "production", *flags, "--force", "--yes"], env, value)
        if r.returncode != 0:
            sys.exit(f"vercel env add {name} упав (код {r.returncode}). Запусти скрипт ще раз.")
    names = vercel(["env", "ls", "production"], env).stdout
    missing = [n for n in values if not re.search(rf"^\s*{n}\s", names, re.M)]
    if missing:
        sys.exit(f"У vercel env не з'явились: {', '.join(missing)}")
    print(f"3/6 env записано у проєкт ({len(values)} змінних, секрети як sensitive)")

    r = vercel(["redeploy", base_url, "--target", "production"], env)
    if r.returncode != 0:
        sys.exit(f"redeploy упав (код {r.returncode}). env уже записано: передеплой вручну і запусти ще раз.")
    print("4/6 прод передеплоєно з новим env")

    hook = f"{base_url}/api/index"
    res = tg_api(token, "setWebhook", {
        "url": hook,
        "secret_token": values["WEBHOOK_SECRET"][0],
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": True,
    })
    if not res.get("ok"):
        sys.exit(f"setWebhook відмовив: {res.get('description')}")
    info = tg_api(token, "getWebhookInfo")["result"]
    print(f"5/6 вебхук: {info.get('url')} · pending {info.get('pending_update_count')} · "
          f"помилка: {info.get('last_error_message') or 'нема'}")
    _, public, owner = asyncio.run(_register_menu(token))
    print(f"6/6 меню: {len(public)} команд для клієнтів, {len(owner)} для тебе")
    print(f"\nDONE: напиши боту @{me['username']} /start")


async def _register_menu(token: str) -> tuple[str, list[str], list[str]]:
    # The menu lives on Telegram's side and bot.main sets it only in polling mode.
    from telegram import Bot

    from bot.scripts.set_commands import register_menu

    async with Bot(token) as bot:
        return await register_menu(bot)


def input_secret(prompt: str) -> str:
    import getpass

    value = getpass.getpass(f"{prompt} (ввід прихований): ").strip()
    if not value:
        sys.exit("Порожній ввід. Нічого не записано.")
    return value


def count_products(url: str, key: str, schema: str) -> int:
    import httpx
    from postgrest.exceptions import APIError
    from supabase import create_client

    for attempt in range(1, 4):
        try:
            res = (
                create_client(url, key).schema(schema).table("products")
                .select("id", count="exact").limit(1).execute()
            )
            break
        except httpx.TransportError as e:
            print(f"   мережа: {type(e).__name__}, спроба {attempt}/3")
            time.sleep(3)
        except APIError as e:
            hint = (" Схема не відкрита для API: Supabase -> Settings -> Data API -> Exposed schemas."
                    if e.code == "PGRST106" else "")
            sys.exit(f"Supabase відмовив ({e.code}): {e.message}.{hint} Нічого не записано.")
    else:
        sys.exit("Supabase недоступний після 3 спроб. Нічого не записано — запусти ще раз.")
    if not res.count:
        sys.exit(f"Ключ не бачить жодного товару в {schema}.products. Нічого не записано.")
    return res.count


if __name__ == "__main__":
    main()
