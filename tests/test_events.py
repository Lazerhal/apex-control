"""emit(), every place that calls it, and GET/POST /api/events."""
import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import src.events as events_module
from src.events import emit
from tests.conftest import PASSWORD, USERNAME
from tests.test_projects import NOWHERE


async def rows(db):
    found = await db.fetch("select * from events order by created_at")
    return [{**dict(r), "payload": json.loads(r["payload"])} for r in found]


# ── emit ──────────────────────────────────────────────────────────

async def test_emit_stores_every_field(db, project):
    await db.execute("truncate events")
    event = await emit("a.b", "bot", target="api", project_id=uuid.UUID(project["id"]), actor="me",
                       status="error", payload={"k": 1}, latency_ms=5, cost_usd=0.000125)
    assert event.id and event.created_at
    (row,) = await rows(db)
    assert (row["kind"], row["source"], row["target"], row["actor"]) == ("a.b", "bot", "api", "me")
    assert (row["status"], row["latency_ms"], float(row["cost_usd"])) == ("error", 5, 0.000125)
    assert row["payload"] == {"k": 1} and str(row["project_id"]) == project["id"]


async def test_emit_defaults(db):
    await emit("a.b", "api")
    (row,) = await rows(db)
    assert (row["status"], row["payload"], row["project_id"]) == ("ok", {}, None)


@pytest.mark.parametrize("bad", [
    {"project_id": uuid.UUID(NOWHERE)},       # foreign key violation
    {"actor": "x" * 51},                      # too long for the column
    {"payload": {"k": object()}},             # not JSON serialisable
    {"cost_usd": 10 ** 9},                    # numeric overflow
])
async def test_emit_never_raises_on_bad_data(db, bad, caplog):
    assert await emit("a.b", "api", **bad) is None
    assert "Failed to emit event" in caplog.text
    assert await rows(db) == []


async def test_emit_never_raises_when_database_is_unreachable(monkeypatch):
    engine = create_async_engine("postgresql+asyncpg://x:x@127.0.0.1:1/unreachable_test")
    monkeypatch.setattr(events_module, "AsyncSessionLocal", async_sessionmaker(engine))
    assert await emit("a.b", "api") is None
    await engine.dispose()


async def test_emit_never_raises_when_database_hangs(db, monkeypatch, caplog):
    monkeypatch.setattr(events_module, "EMIT_TIMEOUT_SECONDS", 0.3)
    async with db.transaction():
        await db.execute("lock table events in access exclusive mode")
        assert await emit("a.b", "api") is None
    assert "TimeoutError" in caplog.text


# ── Every emit point ──────────────────────────────────────────────

async def test_login_events_never_record_secrets(anon, db):
    for username, password in [("typed-password-here", "x"), (USERNAME, "wrong-secret"),
                               (USERNAME, PASSWORD)]:
        await anon.post("/auth/login", json={"username": username, "password": password})
    found = await rows(db)
    assert [(e["kind"], e["status"], e["actor"], e["payload"]) for e in found] == [
        ("auth.login_failure", "error", None, {"reason": "unknown_username"}),
        ("auth.login_failure", "error", USERNAME, {"reason": "bad_password"}),
        ("auth.login_success", "ok", USERNAME, {}),
    ]
    dump = str(found)
    for secret in ("typed-password-here", "wrong-secret", PASSWORD):
        assert secret not in dump


async def write_everything(client):
    """Calls every endpoint that emits, in order; returns the responses."""
    responses = []

    async def send(method, url, body=None):
        responses.append(await client.request(method, url, json=body))
        return responses[-1].json()

    project = await send("POST", "/api/projects", {"name": "p", "type": "saas"})
    base = f"/api/projects/{project['id']}"
    await send("PATCH", base, {"stage": "live", "goal": "g"})
    task = await send("POST", f"{base}/tasks", {"title": "t"})
    await send("PATCH", f"{base}/tasks/{task['id']}", {"status": "done"})
    await send("POST", f"{base}/notes", {"content": "secret note text"})
    await send("POST", f"{base}/handoffs", {
        "what_was_done": "a", "what_remains": "b", "next_model_should": "c", "session_tool": "cc"})
    await send("POST", "/api/ideas", {"title": "i", "raw_description": "d"})
    await send("DELETE", base)
    return responses


