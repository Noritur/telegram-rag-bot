"""Shared fakes for the test suite.

Nothing here talks to the network: Supabase, Gemini and the Telegram Bot API are
replaced at their boundaries, and a guard fails any test that tries to open a
connection anywhere but localhost. Updates still travel the real path:
api/index.py _process -> _build_app() -> handler registration -> handler code.

Live checks against real services are opt-in: RUN_LIVE=1 pytest -m live
"""

import asyncio
import json
import os
import socket
import time
from types import SimpleNamespace

LIVE = os.environ.get("RUN_LIVE") == "1"

# Must happen before anything imports bot.config: load_dotenv() never overrides
# variables that are already set, so the real .env cannot leak into the tests.
_FAKE_ENV = {
    "TELEGRAM_BOT_TOKEN": "123456:TEST-TOKEN",
    "WEBHOOK_SECRET": "test-secret",
    "ADMIN_USER_ID": "999",
}
if not LIVE:
    _FAKE_ENV.update(
        {
            "GEMINI_API_KEY": "test-gemini-key",
            "SUPABASE_URL": "http://supabase.invalid",
            "SUPABASE_KEY": "test-anon-key",
            "SUPABASE_SERVICE_KEY": "",
        }
    )
os.environ.update(_FAKE_ENV)

import pytest  # noqa: E402
from telegram.ext import ApplicationBuilder  # noqa: E402
from telegram.request import BaseRequest  # noqa: E402

import api.index as api_index  # noqa: E402
import bot.rag.embeddings as embeddings  # noqa: E402
import bot.rag.store as store  # noqa: E402

ADMIN_ID = 999
CLIENT_ID = 111
BOT_USER = {
    "id": 1,
    "is_bot": True,
    "first_name": "Murmure",
    "username": "murmure_test_bot",
    "can_join_groups": False,
    "can_read_all_group_messages": False,
    "supports_inline_queries": False,
}
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", None}


# --- network guard -----------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_network(request, monkeypatch):
    if request.node.get_closest_marker("live"):
        return
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def guarded_connect(sock, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in _LOCAL_HOSTS:
            raise RuntimeError(f"network access blocked in tests: {address!r}")
        return real_connect(sock, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host not in _LOCAL_HOSTS:
            raise RuntimeError(f"DNS lookup blocked in tests: {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)


def pytest_collection_modifyitems(config, items):
    if LIVE:
        return
    skip_live = pytest.mark.skip(reason="live check: run with RUN_LIVE=1 pytest -m live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


# --- Supabase ----------------------------------------------------------------


class FakeQuery:
    """Chainable stand-in for a PostgREST query builder."""

    def __init__(self, db: "FakeDB", table: str):
        self.db = db
        self.table = table
        self.filters: list[tuple[str, str, object]] = []
        self.row: dict | None = None
        self.returning: str | None = None
        self.count: str | None = None

    def select(self, *columns, count=None):
        self.count = count
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def gte(self, column, value):
        self.filters.append(("gte", column, value))
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    def insert(self, row, returning=None):
        self.row = row
        self.returning = returning
        return self

    def execute(self):
        if self.table in self.db.fail:
            raise self.db.fail[self.table]
        if self.row is not None:
            self.db.inserts.append(
                SimpleNamespace(table=self.table, row=self.row, returning=self.returning)
            )
            return SimpleNamespace(data=[], count=None)
        rows = list(self.db.tables.get(self.table, []))
        for op, column, value in self.filters:
            if op == "eq":
                rows = [r for r in rows if r.get(column) == value]
        return SimpleNamespace(data=rows, count=len(rows) if self.count else None)


class FakeRPC:
    def __init__(self, db: "FakeDB", name: str, params: dict):
        self.db, self.name, self.params = db, name, params

    def execute(self):
        self.db.rpc_calls.append((self.name, self.params))
        if self.name in self.db.fail:
            raise self.db.fail[self.name]
        return SimpleNamespace(data=list(self.db.rpc_results.get(self.name, [])))


class FakeDB:
    """What murmure() returns: .table() and .rpc(), with every write recorded."""

    def __init__(self):
        self.tables: dict[str, list[dict]] = {}
        self.rpc_results: dict[str, list[dict]] = {}
        self.fail: dict[str, Exception] = {}
        self.inserts: list[SimpleNamespace] = []
        self.rpc_calls: list[tuple[str, dict]] = []
        self.schemas: list[str] = []

    def table(self, name):
        return FakeQuery(self, name)

    def rpc(self, name, params):
        return FakeRPC(self, name, params)

    def inserted(self, table: str) -> list[SimpleNamespace]:
        return [i for i in self.inserts if i.table == table]


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()

    class _Client:
        def schema(self, name):
            fake.schemas.append(name)
            return fake

    monkeypatch.setattr(store, "get_client", lambda: _Client())
    return fake


# --- Gemini ------------------------------------------------------------------


class FakeGenai:
    """Stands in for google.genai.Client: .models.embed_content / generate_content.

    `reply` decides what generate_content does: a string is returned as the
    model text, an exception is raised, a callable gets (model, query) and may
    do either.
    """

    def __init__(self):
        self.reply = "Аметистовий браслет — спокій і ясність, 1200 грн."
        self.generate_calls: list[dict] = []
        self.embed_calls: list[object] = []
        self.models = self

    def embed_content(self, model, contents, config=None):
        self.embed_calls.append(contents)
        n = len(contents) if isinstance(contents, list) else 1
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2, 0.3])] * n)

    def generate_content(self, model, contents, config=None):
        system = getattr(config, "system_instruction", None)
        self.generate_calls.append({"model": model, "query": contents, "system": system})
        outcome = self.reply(model, contents) if callable(self.reply) else self.reply
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(text=outcome)


