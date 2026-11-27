"""GET /api/events/stream against a real server and the real trigger."""
import asyncio
import json
import os
import socket
import sys
import time
import uuid
from urllib.parse import urlsplit

import asyncpg
import httpx
import pytest

import src.api.routers.events as stream_module
from tests.conftest import INTERNAL_KEY, ROOT

INSERT = """insert into events (id, kind, source, payload)
            select gen_random_uuid(), $1, 'forge', jsonb_build_object('pad', repeat('x', $3))
            from generate_series(1, $2) g"""


async def listeners(db) -> int:
    return await db.fetchval("""
        select count(*) from pg_stat_activity
        where datname = current_database() and pid <> pg_backend_pid()
          and query ilike '%LISTEN%apex_events%'""")


async def wait_until(condition, timeout=10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = condition()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return True
        await asyncio.sleep(0.05)
    return False


async def no_listeners(db, timeout=10.0) -> bool:
    async def check():
        return await listeners(db) == 0
    return await wait_until(check, timeout)


class Stream:
    """Reads a stream in the background, recording events, comments and how it ended."""

    def __init__(self, base, headers):
        self.base, self.headers = base, headers

    async def __aenter__(self):
        self.events, self.comments, self.end, self.response = [], [], None, None
        self.client = httpx.AsyncClient(timeout=30)
        self.task = asyncio.create_task(self._read())
        assert await wait_until(lambda: self.comments or self.task.done())
        assert self.comments, f"stream did not start: {self.end}"
        return self

    async def _read(self):
        try:
            async with self.client.stream("GET", f"{self.base}/api/events/stream",
                                          headers=self.headers) as response:
                self.response = response
                async for line in response.aiter_lines():
                    if line.startswith(":"):
                        self.comments.append(line)
                    elif line.startswith("data:"):
                        self.events.append(json.loads(line[5:]))
            self.end = "clean"
        except httpx.HTTPError as e:
            self.end = type(e).__name__

    async def ended(self, timeout=15.0):
        await wait_until(self.task.done, timeout)
        return self.end

    async def received(self, kind, timeout=5.0) -> bool:
        return await wait_until(lambda: any(e["kind"] == kind for e in self.events), timeout)

    async def __aexit__(self, *exc):
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
        await self.client.aclose()


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Basics ────────────────────────────────────────────────────────

@pytest.mark.parametrize("how", ["bearer", "cookie", "bot"])
async def test_auth_and_headers(server, token, db, how):
    headers = {"bearer": {"Authorization": f"Bearer {token}"},
               "cookie": {"Cookie": f"apex_token={token}"},
               "bot": {"X-Bot-Auth": INTERNAL_KEY}}[how]
    async with Stream(server, headers) as stream:
        assert stream.response.status_code == 200
        assert stream.response.headers["content-type"].startswith("text/event-stream")
        assert stream.response.headers["cache-control"] == "no-cache, no-transform"
        assert stream.response.headers["x-accel-buffering"] == "no"
        assert await listeners(db) == 1
    assert await no_listeners(db)


async def test_needs_auth(server, db):
    async with httpx.AsyncClient() as client:
        assert (await client.get(f"{server}/api/events/stream")).status_code == 401
    assert await listeners(db) == 0


async def test_note_arrives_within_two_seconds(server, auth, project):
    async with Stream(server, auth) as stream, httpx.AsyncClient(headers=auth) as client:
        started = time.monotonic()
        res = await client.post(f"{server}/api/projects/{project['id']}/notes", json={"content": "n"})
        assert await stream.received("note.created", timeout=2)
        assert time.monotonic() - started < 2
        event = next(e for e in stream.events if e["kind"] == "note.created")
        listed = (await client.get(f"{server}/api/events?kind=note.created")).json()
    assert event["payload"]["note_id"] == res.json()["id"]
    assert [event] == listed


async def test_posted_and_directly_inserted_events_arrive(server, auth, db):
    async with Stream(server, auth) as stream, httpx.AsyncClient(headers=auth) as client:
        await client.post(f"{server}/api/events", json={
            "kind": "bot.test", "source": "bot", "payload": {"text": "é\nsecond line"}})
        await db.execute(INSERT, "sql.test", 1, 0)
        assert await stream.received("bot.test") and await stream.received("sql.test")
        assert stream.events[0]["payload"] == {"text": "é\nsecond line"}


def test_default_heartbeat_and_queue_size():
    assert (stream_module.HEARTBEAT_SECONDS, stream_module.QUEUE_MAXSIZE) == (15, 1000)


async def test_heartbeat(server, auth, monkeypatch):
    monkeypatch.setattr(stream_module, "HEARTBEAT_SECONDS", 0.1)
    async with Stream(server, auth) as stream:
        assert await wait_until(lambda: stream.comments.count(": heartbeat") >= 3, 3)


async def test_no_listener_left_after_many_connections(server, auth, db):
    async def open_and_close():
        async with Stream(server, auth):
            pass
    for _ in range(5):
        await open_and_close()
    await asyncio.gather(*(open_and_close() for _ in range(10)))
    assert await no_listeners(db)


async def test_database_unavailable_is_503(server, auth, monkeypatch):
    monkeypatch.setattr(stream_module, "LISTEN_DSN", "postgresql://x:x@127.0.0.1:1/unreachable_test")
    async with httpx.AsyncClient(headers=auth) as client:
        res = await client.get(f"{server}/api/events/stream")
    assert res.status_code == 503


async def test_lost_listener_connection_ends_stream(server, auth, db):
    async with Stream(server, auth) as stream:
        await db.execute("""select pg_terminate_backend(pid) from pg_stat_activity
                            where datname = current_database() and pid <> pg_backend_pid()
                              and query ilike '%LISTEN%apex_events%'""")
        assert await stream.ended(5) == "clean"


async def test_smoke_script(server, token, db):
    process = await asyncio.create_subprocess_exec(
        sys.executable, "scripts/test_event_stream.py", "--base-url", server, cwd=ROOT,
        env={**os.environ, "APEX_TOKEN": token},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await asyncio.wait_for(process.communicate(), 30)
    assert process.returncode == 0, (out + err).decode()
    assert b"PASS" in out
    assert await db.fetchval("select count(*) from projects where deleted_at is null") == 0


# ── Events that cannot be loaded ──────────────────────────────────

async def test_missing_events_are_skipped(server, auth, db):
    async with Stream(server, auth) as stream:
        async with db.transaction():  # notifies, but the row is gone by then
            await db.execute(INSERT, "gone", 1, 0)
            await db.execute("delete from events where kind = 'gone'")
        await db.execute("select pg_notify('apex_events', $1)", str(uuid.uuid4()))
        await db.execute(INSERT, "after", 1, 0)
        assert await stream.received("after")
        assert [e["kind"] for e in stream.events] == ["after"] and stream.end is None


async def test_load_error_ends_stream(server, auth, db, events_unavailable, caplog):
    async with Stream(server, auth) as stream:
        async with events_unavailable():
            await db.execute("select pg_notify('apex_events', $1)", str(uuid.uuid4()))
            assert await stream.ended(5) == "clean"
    assert "Ending event stream: could not load event" in caplog.text
    assert "UndefinedTableError" in caplog.text
    assert await no_listeners(db)


async def test_load_timeout_ends_stream(server, auth, db, monkeypatch, caplog):
    monkeypatch.setattr(stream_module, "DB_TIMEOUT_SECONDS", 0.5)
    other = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        async with Stream(server, auth) as stream:
            async with db.transaction():
                await db.execute("lock table events in access exclusive mode")
                await other.execute("select pg_notify('apex_events', $1)", str(uuid.uuid4()))
                assert await stream.ended(8) == "clean"
    finally:
        await other.close()
    assert "Ending event stream: could not load event" in caplog.text and "TimeoutError" in caplog.text
    assert await no_listeners(db)


async def test_repeated_load_timeouts_do_not_drain_the_pool(db, monkeypatch):
    from src.db.session import engine
    monkeypatch.setattr(stream_module, "DB_TIMEOUT_SECONDS", 0.2)
    for _ in range(35):  # more than pool_size + max_overflow
        async with db.transaction():
            await db.execute("lock table events in access exclusive mode")
            with pytest.raises(TimeoutError):
                await stream_module._load_event_json(str(uuid.uuid4()))
    monkeypatch.setattr(stream_module, "DB_TIMEOUT_SECONDS", 5)
    assert await stream_module._load_event_json(str(uuid.uuid4())) is None
    assert await wait_until(lambda: engine.pool.checkedout() == 0)


# ── Bounded queue ─────────────────────────────────────────────────

async def test_burst_within_the_limit_is_delivered(server, auth, db):
    async with Stream(server, auth) as stream:
        await db.execute(INSERT, "burst", 900, 0)
        assert await wait_until(lambda: len(stream.events) == 900, 60)
        assert stream.end is None


async def test_overflow_ends_stream(server, auth, db, caplog):
    async with Stream(server, auth) as stream:
        await db.execute(INSERT, "burst", 3000, 0)
        assert await stream.ended(20) is not None
        assert len(stream.events) < 3000
    assert "Ending event stream: 1000 notifications waiting" in caplog.text
    assert "QueueFull" not in caplog.text
    assert await no_listeners(db)


async def test_client_that_never_reads_is_cut_off(server, token, db):
    address = urlsplit(server)
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        sock.connect((address.hostname, address.port))
        sock.setblocking(False)
        loop = asyncio.get_running_loop()
        await loop.sock_sendall(sock, (f"GET /api/events/stream HTTP/1.1\r\nHost: x\r\n"
                                       f"Authorization: Bearer {token}\r\n\r\n").encode())
        assert b"200 OK" in await asyncio.wait_for(loop.sock_recv(sock, 200), 5)
        await db.execute(INSERT, "big", 30, 1_000_000)  # enough to block the server's send
        await asyncio.sleep(2)
        assert await listeners(db) == 1
        await db.execute(INSERT, "small", 1500, 0)
        assert await no_listeners(db, 15)

        async def drain():
            while await loop.sock_recv(sock, 1 << 16):
                pass
        await asyncio.wait_for(drain(), 20)  # the connection really closes


@pytest.mark.parametrize("trigger", ["notification", "lost listener"])
async def test_full_queue_with_stalled_client(db, monkeypatch, trigger):
    monkeypatch.setattr(stream_module, "QUEUE_MAXSIZE", 3)
    loop = asyncio.get_running_loop()
    errors, previous = [], loop.get_exception_handler()
    loop.set_exception_handler(lambda _, context: errors.append(context))
    try:
        response = await stream_module.stream_events()

        async def receive():
            await asyncio.Event().wait()

        async def send(message):
            if message["type"] == "http.response.body":
                await asyncio.Event().wait()  # the client has stopped reading

        task = asyncio.create_task(
            response({"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send))
        await asyncio.sleep(0.2)
        await db.execute(INSERT, "fill", 3, 0)
        await asyncio.sleep(0.5)
        assert not task.done()
        if trigger == "notification":
            await db.execute(INSERT, "overflow", 1, 0)
        else:
            await db.execute("select pg_terminate_backend($1)", response.conn.get_server_pid())
        await asyncio.wait_for(task, 5)
        await asyncio.sleep(0.2)
        assert response.conn.is_closed() and errors == []
    finally:
        loop.set_exception_handler(previous)
    assert await no_listeners(db)
