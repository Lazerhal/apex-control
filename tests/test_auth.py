from datetime import timedelta

import pytest
from jose import jwt

from tests.conftest import BOT_TOKEN, PASSWORD, USERNAME


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
    assert (await anon.get("/api/projects", headers={"X-Bot-Auth": BOT_TOKEN})).status_code == 200
    for wrong in ("wrong", ""):
        assert (await anon.get("/api/projects", headers={"X-Bot-Auth": wrong})).status_code == 401


async def test_health_is_public(anon):
    assert (await anon.get("/health")).json() == {"status": "ok", "environment": "test"}
    assert (await anon.get("/api")).status_code == 200
