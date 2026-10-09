"""bot/scripts/set_commands.py: the command menu a webhook-only bot never got."""

import logging
import os
import subprocess
import sys
from pathlib import Path

from telegram import Bot

from bot.scripts import set_commands
from tests.conftest import ADMIN_ID, FakeTelegramRequest

ROOT = Path(__file__).resolve().parent.parent


async def test_menu_is_registered_per_language_and_for_the_owner():
    request = FakeTelegramRequest()
    async with Bot("123456:TEST-TOKEN", request=request) as bot:
        username, public, owner = await set_commands.register_menu(bot)

    assert username == "murmure_test_bot"
    assert public == ["start", "catalog", "help"]
    assert owner == ["start", "catalog", "help", "stats", "missed"]
    sets = [p for e, p in request.calls if e == "setMyCommands"]
    assert sorted(str(p.get("language_code")) for p in sets) == ["None", "None", "en", "ru", "uk"]
    owner_scope = [p for p in sets if "chat_id" in str(p.get("scope"))]
    assert len(owner_scope) == 1 and str(ADMIN_ID) in str(owner_scope[0]["scope"])


def test_importing_the_script_keeps_the_token_out_of_logs():
    # bot.main turns on INFO; httpx at INFO prints request URLs with the token.
    # A fresh interpreter: in this test session api/index.py has muted httpx already.
    probe = (
        "import logging, bot.scripts.set_commands;"
        "print(logging.getLogger('httpx').getEffectiveLevel())"
    )
    env = {**os.environ, "TELEGRAM_BOT_TOKEN": "123456:TEST-TOKEN", "ADMIN_USER_ID": "999"}
    out = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT, env=env, capture_output=True, text=True, check=True
    )
    assert int(out.stdout.strip().splitlines()[-1]) >= logging.WARNING
