"""HTTP layer of the Vercel function: api/index.py `handler`.

Runs the real handler class on a localhost HTTPServer, so the secret check,
status codes and the asyncio.run() hand-off are exercised exactly as in prod.
"""

import http.client
import json
import threading
from http.server import HTTPServer

import pytest

import api.index as api_index
from tests.conftest import CLIENT_ID, PRODUCT

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


@pytest.fixture
def serve():
    servers = []

    def start() -> int:
        srv = HTTPServer(("127.0.0.1", 0), api_index.handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return srv.server_address[1]

    yield start
    for srv in servers:
        srv.shutdown()
        srv.server_close()


@pytest.fixture
def processed(monkeypatch):
    """Replaces _process with a recorder: these tests are about the HTTP gate."""
    bodies = []

    async def record(body):
        bodies.append(body)

    monkeypatch.setattr(api_index, "_process", record)
    return bodies


def request(port, method="POST", body=None, headers=None):
    # Rejected requests are answered without reading the body (by design), and
    # closing a socket with unread bytes can reset the connection - so gate
    # tests send no body; the decision is header-only anyway.
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    payload = json.dumps(body).encode() if body is not None else None
    conn.request(method, "/api/index", body=payload, headers=headers or {})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, json.loads(data)


def test_post_without_secret_is_rejected_before_any_work(serve, processed):
    status, body = request(serve())
    assert status == 403
    assert body == {"error": "forbidden"}
    assert processed == []


def test_post_with_wrong_secret_is_rejected(serve, processed):
    status, _ = request(serve(), headers={SECRET_HEADER: "guess"})
    assert status == 403
    assert processed == []


def test_unset_secret_fails_closed(serve, processed, monkeypatch):
    # A missing WEBHOOK_SECRET must not turn into "empty header is fine".
    monkeypatch.setattr(api_index, "WEBHOOK_SECRET", "")
    status, _ = request(serve(), headers={SECRET_HEADER: ""})
    assert status == 403
    assert processed == []


def test_post_with_secret_is_processed(serve, processed):
    update = {"update_id": 42, "message": {"text": "hi"}}
    status, body = request(serve(), body=update, headers={SECRET_HEADER: "test-secret"})
    assert status == 200
    assert body == {"ok": True}
    assert processed == [update]


def test_handler_crash_still_answers_200(serve, monkeypatch):
    # Telegram would retry a 5xx forever; app-side bugs are logged instead.
    async def boom(body):
        raise RuntimeError("handler bug")

    monkeypatch.setattr(api_index, "_process", boom)
    status, _ = request(serve(), body={"update_id": 1}, headers={SECRET_HEADER: "test-secret"})
    assert status == 200


def test_get_reveals_nothing(serve, processed):
    status, body = request(serve(), method="GET")
    assert status == 404
    assert body == {"error": "not_found"}


def test_full_path_from_http_to_reply(serve, bot, db):
    """POST -> secret check -> asyncio.run(_process) -> handler -> reply + log."""
    db.rpc_results["match_products"] = [{**PRODUCT, "similarity": 0.8}]
    status, _ = request(
        serve(), body=bot.text("браслет з аметисту"), headers={SECRET_HEADER: "test-secret"}
    )
    assert status == 200
    assert len(bot.texts_to(CLIENT_ID)) == 1
    assert bot.buttons_to(CLIENT_ID) == ["order:amethyst-bracelet", "nav:catalog"]
    # Logging is fire-and-forget inside the handler; it must still land before
    # the function returns, or /stats silently undercounts.
    [logged] = db.inserted("messages")
    assert logged.row["matched"] is True