@pytest.fixture
def genai(monkeypatch):
    fake = FakeGenai()
    monkeypatch.setattr(embeddings, "_get_client", lambda: fake)
    return fake


# --- Telegram Bot API --------------------------------------------------------


class FakeTelegramRequest(BaseRequest):
    """Answers Bot API calls locally and records what the bot sent."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self._next_id = 1000

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    @property
    def read_timeout(self) -> float:
        return 5.0

    async def do_request(self, url, method, request_data=None, **_timeouts):
        # Real I/O yields to the event loop; without this, fire-and-forget tasks
        # created by handlers would behave differently than in production.
        await asyncio.sleep(0)
        endpoint = url.rsplit("/", 1)[-1]
        params = dict(request_data.parameters) if request_data else {}
        self.calls.append((endpoint, params))
        return 200, json.dumps({"ok": True, "result": self._result(endpoint, params)}).encode()

    def _result(self, endpoint: str, params: dict):
        if endpoint == "getMe":
            return BOT_USER
        if endpoint in ("sendMessage", "editMessageText", "editMessageReplyMarkup"):
            self._next_id += 1
            return {
                "message_id": params.get("message_id", self._next_id),
                "date": int(time.time()),
                "chat": {"id": params.get("chat_id", 0), "type": "private"},
                "from": BOT_USER,
                "text": params.get("text", "…"),
            }
        return True


class BotHarness:
    """Feeds update dicts through the production entry point and reads results."""

    def __init__(self, request: FakeTelegramRequest):
        self.request = request
        self._update_id = 0

    async def send(self, update: dict) -> None:
        await api_index._process(update)
        # Handlers log via fire-and-forget tasks; let them finish so the test
        # can assert on what they wrote.
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def calls(self, endpoint: str) -> list[dict]:
        return [p for e, p in self.request.calls if e == endpoint]

    def texts_to(self, chat_id: int) -> list[str]:
        return [p["text"] for p in self.calls("sendMessage") if p.get("chat_id") == chat_id]

    def buttons_to(self, chat_id: int) -> list[str]:
        """callback_data of every inline button sent to chat_id, in order."""
        out = []
        for p in self.calls("sendMessage"):
            if p.get("chat_id") != chat_id or "reply_markup" not in p:
                continue
            markup = p["reply_markup"]
            markup = json.loads(markup) if isinstance(markup, str) else markup
            for row in markup.get("inline_keyboard", []):
                out.extend(b.get("callback_data") for b in row)
        return out

    # update builders

    def _uid(self) -> int:
        self._update_id += 1
        return self._update_id

    def text(self, text: str, user_id: int = CLIENT_ID, lang: str = "uk") -> dict:
        return {
            "update_id": self._uid(),
            "message": {
                "message_id": self._update_id,
                "date": int(time.time()),
                "chat": {"id": user_id, "type": "private"},
                "from": _user(user_id, lang),
                "text": text,
                **(
                    {"entities": [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]}
                    if text.startswith("/")
                    else {}
                ),
            },
        }

    def click(self, data: str, user_id: int = CLIENT_ID, lang: str = "uk") -> dict:
        return {
            "update_id": self._uid(),
            "callback_query": {
                "id": f"cb{self._update_id}",
                "chat_instance": "ci",
                "from": _user(user_id, lang),
                "data": data,
                "message": {
                    "message_id": 50,
                    "date": int(time.time()),
                    "chat": {"id": user_id, "type": "private"},
                    "from": BOT_USER,
                    "text": "previous bot answer",
                },
            },
        }


def _user(user_id: int, lang: str) -> dict:
    return {
        "id": user_id,
        "is_bot": False,
        "first_name": "Olena",
        "username": "olena_buyer",
        "language_code": lang,
    }


@pytest.fixture
def bot(monkeypatch, db, genai):
    """The real _build_app(), wired to the fake Bot API instead of Telegram."""
    request = FakeTelegramRequest()

    def builder():
        return (
            ApplicationBuilder()
            .request(request)
            .get_updates_request(FakeTelegramRequest())
        )

    monkeypatch.setattr(api_index, "Application", SimpleNamespace(builder=builder))
    return BotHarness(request)


PRODUCT = {
    "id": "amethyst-bracelet",
    "name": "Браслет з аметисту",
    "category": "браслети",
    "stone": "аметист",
    "color": "фіолетовий",
    "price_uah": 1200,
    "description": "Спокій і ясність думок.",
    "in_stock": True,
}
