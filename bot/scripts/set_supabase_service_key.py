"""Put the Supabase service_role key into Vercel production env, end to end.

The bot used to run on the anon key, which is public (the same Supabase
project serves a browser app). With RLS on murmure.messages / murmure.missed
and no anon policies, every log write failed with 42501 and /stats read
nothing. bot.rag.store already prefers SUPABASE_SERVICE_KEY; it was just
never set in Vercel.

Prompts for the key (hidden input), then:
  1. checks it is a service_role key for this project (JWT claims, no network),
  2. reads murmure.messages through supabase-py with it - a non-zero count
     proves RLS is bypassed, i.e. the key does what the bot needs,
  3. stores it in Vercel production as a sensitive variable, value via stdin
     (never in argv, so it does not show up in `ps`).
Prints statuses only. Env changes reach the bot with the next deployment.

Usage: .venv/bin/python bot/scripts/set_supabase_service_key.py
"""

import base64
import getpass
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = ROOT / ".env"
VAR = "SUPABASE_SERVICE_KEY"


def read_env_value(key: str) -> str:
    for line in ENV_PATH.read_text().splitlines():
        m = re.match(rf"^{key}=(.*)$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return ""


def jwt_claims(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def main() -> None:
    url = read_env_value("SUPABASE_URL")
    m = re.match(r"^https://([a-z0-9]+)\.supabase\.co/?$", url)
    if not m:
        sys.exit("SUPABASE_URL у .env не схожий на https://<ref>.supabase.co")
    ref = m.group(1)

    key = getpass.getpass(
        "Supabase service_role key (Settings -> API Keys -> service_role, ввід прихований): "
    ).strip()
    try:
        claims = jwt_claims(key)
    except Exception:
        sys.exit("Це не схоже на JWT-ключ (має починатися з eyJ...). Потрібен legacy service_role.")
    if claims.get("role") != "service_role":
        sys.exit(f"Це ключ ролі '{claims.get('role')}', а потрібен service_role.")
    if claims.get("ref") != ref:
        sys.exit("Ключ від іншого проєкту supabase, не від того, що в SUPABASE_URL.")
    print("1/3 ключ: service_role цього проєкту")

    import httpx
    from postgrest.exceptions import APIError
    from supabase import create_client

    res = None
    for attempt in range(1, 4):
        try:
            res = (
                create_client(url, key)
                .schema("murmure")
                .table("messages")
                .select("id", count="exact")
                .limit(1)
                .execute()
            )
            break
        except httpx.TransportError as e:
            # Flaky links reset TLS now and then; nothing has been written yet.
            print(f"   мережа: {type(e).__name__}, спроба {attempt}/3")
            time.sleep(3)
        except APIError as e:
            sys.exit(f"Supabase відмовив ({e.code}): {e.message}. У vercel нічого не записано.")
    if res is None:
        sys.exit("Supabase недоступний після 3 спроб. У vercel нічого не записано — запусти ще раз.")
    if not res.count:
        sys.exit("Ключ не бачить жодного рядка в murmure.messages — RLS він не обходить.")
    print(f"2/3 доступ перевірено: ключ бачить murmure.messages ({res.count} рядків)")

    r = subprocess.run(
        ["vercel", "env", "add", VAR, "production", "--sensitive", "--force", "--yes"],
        cwd=ROOT, input=key, capture_output=True, text=True,
    )
    if r.returncode != 0:
        sys.exit(f"vercel env add упав (код {r.returncode})")
    names = subprocess.run(
        ["vercel", "env", "ls", "production"], cwd=ROOT, capture_output=True, text=True
    ).stdout
    if not re.search(rf"^\s*{VAR}\s", names, re.M):
        sys.exit(f"{VAR} не з'явився у vercel env ls production")
    print(f"3/3 {VAR} записано у vercel production як sensitive")
    print("\nDONE: ключ у vercel. бот підхопить його з наступним деплоєм.")


if __name__ == "__main__":
    main()
