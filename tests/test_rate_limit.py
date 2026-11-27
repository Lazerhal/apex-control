"""Five failed logins from one address in 15 minutes block it with 429."""
import asyncio
import json

import httpx
import pytest

from src.rate_limit import FailureLimiter, login_limiter
from tests.conftest import PASSWORD, USERNAME

GOOD = {"username": USERNAME, "password": PASSWORD}
BAD = {"username": USERNAME, "password": "wrong"}


async def login(client, body=BAD, **headers):
    return await client.post("/auth/login", json=body, headers=headers)


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(login_limiter, "clock", lambda: now[0])
    return now


async def test_sixth_attempt_is_blocked_and_recorded(anon, db):
    assert [(await login(anon)).status_code for _ in range(5)] == [401] * 5
    for body in (BAD, GOOD):  # even the right password has to wait
        res = await login(anon, body)
        assert res.status_code == 429
        assert 0 < int(res.headers["retry-after"]) <= 900
        assert "set-cookie" not in res.headers
    events = await db.fetch("select * from events where kind = 'auth.login_rate_limited'")
    assert len(events) == 2 and events[0]["status"] == "error"
    assert json.loads(events[0]["payload"]) == {"ip": "127.0.0.1"}
    assert await db.fetchval("select count(*) from events where kind = 'auth.login_failure'") == 5


async def test_unknown_usernames_count_too(anon):
    for _ in range(5):
        await login(anon, {"username": "someone", "password": "p"})
    assert (await login(anon, GOOD)).status_code == 429


async def test_successful_logins_do_not_count(anon):
    for _ in range(4):
        await login(anon)
    assert [(await login(anon, GOOD)).status_code for _ in range(10)] == [200] * 10


async def test_the_block_ends_15_minutes_after_the_failures(anon, clock):
    for _ in range(5):
        await login(anon)
        clock[0] += 60
    # The first failure was 5 minutes ago. Blocked attempts do not extend the block
    res = await login(anon)
    assert (res.status_code, res.headers["retry-after"]) == (429, "600")
    clock[0] += 599
    assert (await login(anon, GOOD)).status_code == 429
    clock[0] += 1
    assert (await login(anon, GOOD)).status_code == 200
    assert (await login(anon)).status_code == 401  # a fifth recent failure again
    assert (await login(anon, GOOD)).status_code == 429


async def test_addresses_are_limited_separately(anon):
    for _ in range(5):
        await login(anon, **{"CF-Connecting-IP": "203.0.113.1"})
    assert (await login(anon, **{"CF-Connecting-IP": "203.0.113.1"})).status_code == 429
    assert (await login(anon, GOOD, **{"CF-Connecting-IP": "203.0.113.2"})).status_code == 200
    assert (await login(anon, GOOD)).status_code == 200


async def test_remote_connections_cannot_choose_their_address(app):
    transport = httpx.ASGITransport(app=app, client=("198.51.100.7", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as remote:
        statuses = [(await login(remote, **{"CF-Connecting-IP": f"203.0.113.{n}"})).status_code
                    for n in range(6)]
    assert statuses == [401] * 5 + [429]


async def test_a_header_that_is_not_an_address_is_ignored(anon):
    statuses = [(await login(anon, **{"CF-Connecting-IP": f"junk-{n}"})).status_code
                for n in range(6)]
    assert statuses == [401] * 5 + [429]


async def test_simultaneous_attempts_cannot_pass_the_limit(anon):
    responses = await asyncio.gather(*(login(anon) for _ in range(12)))
    assert sorted(r.status_code for r in responses) == [401] * 5 + [429] * 7


async def test_blocked_even_when_events_cannot_be_stored(anon, events_unavailable):
    async with events_unavailable():
        statuses = [(await login(anon)).status_code for _ in range(6)]
    assert statuses == [401] * 5 + [429]


def test_old_addresses_are_forgotten():
    now = [0.0]
    limiter = FailureLimiter(clock=lambda: now[0])
    for n in range(100):
        limiter.record_failure(str(n))
    now[0] = 901
    limiter.record_failure("new")
    assert list(limiter._failures) == ["new"]