async def test_each_write_emits_one_event(client, db):
    responses = await write_everything(client)
    created, _, task, _, note, handoff, idea, _ = [r.json() for r in responses]
    found = await rows(db)
    apex = {"apex_id": created["apex_id"]}
    task_ref = {"task_id": task["id"], "apex_task_id": "T-001"}
    assert [(e["kind"], e["payload"]) for e in found] == [
        ("project.created", {**apex, "name": "p"}),
        ("project.updated", {**apex, "fields": ["goal", "stage"]}),
        ("task.created", {**task_ref, "title": "t"}),
        ("task.updated", {**task_ref, "fields": ["status"], "task_status": "done"}),
        ("note.created", {"note_id": note["id"], "note_source": "dashboard"}),
        ("handoff.created", {"handoff_id": handoff["id"], "session_tool": "cc"}),
        ("idea.created", {"idea_id": idea["id"], "title": "i", "idea_source": "dashboard"}),
        ("project.deleted", {**apex, "name": "p"}),
    ]
    assert {e["source"] for e in found} == {"api"}
    assert [str(e["project_id"]) for e in found if e["kind"] != "idea.created"] == [created["id"]] * 7
    assert "secret note text" not in str(found)


async def test_rejected_writes_emit_nothing(client, db):
    await client.post(f"/api/projects/{NOWHERE}/notes", json={"content": "x"})
    await client.patch(f"/api/projects/{NOWHERE}", json={})
    await client.post("/api/ideas", json={})
    assert await rows(db) == []


async def test_writes_succeed_when_events_are_broken(client, anon, events_unavailable):
    async with events_unavailable():
        responses = await write_everything(client)
        login = await anon.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
        failed = await anon.post("/auth/login", json={"username": USERNAME, "password": "no"})
    assert [r.status_code for r in responses] == [201, 200, 201, 200, 201, 201, 201, 200]
    assert (login.status_code, failed.status_code) == (200, 401)


# ── GET and POST /api/events ──────────────────────────────────────

async def test_post_event(client, project, db):
    res = await client.post("/api/events", json={
        "kind": "forge.run", "source": "forge", "target": "api", "project_id": project["id"],
        "actor": "forge", "latency_ms": 10, "cost_usd": 0.5, "payload": {"n": [1]}})
    assert res.status_code == 201
    assert res.json()["cost_usd"] == 0.5 and res.json()["payload"] == {"n": [1]}
    assert await db.fetchval("select count(*) from events where kind = 'forge.run'") == 1


@pytest.mark.parametrize("change", [
    {"kind": None}, {"source": None}, {"kind": ""}, {"kind": "k" * 51}, {"source": "s" * 31},
    {"target": "t" * 51}, {"actor": "a" * 51}, {"status": "s" * 21}, {"latency_ms": -1},
    {"cost_usd": -1}, {"cost_usd": 10000}, {"project_id": "nope"}, {"payload": [1]},
])
async def test_post_event_validation(client, change):
    res = await client.post("/api/events", json={"kind": "a.b", "source": "bot", **change})
    assert res.status_code == 422, res.text


async def test_post_event_unknown_project(client):
    res = await client.post("/api/events", json={"kind": "a", "source": "bot", "project_id": NOWHERE})
    assert res.status_code == 404


async def test_post_event_storage_failure_is_503(client, events_unavailable):
    async with events_unavailable():
        res = await client.post("/api/events", json={"kind": "a", "source": "bot"})
    assert res.status_code == 503


async def test_list_newest_first_with_limits_and_filters(client, project, db):
    await db.execute("truncate events")
    await db.execute("""
        insert into events (id, kind, source, created_at)
        select gen_random_uuid(), 'bulk', 'api', now() - make_interval(secs => 1000 - g)
        from generate_series(1, 600) g""")
    await client.post("/api/events", json={"kind": "special", "source": "bot", "project_id": project["id"]})
    default = (await client.get("/api/events")).json()
    assert len(default) == 50 and default[0]["kind"] == "special"
    stamps = [e["created_at"] for e in default]
    assert stamps == sorted(stamps, reverse=True)
    assert len((await client.get("/api/events?limit=500")).json()) == 500
    assert len((await client.get("/api/events?limit=1")).json()) == 1
    for bad in ("0", "501", "x"):
        assert (await client.get(f"/api/events?limit={bad}")).status_code == 422
    assert [e["kind"] for e in (await client.get("/api/events?kind=special")).json()] == ["special"]
    by_project = (await client.get(f"/api/events?project_id={project['id']}")).json()
    assert [e["kind"] for e in by_project] == ["special"]
    assert (await client.get(f"/api/events?project_id={NOWHERE}")).json() == []


@pytest.mark.parametrize("body", [
    '{"kind": "a", "source": "bot", "cost_usd": NaN}',
    '{"source": "bot", "cost_usd": Infinity}',  # the error repeats the whole body
])
async def test_non_finite_numbers_get_a_422(client, body):
    res = await client.post("/api/events", content=body, headers={"Content-Type": "application/json"})
    assert res.status_code == 422, res.text
