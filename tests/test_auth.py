from datetime import timedelta

import pytest
from jose import jwt

from tests.conftest import INTERNAL_KEY, PASSWORD, TELEGRAM_TOKEN, USERNAME


async def test_login_ok(anon):
    res = await anon.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert res.status_code == 200
    assert res.json()["username"] == USERNAME and res.json()["token_type"] == "bearer"
    cookie = res.headers["set-cookie"].lower()
    assert "apex_token=" in cookie and "httponly" in cookie and "secure" in cookie
    me = await anon.get("/auth/me", headers={"Authorization": f"Bearer {res.json()['access_token']}"})
    assert me.json() == {"username": USERNAME, "authenticated": True}


@pytest.mark.parametrize("username,password", [(USERNAME, "wrong"), ("someone", PASSWORD), ("", "")])
async def test_login_fail(anon, username, password):
    res = await anon.post("/auth/login", json={"username": username, "password": password})
    assert res.status_code == 401
    assert res.json() == {"detail": "Invalid credentials"}
    assert "set-cookie" not in res.headers


async def test_cookie_authenticates_and_logout_clears_it(anon):
    await anon.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert (await anon.get("/api/projects")).status_code == 200
    assert (await anon.get("/auth/me")).status_code == 200
    assert (await anon.post("/auth/logout")).status_code == 200
    assert (await anon.get("/api/projects")).status_code == 401


def _protected_operations():
    from src.main import app
    return sorted((method.upper(), path)
                  for path, operations in app.openapi()["paths"].items()
                  if path.startswith("/api/")
                  for method in operations)


async def test_every_api_route_needs_a_token(anon):
    operations = _protected_operations()
    assert len(operations) >= 18
    for method, path in operations:
        url = path
        for name in ("project_id", "task_id", "idea_id", "apex_id"):
            url = url.replace("{" + name + "}", "00000000-0000-0000-0000-000000000000")
        res = await anon.request(method, url, json={})
        assert res.status_code == 401, f"{method} {path} -> {res.status_code}"


async def test_me_without_token(anon):
    assert (await anon.get("/auth/me")).status_code == 401


@pytest.mark.parametrize("bad", ["not-a-token", "wrong-key", "expired"])
async def test_bad_tokens_rejected(anon, bad):
    from src.auth import create_access_token
    if bad == "wrong-key":
        bad = jwt.encode({"sub": USERNAME}, "another-key", algorithm="HS256")
    elif bad == "expired":
        bad = create_access_token({"sub": USERNAME}, timedelta(seconds=-10))
    headers = {"Authorization": f"Bearer {bad}"}
    assert (await anon.get("/api/projects", headers=headers)).status_code == 401
    assert (await anon.get("/auth/me", headers=headers)).status_code == 401


async def test_bot_header(anon):
    assert (await anon.get("/api/projects", headers={"X-Bot-Auth": INTERNAL_KEY})).status_code == 200
    for wrong in ("wrong", "", INTERNAL_KEY[:-1], INTERNAL_KEY + "x", b"\xff\xfe"):
        res = await anon.get("/api/projects", headers={"X-Bot-Auth": wrong})
        assert res.status_code == 401, wrong


async def test_telegram_token_is_no_longer_a_credential(anon):
    res = await anon.get("/api/projects", headers={"X-Bot-Auth": TELEGRAM_TOKEN})
    assert res.status_code == 401


async def test_bot_key_is_compared_in_constant_time(anon, monkeypatch):
    import hmac
    seen, real = [], hmac.compare_digest

    def spy(a, b):
        seen.append((a, b))
        return real(a, b)

    monkeypatch.setattr(hmac, "compare_digest", spy)
    await anon.get("/api/projects", headers={"X-Bot-Auth": "guess"})
    assert (b"guess", INTERNAL_KEY.encode()) in seen


@pytest.mark.parametrize("sent", ["", "anything", TELEGRAM_TOKEN])
async def test_no_internal_key_means_no_bot_access(anon, monkeypatch, sent):
    from src.auth import settings
    monkeypatch.setattr(settings, "apex_internal_key", "")
    assert (await anon.get("/api/projects", headers={"X-Bot-Auth": sent})).status_code == 401


async def test_health_is_public(anon):
    assert (await anon.get("/health")).json() == {"status": "ok", "environment": "test"}
    assert (await anon.get("/api")).status_code == 200
